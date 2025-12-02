import random
from typing import Dict, List

from recommendation.api.translation.models import (
    PageCollection,
    SectionTranslationRecommendation,
    SectionTranslationRecommendationResponse,
    TranslationRecommendation,
    TranslationRecommendationRequest,
    TranslationRecommendationResponse,
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

    async def recommend(self) -> TranslationRecommendationResponse:
        candidates = self.get_recommendations_by_status(missing=True)

        if self.should_filter_by_article_size(self.min_size, self.max_size):
            recommendations = [
                candidate
                for candidate in candidates
                if matches_article_size_filter(candidate.size, self.min_size, self.max_size)
            ]
            recommendations = self.reorder_page_collection_recommendations(recommendations)
            recommendations = recommendations[: self.count]
        # Apply lead section filtering if requested
        elif self.should_filter_by_lead_section_size(self.min_size, self.max_size):
            # at most "count" recommendations will be returned. Once enough recommendations have been fetched
            # the lead section requests will stop
            recommendations = await filter_recommendations_by_lead_section_size(
                candidates, self.source_language, self.min_size, self.max_size, self.count
            )
            recommendations = self.reorder_page_collection_recommendations(recommendations)
        elif self.lead_section:
            # We always want to add the lead_section_size to the recommendations when "lead_section" URL param is set
            # When "min_size" and/or "max_size" URL param is also provided, we already add the lead_section_size to
            # the recommendation during lead section size filtering, thus no need to add it again here.
            recommendations = self.reorder_page_collection_recommendations(candidates)
            recommendations = recommendations[: self.count]
            recommendations = await add_lead_section_sizes_to_recommendations(recommendations, self.source_language)
        else:
            recommendations = self.reorder_page_collection_recommendations(candidates)
            recommendations = recommendations[: self.count]

        return TranslationRecommendationResponse(recommendations=recommendations)

    async def recommend_sections(self) -> SectionTranslationRecommendationResponse:
        candidates = self.get_recommendations_by_status(missing=False)
        candidates = self.reorder_page_collection_recommendations(candidates)
        recommendations = await get_section_suggestions_for_recommendations(
            candidates, self.source_language, self.target_language, self.count, self.min_size, self.max_size
        )

        recommendations = self.reorder_page_collection_recommendations(recommendations)

        return SectionTranslationRecommendationResponse(recommendations=recommendations)

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

    def get_recommendations_by_status(self, missing: bool = True) -> List[TranslationRecommendation]:
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
