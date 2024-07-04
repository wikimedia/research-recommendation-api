from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

from recommendation.utils import language_pairs


class RecommendationAlgorithmEnum(str, Enum):
    morelike = "morelike"
    mostpopular = "mostpopular"


class RankMethodEnum(str, Enum):
    default = "default"
    sitelinks = "sitelinks"


class TranslationRecommendationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=False)
    source: str = Field(
        ...,
        description="Source wiki project language code",
    )
    target: str = Field(
        ...,
        description="Target wiki project language code",
    )
    count: int = Field(
        description="Number of recommendations to fetch",
        default=12,
    )
    seed: Optional[str] = Field(
        description="Seed article list for personalized recommendations, separated by |",
        default=None,
    )
    include_pageviews: bool = Field(
        description="Whether to include pageview counts",
        default=False,
    )
    search_algorithm: RecommendationAlgorithmEnum = Field(
        description="Which search algorithm to use if a seed is specified",
        default=RecommendationAlgorithmEnum.morelike,
    )
    rank_method: RankMethodEnum = Field(
        description="rank_method",
        default=RankMethodEnum.default,
    )

    @model_validator(mode="after")
    def verify_languags(self) -> Self:
        if not language_pairs.is_valid_source_language(self.source):
            raise ValueError("Invalid source language code")

        if not language_pairs.is_valid_target_language(self.target):
            raise ValueError("Invalid target language code")
        if self.source == self.target:
            raise ValueError("Source and target languages must be different")
        return self


class TranslationRecommendation(BaseModel):
    title: str
    pageviews: Optional[int] = 0
    wikidata_id: Optional[str] = None
    rank: Optional[float] = 0.0
    langlinks_count: Optional[int] = 0


class TranslationRecommendationCandidate(TranslationRecommendation):
    languages: Optional[list[str]] = None
