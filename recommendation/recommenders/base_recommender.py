from abc import ABC, abstractmethod
from typing import List, Optional

from recommendation.api.translation.models import (
    SectionTranslationRecommendation,
    SectionTranslationRecommendationResponse,
    TranslationRecommendation,
    TranslationRecommendationResponse,
)
from recommendation.utils.lead_section_size_helper import add_lead_section_sizes_to_recommendations
from recommendation.utils.recommendation_helper import filter_recommendations_by_lead_section_size
from recommendation.utils.section_recommendation_helper import get_section_suggestions_for_recommendations
from recommendation.utils.size_helper import matches_article_size_filter


class BaseRecommender(ABC):
    # Subclasses must set these
    source_language: str
    target_language: str
    count: int
    min_size: Optional[int]
    max_size: Optional[int]
    lead_section: bool = False

    @abstractmethod
    def match(self) -> bool:
        """Check if this recommender matches the request parameters."""
        pass

    @abstractmethod
    async def get_recommendations_by_status(self, missing: bool) -> List[TranslationRecommendation]:
        pass

    def post_filter_article_translation_hook(
        self, recommendations: List[TranslationRecommendation]
    ) -> List[TranslationRecommendation]:
        """Override to apply post-filtering transformations (e.g., reordering)."""
        return recommendations

    def build_translation_recommendation_response(
        self, recommendations: List[TranslationRecommendation]
    ) -> TranslationRecommendationResponse:
        """Override to customize response (e.g., add continue_offset)."""
        return TranslationRecommendationResponse(recommendations=recommendations)

    async def recommend(self) -> TranslationRecommendationResponse:
        candidates = await self.get_recommendations_by_status(missing=True)

        if self.should_filter_by_article_size(self.min_size, self.max_size):
            recommendations = [
                candidate
                for candidate in candidates
                if matches_article_size_filter(candidate.size, self.min_size, self.max_size)
            ]
            recommendations = self.post_filter_article_translation_hook(recommendations)
            recommendations = recommendations[: self.count]

        elif self.should_filter_by_lead_section_size(self.min_size, self.max_size):
            recommendations = await filter_recommendations_by_lead_section_size(
                candidates, self.source_language, self.min_size, self.max_size, self.count
            )
            recommendations = self.post_filter_article_translation_hook(recommendations)

        elif self.lead_section:
            recommendations = self.post_filter_article_translation_hook(candidates)
            recommendations = recommendations[: self.count]
            recommendations = await add_lead_section_sizes_to_recommendations(recommendations, self.source_language)

        else:
            recommendations = self.post_filter_article_translation_hook(candidates)
            recommendations = recommendations[: self.count]

        return self.build_translation_recommendation_response(recommendations)

    def pre_section_suggestions_hook(
        self, candidates: List[TranslationRecommendation]
    ) -> List[TranslationRecommendation]:
        """Override to transform candidates before fetching section suggestions."""
        return candidates

    def post_section_suggestions_hook(
        self,
        candidates: List[TranslationRecommendation],
        section_recommendations: List[SectionTranslationRecommendation],
    ) -> List[SectionTranslationRecommendation]:
        """Override to transform section recommendations after fetching."""
        return section_recommendations

    def build_section_translation_response(
        self, section_recommendations: List[SectionTranslationRecommendation]
    ) -> SectionTranslationRecommendationResponse:
        """Override to customize section response."""
        return SectionTranslationRecommendationResponse(recommendations=section_recommendations)

    async def recommend_sections(self) -> SectionTranslationRecommendationResponse:
        candidates = await self.get_recommendations_by_status(missing=False)
        candidates = self.pre_section_suggestions_hook(candidates)

        section_recommendations = await get_section_suggestions_for_recommendations(
            candidates,
            self.source_language,
            self.target_language,
            self.count,
            self.min_size,
            self.max_size,
        )

        section_recommendations = self.post_section_suggestions_hook(candidates, section_recommendations)

        return self.build_section_translation_response(section_recommendations)

    def should_filter_by_article_size(self, min_size: Optional[int], max_size: Optional[int]) -> bool:
        """Return True if article size filtering should be applied for recommendations."""
        return not self.lead_section and (min_size is not None or max_size is not None)

    def should_filter_by_lead_section_size(self, min_size: Optional[int], max_size: Optional[int]) -> bool:
        """Return True if size filtering should be applied for the lead sections of the recommendations."""
        return self.lead_section and (min_size is not None or max_size is not None)
