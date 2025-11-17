from abc import ABC, abstractmethod
from typing import Optional

from recommendation.api.translation.models import (
    SectionTranslationRecommendationResponse,
    TranslationRecommendationResponse,
)


class BaseRecommender(ABC):
    lead_section: bool = False  # subclasses should set this as appropriate

    @abstractmethod
    def match(self) -> bool:
        """Check if this recommender matches the request parameters."""
        pass

    @abstractmethod
    def recommend(self) -> TranslationRecommendationResponse:
        """Generate recommendations based on input parameters."""
        pass

    @abstractmethod
    def recommend_sections(self) -> SectionTranslationRecommendationResponse:
        """Generate section recommendations based on input parameters."""
        pass

    def should_filter_by_article_size(self, min_size: Optional[int], max_size: Optional[int]) -> bool:
        """Return True if article size filtering should be applied for recommendations."""
        return not self.lead_section and (min_size is not None or max_size is not None)

    def should_filter_by_lead_section_size(self, min_size: Optional[int], max_size: Optional[int]) -> bool:
        """Return True if size filtering should be applied for the lead sections of the recommendations."""
        return self.lead_section and (min_size is not None or max_size is not None)
