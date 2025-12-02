import random
from typing import List, Optional, Tuple

from recommendation.api.translation.models import (
    PageCollection,
    SectionTranslationRecommendation,
    SectionTranslationRecommendationResponse,
    TranslationRecommendation,
    TranslationRecommendationRequest,
    TranslationRecommendationResponse,
    WikiDataArticle,
)
from recommendation.cache import get_page_collection_cache
from recommendation.recommenders.base_recommender import BaseRecommender
from recommendation.utils.lead_section_size_helper import (
    add_lead_section_sizes_to_recommendations,
)
from recommendation.utils.recommendation_helper import filter_recommendations_by_lead_section_size
from recommendation.utils.section_recommendation_helper import get_section_suggestions_for_recommendations
from recommendation.utils.size_helper import matches_article_size_filter


class SingleCollectionRecommender(BaseRecommender):
    def __init__(self, request_model: TranslationRecommendationRequest):
        self.source_language = request_model.source
        self.target_language = request_model.target
        self.collections = request_model.collections
        self.collection_name = request_model.seed
        self.count = request_model.count
        self.min_size = request_model.min_size
        self.max_size = request_model.max_size
        self.lead_section = request_model.lead_section
        self.continue_offset = request_model.continue_offset
        self.continue_seed = request_model.continue_seed

        page_collection_cache = get_page_collection_cache()
        self.page_collections: List[PageCollection] = page_collection_cache.get_page_collections()

    def match(self) -> bool:
        return self.collections and len(self.get_matched_collections()) == 1

    def get_matched_collections(self) -> List[PageCollection]:
        if not self.collection_name:
            return []

        return [
            collection
            for collection in self.page_collections
            if collection.name.casefold() == self.collection_name.casefold()
            or collection.name.casefold().startswith(f"{self.collection_name.casefold()}/")
        ]

    async def recommend(self) -> TranslationRecommendationResponse:
        recommendation_response = self.get_recommendations_by_status(
            missing=True, min_size=self.min_size, max_size=self.max_size
        )

        # Apply lead section filtering if requested
        if self.should_filter_by_lead_section_size(self.min_size, self.max_size):
            recommendation_response.recommendations = await filter_recommendations_by_lead_section_size(
                recommendation_response.recommendations, self.source_language, self.min_size, self.max_size
            )
        elif self.lead_section:
            # We always want to add the lead_section_size to the recommendations when "lead_section" URL param is set
            # When "min_size" and/or "max_size" URL param is also provided, we already add the lead_section_size to
            # the recommendation during lead section size filtering, thus no need to add it again here.
            recommendation_response.recommendations = await add_lead_section_sizes_to_recommendations(
                recommendation_response.recommendations, self.source_language
            )

        return recommendation_response

    async def recommend_sections(
        self,
    ) -> SectionTranslationRecommendationResponse:
        recommendation_response = self.get_recommendations_by_status(missing=False, min_size=None, max_size=None)
        section_recommendations: List[
            SectionTranslationRecommendation
        ] = await get_section_suggestions_for_recommendations(
            recommendation_response.recommendations,
            self.source_language,
            self.target_language,
            self.count,
            self.min_size,
            self.max_size,
        )

        if self.continue_offset is not None:
            # Preserve the ordering of the original page list
            index_map = {rec.title: i for i, rec in enumerate(recommendation_response.recommendations)}
            section_recommendations.sort(key=lambda x: index_map.get(x.source_title, float("inf")))

        return SectionTranslationRecommendationResponse(
            recommendations=section_recommendations,
            continue_offset=recommendation_response.continue_offset,
            continue_seed=recommendation_response.continue_seed,
        )

    def get_valid_collection_recommendation_for_wikidata_article(
        self,
        page_collection: PageCollection,
        wikidata_article: WikiDataArticle,
        recommendations: List[TranslationRecommendation],
        missing: bool,
        min_size: Optional[int],
        max_size: Optional[int],
    ) -> Optional[TranslationRecommendation]:
        candidate_source_article_title = wikidata_article.langlinks.get(self.source_language)
        candidate_target_article_title = wikidata_article.langlinks.get(self.target_language)
        already_exists = any(
            wikidata_article.wikidata_id == recommendation.wikidata_id for recommendation in recommendations
        )

        if not candidate_source_article_title or bool(candidate_target_article_title) == missing or already_exists:
            return None

        # Get article size from cached data for source language only
        article_size = wikidata_article.sizes.get(self.source_language)

        # Apply size filtering
        if (
            self.should_filter_by_article_size(min_size, max_size)
            and article_size is not None
            and not matches_article_size_filter(article_size, min_size, max_size)
        ):
            return None

        return TranslationRecommendation(
            title=candidate_source_article_title,
            wikidata_id=wikidata_article.wikidata_id,
            langlinks_count=len(wikidata_article.langlinks),
            size=article_size,
            collection=page_collection.get_metadata(self.target_language),
        )

    def apply_continue_offset(self, collection: PageCollection) -> Tuple[List[WikiDataArticle], Optional[int]]:
        """
        Applies a deterministic shuffled order (based on a seed) to the article list,
        then returns articles starting from the continue_offset position.
        """
        # Sort based on a random seed
        seed = self.continue_seed if self.continue_seed else random.randint(0, 2**32 - 1)
        sorted_articles: List[WikiDataArticle] = self.shuffle_articles_with_seed(collection.articles, seed)
        # If continue_offset == 0 → start from beginning
        if self.continue_offset == 0:
            return sorted_articles, seed

        return sorted_articles[self.continue_offset :], seed

    @staticmethod
    def shuffle_articles_with_seed(articles: List, seed: int) -> List:
        rng = random.Random(seed)
        rng.shuffle(articles)

        return articles

    def get_recommendations_by_status(
        self, missing: bool = True, min_size: Optional[int] = None, max_size: Optional[int] = None
    ) -> TranslationRecommendationResponse:
        page_collection = self.get_matched_collections()[0]

        sorted_articles, continue_seed = self.apply_continue_offset(page_collection)
        page_collection.articles = sorted_articles

        recommendations = []
        articles = page_collection.articles
        i = 0
        while len(recommendations) < self.count and i < len(articles):
            wikidata_article = articles[i]
            i = i + 1
            valid_recommendation_for_collection = self.get_valid_collection_recommendation_for_wikidata_article(
                page_collection, wikidata_article, recommendations, missing, min_size, max_size
            )
            if valid_recommendation_for_collection:
                recommendations.append(valid_recommendation_for_collection)

        if self.continue_offset is None:
            continue_offset = None
        elif i == len(articles):
            # if available collection articles have been exhausted, return -1 to signal end of "pagination"
            continue_offset = -1
        else:
            continue_offset = max(self.continue_offset, 0) + i

        return TranslationRecommendationResponse(
            recommendations=recommendations, continue_offset=continue_offset, continue_seed=continue_seed
        )
