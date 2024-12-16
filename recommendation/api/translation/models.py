import asyncio
from enum import Enum
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
from typing_extensions import Self


class WikiPage(BaseModel):
    id: Optional[int] = Field(default=None, description="Unique identifier for the wiki page")
    title: str = Field(..., description="Title of the wiki page", frozen=True)
    revision_id: Optional[int] = Field(default=None, description="Revision identifier for the wiki page")
    namespace: Optional[int] = Field(default=0, description="Namespace of the wiki page")
    language: str = Field(..., description="Language code of the wiki page", frozen=True)
    wiki: Optional[str] = Field(default=None, description="Wiki project code")
    qid: Optional[str] = Field(default=None, description="Wikidata identifier")

    @computed_field
    @property
    def key(self) -> str:
        return f"{self.language}:{self.id}:{self.revision_id}"

    def __hash__(self) -> int:
        return hash(self.key)


class WikiDataArticle(BaseModel):
    wikidata_id: str
    langlinks: Dict[str, str]

    def __hash__(self) -> int:
        return hash(self.wikidata_id)


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
    collections: bool = Field(
        description="Whether to fetch recommendations from page collections",
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


class PageCollectionMetadata(BaseModel):
    name: str
    description: Optional[str] = None
    end_date: Optional[str] = None
    articles_count: Optional[int] = None
    articles_by_language_count: Optional[Dict] = None

    def __hash__(self) -> int:
        return hash(self.name)


class TranslationRecommendation(BaseModel):
    title: str
    pageviews: Optional[int] = 0
    wikidata_id: Optional[str] = None
    rank: Optional[float] = 0.0
    langlinks_count: Optional[int] = 0
    collection: Optional[PageCollectionMetadata] = None

    def __hash__(self) -> int:
        return hash(self.wikidata_id)


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
    collection: Optional[PageCollectionMetadata] = Field(
        description="""An optional PageCollectionMetadata DTO, used for section translation recommendations
                    from page collections""",
        default=None,
    )


class TranslationRecommendationCandidate(TranslationRecommendation):
    languages: Optional[list[str]] = None


class PageCollection(BaseModel):
    name: str = Field(
        ...,
        description="Name of the page collection",
        frozen=True,
    )
    pages: Set[WikiPage] = Field(
        default=set(),
        description="Set of WikiPage objects associated with the page collection",
    )
    articles: Set[WikiDataArticle] = Field(
        default=set(),
        description="Set of articles that are part of this page collection",
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of the page collection",
    )
    end_date: Optional[str] = Field(
        default=None,
        description="End date of the page collection",
    )

    def __str__(self) -> str:
        return f"{self.name} ({len(self.articles)} articles)"

    async def fetch_articles(self):
        # This import is here to avoid circular imports
        from recommendation.external_data import fetcher

        tasks = [fetcher.get_candidates_in_collection_page(page) for page in self.pages]
        results = await asyncio.gather(*tasks)

        for candidates in results:
            self.articles.update(candidates)

    @computed_field
    @property
    def cache_key(self) -> str:
        # sort page keys alphabetically, so that cache_key doesn't change with page order
        page_keys = sorted([page.key for page in self.pages])
        # Cache key will depend on revision id of all pages where this page-collection applies
        # So when any of the pages are updated, the cache will be invalidated
        return "-".join(page_keys)

    @computed_field
    @property
    def articles_count(self) -> int:
        return len(self.articles)

    def articles_in_language_count(self, language) -> int:
        return sum(1 for article in self.articles if any(language in key for key in article.langlinks))

    def get_metadata(self, target_language) -> PageCollectionMetadata:
        return PageCollectionMetadata(
            name=self.name,
            description=self.description,
            end_date=self.end_date,
            articles_count=self.articles_count,
            articles_by_language_count={target_language: self.articles_in_language_count(target_language)},
        )

    def __hash__(self) -> int:
        return hash(self.cache_key)


class PageCollectionResponse(BaseModel):
    name: str
    description: Optional[str] = None
    end_date: Optional[str] = None
    articles_count: int


class PageCollectionsList(BaseModel):
    list: Set[PageCollection] = set()

    def add(self, collection: PageCollection):
        self.list.add(collection)
