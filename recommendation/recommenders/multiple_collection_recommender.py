import random
from typing import Dict, List

from recommendation.api.translation.models import (
    PageCollection,
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.cache import get_page_collection_cache
from recommendation.recommenders.base_recommender import BaseRecommender
from recommendation.utils.logger import log


class MultipleCollectionRecommender(BaseRecommender):
    def __init__(self, request_model: TranslationRecommendationRequest):
        self.source_language = request_model.source
        self.target_language = request_model.target
        self.collections = request_model.collections
        self.collection_name = request_model.seed
        self.count = request_model.count
        self.min_size = request_model.min_size
        self.max_size = request_model.max_size
        self.lead_section = request_model.lead_section

        page_collection_cache = get_page_collection_cache()
        self.page_collections: List[PageCollection] = page_collection_cache.get_page_collections()

    def match(self) -> bool:
        return self.collections and len(self.get_matched_collections()) != 1

    def get_matched_collections(self) -> List[PageCollection]:
        if not self.collection_name:
            return []

        return [
            collection
            for collection in self.page_collections
            if collection.name.casefold() == self.collection_name.casefold()
            or collection.name.casefold().startswith(f"{self.collection_name.casefold()}/")
        ]

    def post_filter_article_translation_hook(self, recommendations):
        return self.reorder_page_collection_recommendations(recommendations)

    def pre_section_suggestions_hook(self, candidates):
        return self.reorder_page_collection_recommendations(candidates)

    def post_section_suggestions_hook(self, candidates, section_recommendations):
        return self.reorder_page_collection_recommendations(section_recommendations)

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

    async def get_recommendations_by_status(self, missing: bool = True) -> List[TranslationRecommendation]:
        page_collections = self.page_collections

        if self.collection_name:
            page_collections = self.get_matched_collections()

        active_collections = []
        for page_collection in page_collections:
            if len(page_collection.articles) == 0:
                log.warning(f"Found empty page-collection {page_collection}")
            else:
                active_collections.append(page_collection)

        if not active_collections:
            return []  # Exit early if no page collections have articles

        self.shuffle_collections(active_collections)
        recommendations: Dict = {}

        for page_collection in active_collections:
            collection_metadata = page_collection.get_metadata(self.target_language)

            for wikidata_article in page_collection.articles:
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

    @staticmethod
    def reorder_page_collection_recommendations(
        recommendations: List[TranslationRecommendation | SectionTranslationRecommendation],
    ) -> List[TranslationRecommendation | SectionTranslationRecommendation]:
        """
        Reorders a list of recommendations such that recommendations from different collections are
        interleaved. The method distributes the recommendations by cycling through their collections,
        ensuring that each collection's recommendations are listed in a round-robin fashion.

        Args:
            recommendations: A list of article or section translation recommendations.

        Returns:
            List[TranslationRecommendation|SectionTranslationRecommendation]: A reordered list of recommendations.
        """
        recommendations_by_collection: Dict[
            str, List[TranslationRecommendation | SectionTranslationRecommendation]
        ] = {}

        for recommendation in recommendations:
            collection_name = recommendation.collection.name
            if collection_name not in recommendations_by_collection:
                recommendations_by_collection[collection_name] = []  # Initialize a list for this collection
            recommendations_by_collection[collection_name].append(recommendation)

        collection_groups: List[List[TranslationRecommendation | SectionTranslationRecommendation]] = list(
            recommendations_by_collection.values()
        )
        max_len = max((len(group) for group in collection_groups), default=0)

        # Interleave the recommendations so each one has a different collection
        recommendations = []
        for i in range(max_len):
            for group in collection_groups:
                if i < len(group):
                    recommendations.append(group[i])

        return recommendations
