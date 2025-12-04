import random
from itertools import zip_longest
from typing import Dict, List, Optional

from recommendation.api.translation.models import (
    PageCollection,
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.cache import get_page_collection_cache
from recommendation.recommenders.base_recommender import BaseRecommender
from recommendation.utils.recommendation_helper import interleave_by_ratio

MAX_RECOMMENDATIONS = 500


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
        self.featured_collection: Optional[PageCollection] = self.get_collection(request_model.featured_collection)

    def match(self) -> bool:
        return self.collections and len(self.get_matched_collections()) != 1

    def get_collection(self, collection_name):
        if not collection_name:
            return None

        found = None
        for collection in self.page_collections:
            if collection.name.casefold() == collection_name.casefold():
                found = collection
                break

        return found

    def get_featured_collection_recommendations_by_status(self, missing):
        if not self.featured_collection:
            return []

        recommendations = []
        collection_metadata = self.featured_collection.get_metadata(self.target_language)
        for article in self.featured_collection.articles:
            if (
                article.langlinks.get(self.source_language)
                and bool(article.langlinks.get(self.target_language)) != missing
            ):
                recommendation = TranslationRecommendation(
                    title=article.langlinks.get(self.source_language),
                    wikidata_id=article.wikidata_id,
                    langlinks_count=len(article.langlinks),
                    size=article.sizes.get(self.source_language),
                    collection=collection_metadata,
                )
                recommendations.append(recommendation)

        return recommendations

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

    def post_section_suggestions_hook(self, candidates, section_recommendations):
        return self.reorder_page_collection_recommendations(section_recommendations)

    def reorder_page_collection_recommendations(
        self, recommendations: List[TranslationRecommendation | SectionTranslationRecommendation]
    ) -> List[TranslationRecommendation | SectionTranslationRecommendation]:
        if not self.featured_collection:
            return self.interleave_by_collection(recommendations)

        simple_recommendations = []
        featured_recommendations = []
        for recommendation in recommendations:
            if recommendation.collection.name == self.featured_collection.name:
                featured_recommendations.append(recommendation)
            else:
                simple_recommendations.append(recommendation)

        simple_recommendations = self.interleave_by_collection(simple_recommendations)

        return interleave_by_ratio(simple_recommendations, featured_recommendations)

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

        if self.featured_collection:
            page_collections = [
                collection
                for collection in page_collections
                if collection.name.casefold() != self.featured_collection.name.casefold()
            ]

        self.shuffle_collections(page_collections)

        collection_articles = []
        for page_collection in page_collections:
            collection_metadata = page_collection.get_metadata(self.target_language)

            articles_list = [
                (article, collection_metadata)
                for article in page_collection.articles
                if article.langlinks.get(self.source_language)
                and bool(article.langlinks.get(self.target_language)) != missing
            ]

            if articles_list:
                collection_articles.append(articles_list)

        recommendations: Dict = {}
        # Interleave and add to recommendations with limit
        for articles_tuple in zip_longest(*collection_articles):
            for article_data in articles_tuple:
                if len(recommendations) >= MAX_RECOMMENDATIONS:
                    break  # Exit when limit reached

                if article_data and article_data[0].wikidata_id not in recommendations:
                    article, metadata = article_data
                    recommendations[article.wikidata_id] = TranslationRecommendation(
                        title=article.langlinks.get(self.source_language),
                        wikidata_id=article.wikidata_id,
                        langlinks_count=len(article.langlinks),
                        size=article.sizes.get(self.source_language),
                        collection=metadata,
                    )

        featured_recommendations = self.get_featured_collection_recommendations_by_status(missing)

        return interleave_by_ratio(list(recommendations.values()), featured_recommendations)

    @staticmethod
    def interleave_by_collection(
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
