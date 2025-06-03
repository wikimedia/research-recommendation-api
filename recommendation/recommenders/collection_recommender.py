import random
from itertools import cycle
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
from recommendation.utils.section_recommendation_helper import get_section_suggestions_for_recommendations


class CollectionRecommender(BaseRecommender):
    def __init__(self, request_model: TranslationRecommendationRequest):
        self.source_language = request_model.source
        self.target_language = request_model.target
        self.collections = request_model.collections
        self.collection_name = request_model.seed
        self.count = request_model.count

    def match(self) -> bool:
        return self.collections

    def recommend(self) -> List[TranslationRecommendation]:
        return self.get_recommendations_by_status(missing=True)

    async def recommend_sections(
        self,
    ) -> List[SectionTranslationRecommendation]:
        recommendations = self.get_recommendations_by_status(missing=False)
        recommendations = await get_section_suggestions_for_recommendations(
            recommendations, self.source_language, self.target_language, self.count
        )

        return self.reorder_page_collection_section_recommendations(recommendations)

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

    def get_recommendations_by_status(self, missing=True):
        page_collection_cache = get_page_collection_cache()
        page_collections: List[PageCollection] = page_collection_cache.get_page_collections()

        if self.collection_name:
            page_collections = [
                collection
                for collection in page_collections
                if collection.name.casefold() == self.collection_name.casefold()
                or collection.name.casefold().startswith(f"{self.collection_name.casefold()}/")
            ]

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
                    candidate_source_article_title = wikidata_article.langlinks.get(self.source_language)
                    candidate_target_article_title = wikidata_article.langlinks.get(self.target_language)
                    already_exists = any(
                        wikidata_article.wikidata_id == recommendation.wikidata_id for recommendation in recommendations
                    )
                    if (
                        candidate_source_article_title
                        and bool(candidate_target_article_title) != missing
                        and not already_exists
                    ):
                        valid_recommendation_for_collection = TranslationRecommendation(
                            title=candidate_source_article_title,
                            wikidata_id=wikidata_article.wikidata_id,
                            langlinks_count=len(wikidata_article.langlinks),
                            collection=page_collection.get_metadata(self.target_language),
                        )

                recommendations.append(valid_recommendation_for_collection)

            except StopIteration:
                # Remove exhausted iterator
                article_iterators.remove(active_iterator)
                active_iterators = cycle(article_iterators)
                if not article_iterators:
                    break

        return recommendations

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
