from abc import ABC, abstractmethod
from typing import List

from recommendation.api.translation.models import (
    SectionTranslationRecommendation,
    TranslationRecommendation,
)


class BaseRecommender(ABC):
    @abstractmethod
    def match(self) -> bool:
        """Check if this recommender matches the request parameters."""
        pass

    @abstractmethod
    def recommend(self) -> List[TranslationRecommendation]:
        """Generate recommendations based on input parameters."""
        pass

    @abstractmethod
    def recommend_sections(self) -> List[SectionTranslationRecommendation]:
        """Generate section recommendations based on input parameters."""
        pass
