from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class WikiDataArticle(BaseModel):
    wikidata_id: str
    langlinks: Dict[str, str]


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
    topic: Optional[str] = Field(
        description="""Article topic for personalized recommendations.
                Refer https://www.mediawiki.org/wiki/ORES/Articletopic#Taxonomy for possible topics.""",
        default=None,
        examples=["Fashion", "Music+South Africa", "Southern Africa|Western Africa", "Women+Space"],
    )
    include_campaigns: bool = Field(
        description="Whether to include articles associated with a campaign",
        default=False,
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
    def verify_languages(self) -> Self:
        # This import is here to avoid circular imports
        from recommendation.utils import language_pairs

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


class SectionTranslationRecommendation(BaseModel):
    source_title: str = Field(
        description="Source title of the section translation recommendation",
    )
    target_title: str = Field(
        description="Target title of the section translation recommendation",
    )
    source_sections: List[str] = Field(
        description="List of section titles of the source article of the section translation recommendation",
    )
    target_sections: List[str] = Field(
        description="List of section titles of the target article of the section translation recommendation",
    )
    present: Dict[str, str] = Field(
        description="""Dict that maps the source section titles that are also present in the target article,
                    to the corresponding target section titles of the section translation recommendation""",
    )
    missing: Dict[str, str] = Field(
        description="""Dict that maps the source section titles that are missing from the target article,
                    to the corresponding proposed target section titles of the section translation recommendation""",
    )


class TranslationRecommendationCandidate(TranslationRecommendation):
    languages: Optional[list[str]] = None
