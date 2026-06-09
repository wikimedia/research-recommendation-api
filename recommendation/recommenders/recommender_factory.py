from functools import cached_property
from typing import List

from recommendation.api.translation.models import PageCollection, TranslationRecommendationRequest
from recommendation.cache import get_page_collection_cache
from recommendation.recommenders.featured_collection_search_recommender import FeaturedCollectionSearchRecommender
from recommendation.recommenders.multiple_collection_recommender import MultipleCollectionRecommender
from recommendation.recommenders.popular_recommender import PopularRecommender
from recommendation.recommenders.search_recommender import SearchRecommender
from recommendation.recommenders.single_collection_recommender import SingleCollectionRecommender


class RecommenderFactory:
    # Order matters: first match wins. Collection-aware recommenders are tried before the
    # rest, so the two lists below are evaluated in order (collection-aware, then other).

    # Recommenders that read the (large) page-collection cache. They receive a shared
    # request-scoped provider, so the cache is deserialized at most once per request,
    # instead of once for each one the factory tries while matching.
    COLLECTION_AWARE_CLASSES = [
        SingleCollectionRecommender,
        MultipleCollectionRecommender,
        FeaturedCollectionSearchRecommender,
    ]

    # Recommenders that never touch the page-collection cache.
    OTHER_RECOMMENDER_CLASSES = [
        SearchRecommender,
        PopularRecommender,
    ]

    def __init__(self, request_model: TranslationRecommendationRequest):
        self.request_model = request_model

    @cached_property
    def page_collections(self) -> List[PageCollection]:
        # Lazy + request-scoped: the cache is deserialized only on first access (so
        # non-collection requests never touch it) and then memoized for this request,
        # so every collection recommender shares a single deserialization.
        return get_page_collection_cache().get_page_collections()

    def get_recommender(self):
        # Lazy: instantiate and match one recommender at a time, stopping at the first match,
        # so recommenders ordered after the selected one are never built.
        for recommender_class in self.COLLECTION_AWARE_CLASSES:
            recommender = recommender_class(self.request_model, page_collections_provider=lambda: self.page_collections)
            if recommender.match():
                return recommender

        for recommender_class in self.OTHER_RECOMMENDER_CLASSES:
            recommender = recommender_class(self.request_model)
            if recommender.match():
                return recommender

        raise ValueError("No matching recommender found.")
