import random
from itertools import cycle
from typing import Dict, List, Optional, Tuple

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
from recommendation.utils.logger import log
from recommendation.utils.recommendation_helper import filter_recommendations_by_lead_section_size
from recommendation.utils.section_recommendation_helper import get_section_suggestions_for_recommendations
from recommendation.utils.size_helper import matches_article_size_filter


class CollectionRecommender(BaseRecommender):
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

    def match(self) -> bool:
        return self.collections

    async def recommend(self) -> TranslationRecommendationResponse:
        recommendation_response = await self.get_recommendations_by_status(
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
        recommendation_response = await self.get_recommendations_by_status(missing=False, min_size=None, max_size=None)
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
        else:
            section_recommendations = self.reorder_page_collection_section_recommendations(section_recommendations)

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
    def shuffle_collections(page_collections: List[PageCollection]):
        """
        Shuffles in place page collections and their articles to randomize the recommendations.

        Args:
            page_collections (List[PageCollection]): A list of page collections.
        """
        random.shuffle(page_collections)
        for collection in page_collections:
            random.shuffle(collection.articles)

    @staticmethod
    def shuffle_articles_with_seed(articles: List, seed: int) -> List:
        rng = random.Random(seed)
        rng.shuffle(articles)

        return articles

    def get_recommendations_for_single_collection(
        self,
        page_collection: PageCollection,
        missing: bool,
        min_size: Optional[int],
        max_size: Optional[int],
        continue_seed: Optional[int],
    ) -> TranslationRecommendationResponse:
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

    def get_recommendations_for_multiple_collections(
        self,
        page_collections: List[PageCollection],
        missing: bool,
        min_size: Optional[int],
        max_size: Optional[int],
    ) -> TranslationRecommendationResponse:
        active_collections = []
        for page_collection in page_collections:
            if len(page_collection.articles) == 0:
                log.warning(f"Found empty page-collection {page_collection}")
            else:
                active_collections.append(page_collection)

        if not active_collections:
            return []  # Exit early if no page collections have articles

        self.shuffle_collections(active_collections)

        # Create iterators for the articles of each page collection, paired with their collection
        article_iterators = [(iter(collection.articles), collection) for collection in active_collections]
        # Use cycle to iterate through the iterators in a round-robin fashion
        active_iterators = cycle(article_iterators)

        recommendations = []
        active_iterator = None
        while article_iterators and len(recommendations) < self.count:
            try:
                # Get the next iterator and its associated page collection
                active_iterator = next(active_iterators)
                article_iterator = active_iterator[0]
                page_collection = active_iterator[1]

                valid_recommendation_for_collection = None
                while not valid_recommendation_for_collection:
                    # Fetch the next article from the current iterator
                    wikidata_article = next(article_iterator)

                    valid_recommendation_for_collection = self.get_valid_collection_recommendation_for_wikidata_article(
                        page_collection, wikidata_article, recommendations, missing, min_size, max_size
                    )

                recommendations.append(valid_recommendation_for_collection)

            except StopIteration:
                # Remove exhausted iterator
                article_iterators.remove(active_iterator)
                active_iterators = cycle(article_iterators)
                if not article_iterators:
                    break

        return TranslationRecommendationResponse(recommendations=recommendations)

    async def get_recommendations_by_status(
        self, missing: bool = True, min_size: Optional[int] = None, max_size: Optional[int] = None
    ) -> TranslationRecommendationResponse:
        page_collection_cache = get_page_collection_cache()
        page_collections: List[PageCollection] = page_collection_cache.get_page_collections()
        continue_seed = None

        if self.collection_name:
            normalized_collection_name = self.collection_name.casefold()
            if self.continue_offset is None:
                page_collections = [
                    collection
                    for collection in page_collections
                    if collection.name.casefold() == normalized_collection_name
                    or collection.name.casefold().startswith(f"{normalized_collection_name}/")
                ]
            else:
                matched_collection = None
                for collection in page_collections:
                    if collection.name.casefold() == normalized_collection_name:
                        matched_collection = collection

                if not matched_collection:
                    return TranslationRecommendationResponse(recommendations=[])

                sorted_articles, continue_seed = self.apply_continue_offset(matched_collection)
                matched_collection.articles = sorted_articles
                page_collections = [matched_collection]

        if len(page_collections) == 1:
            return self.get_recommendations_for_single_collection(
                page_collections[0], missing, min_size, max_size, continue_seed
            )
        else:
            return self.get_recommendations_for_multiple_collections(page_collections, missing, min_size, max_size)

    @staticmethod
    def reorder_page_collection_section_recommendations(
        recommendations: List[SectionTranslationRecommendation],
    ) -> List[SectionTranslationRecommendation]:
        """
        Reorders a list of section recommendations such that recommendations from different collections are
        interleaved. The method distributes the recommendations by cycling through their collections,
        ensuring that each collection's recommendations are listed in a round-robin fashion.
        This is used only for section recommendations, because we cannot know beforehand which article will
        produce a valid section recommendation, thus we need to re-order the section recommendations, once
        they have been fetched.

        Args:
            recommendations (List[SectionTranslationRecommendation]): A list of section translation recommendations.

        Returns:
            List[SectionTranslationRecommendation]: A reordered list of recommendations.

        Example:
            >>> collection1 = PageCollectionMetadata( name="Collection One" )
            >>> collection2 = PageCollectionMetadata( name="Collection Two" )
            >>> collection3 = PageCollectionMetadata( name="Collection Three" )

            >>> rec1 = SectionTranslationRecommendation( source_title="Article 1", collection=collection1 )
            >>> rec2 = SectionTranslationRecommendation( source_title="Article 2", collection=collection1 )
            >>> rec3 = SectionTranslationRecommendation( source_title="Article 3", collection=collection2 )
            >>> rec4 = SectionTranslationRecommendation( source_title="Article 4", collection=collection2 )
            >>> rec5 = SectionTranslationRecommendation( source_title="Article 5", collection=collection3 )
            >>> test_recommendations = [rec1, rec2, rec3, rec4, rec5]
            >>> CollectionRecommender.reorder_page_collection_section_recommendations(test_recommendations)
            [rec1, rec3, rec5, rec2, rec4]
        """
        recommendations_by_collection: Dict[str, List[SectionTranslationRecommendation]] = {}

        for recommendation in recommendations:
            collection_name = recommendation.collection.name
            if collection_name not in recommendations_by_collection:
                recommendations_by_collection[collection_name] = []  # Initialize a list for this collection
            recommendations_by_collection[collection_name].append(recommendation)

        collection_groups: List[List[SectionTranslationRecommendation]] = list(recommendations_by_collection.values())
        max_len = max((len(group) for group in collection_groups), default=0)

        # Interleave the recommendations so each one has a different collection
        recommendations = []
        for i in range(max_len):
            for group in collection_groups:
                if i < len(group):
                    recommendations.append(group[i])

        return recommendations
