import random
from typing import Dict, List

from recommendation.api.translation.models import (
    PageCollection,
    SectionTranslationRecommendationResponse,
    TranslationRecommendation,
    TranslationRecommendationRequest,
    TranslationRecommendationResponse,
    WikiDataArticle,
)
from recommendation.cache import get_page_collection_cache
from recommendation.recommenders.base_recommender import BaseRecommender


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
        # continue_offset is always expected for single collections
        self.continue_offset = request_model.continue_offset or 0
        self.continue_seed = request_model.continue_seed

        page_collection_cache = get_page_collection_cache()
        self.page_collections: List[PageCollection] = page_collection_cache.get_page_collections()
        self.sorted_collection_articles = []

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

    def build_translation_recommendation_response(self, recommendations):
        if not recommendations:
            continue_offset = -1
        else:
            continue_offset = self.continue_offset + self.get_index_in_sorted_articles(recommendations[-1].title)

        return TranslationRecommendationResponse(
            recommendations=recommendations,
            continue_offset=continue_offset,
            continue_seed=self.continue_seed,
        )

    def post_section_suggestions_hook(self, candidates, section_recommendations):
        # Preserve ordering of original page list
        index_map = {rec.title: i for i, rec in enumerate(candidates)}
        section_recommendations.sort(key=lambda x: index_map.get(x.source_title, float("inf")))
        return section_recommendations

    def build_section_response(self, section_recommendations):
        if not section_recommendations:
            continue_offset = -1
        else:
            continue_offset = self.continue_offset + self.get_index_in_sorted_articles(
                section_recommendations[-1].source_title
            )

        return SectionTranslationRecommendationResponse(
            recommendations=section_recommendations,
            continue_offset=continue_offset,
            continue_seed=self.continue_seed,
        )

    def get_current_continue_seed(self):
        if not self.continue_seed:
            self.continue_seed = random.randint(0, 2**32 - 1)

        return self.continue_seed

    def apply_continue_offset(self, collection: PageCollection) -> List[WikiDataArticle]:
        """
        Applies a deterministic shuffled order (based on a seed) to the article list,
        then returns articles starting from the continue_offset position.
        """
        # Sort based on a random seed
        seed = self.get_current_continue_seed()
        sorted_articles: List[WikiDataArticle] = self.shuffle_articles_with_seed(collection.articles, seed)
        # If continue_offset == 0 → start from beginning
        if self.continue_offset == 0:
            return sorted_articles

        return sorted_articles[self.continue_offset :]

    def get_index_in_sorted_articles(self, recommendation_title: str) -> int:
        for index, article in enumerate(self.sorted_collection_articles):
            candidate_source_article_title = article.langlinks.get(self.source_language)
            if candidate_source_article_title == recommendation_title:
                return index

        return -1

    @staticmethod
    def shuffle_articles_with_seed(articles: List, seed: int) -> List:
        rng = random.Random(seed)
        rng.shuffle(articles)

        return articles

    async def get_recommendations_by_status(self, missing: bool = True) -> List[TranslationRecommendation]:
        page_collection = self.get_matched_collections()[0]
        self.sorted_collection_articles = self.apply_continue_offset(page_collection)

        recommendations: Dict = {}
        collection_metadata = page_collection.get_metadata(self.target_language)

        for wikidata_article in self.sorted_collection_articles:
            candidate_source_article_title = wikidata_article.langlinks.get(self.source_language)
            candidate_target_article_title = wikidata_article.langlinks.get(self.target_language)
            if (
                candidate_source_article_title
                and bool(candidate_target_article_title) != missing
                and wikidata_article.wikidata_id not in recommendations
            ):
                recommendations[wikidata_article.wikidata_id] = TranslationRecommendation(
                    title=candidate_source_article_title,
                    wikidata_id=wikidata_article.wikidata_id,
                    langlinks_count=len(wikidata_article.langlinks),
                    size=wikidata_article.sizes.get(self.source_language),
                    collection=collection_metadata,
                )

        return list(recommendations.values())
