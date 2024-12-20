from recommendation.api.translation.models import TranslationRecommendationRequest
from recommendation.recommenders.collection_recommender import CollectionRecommender
from recommendation.recommenders.popular_recommender import PopularRecommender
from recommendation.recommenders.search_recommender import SearchRecommender


class RecommenderFactory:
    def __init__(self, request_model: TranslationRecommendationRequest):
        # Create recommender instances with the request model
        self.recommenders = [
            CollectionRecommender(request_model),
            SearchRecommender(request_model),
            PopularRecommender(request_model),
        ]

    def get_recommender(self):
        for recommender in self.recommenders:
            if recommender.match():
                return recommender
        raise ValueError("No matching recommender found.")
