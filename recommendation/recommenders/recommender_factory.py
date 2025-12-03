from recommendation.api.translation.models import TranslationRecommendationRequest
from recommendation.recommenders.featured_collection_search_recommender import FeaturedCollectionSearchRecommender
from recommendation.recommenders.multiple_collection_recommender import MultipleCollectionRecommender
from recommendation.recommenders.popular_recommender import PopularRecommender
from recommendation.recommenders.search_recommender import SearchRecommender
from recommendation.recommenders.single_collection_recommender import SingleCollectionRecommender


class RecommenderFactory:
    def __init__(self, request_model: TranslationRecommendationRequest):
        # Create recommender instances with the request model
        self.recommenders = [
            SingleCollectionRecommender(request_model),
            MultipleCollectionRecommender(request_model),
            FeaturedCollectionSearchRecommender(request_model),
            SearchRecommender(request_model),
            PopularRecommender(request_model),
        ]

    def get_recommender(self):
        for recommender in self.recommenders:
            if recommender.match():
                return recommender
        raise ValueError("No matching recommender found.")
