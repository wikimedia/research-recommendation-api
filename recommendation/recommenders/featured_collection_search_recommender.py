from typing import Dict, List, Optional

from recommendation.api.translation.models import (
    PageCollection,
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.cache import get_page_collection_cache
from recommendation.external_data.fetcher import (
    get_wikipedia_page_ids,
)
from recommendation.recommenders.base_recommender import BaseRecommender
from recommendation.recommenders.search_recommender import SearchRecommender
from recommendation.utils.recommendation_helper import (
    interleave_by_ratio,
)


class FeaturedCollectionSearchRecommender(BaseRecommender):
    """Decorator recommender that augments a SearchRecommender with featured-collection suggestions.

    This class wraps a SearchRecommender instance and, when a featured_collection is
    requested, fetches pages from that collection and interleaves them with the base
    search recommendations.
    """

    def __init__(self, request_model: TranslationRecommendationRequest):
        self.base = SearchRecommender(request_model)
        self.source_language = request_model.source
        self.target_language = request_model.target
        self.count = request_model.count
        self.min_size = request_model.min_size
        self.max_size = request_model.max_size
        self.lead_section = request_model.lead_section
        self.featured_collection = request_model.featured_collection

    def match(self) -> bool:
        return self.base.match() and bool(self.featured_collection)

    def post_section_suggestions_hook(
        self,
        candidates: List[TranslationRecommendation],
        section_recommendations: List[SectionTranslationRecommendation],
    ) -> List[SectionTranslationRecommendation]:
        # Reorders the section recommendations, so that elements with a `collection` value and
        # elements without one are arranged in an alternating pattern (with → none → with → none).
        # If one category runs out before the other, the remaining items are appended while
        # preserving the alternation as much as possible.
        recs_with_collection = [rec for rec in section_recommendations if rec.collection is not None]
        recs_without_collection = [rec for rec in section_recommendations if rec.collection is None]

        result = []
        i = 0

        # Alternate between the two lists
        while recs_with_collection or recs_without_collection:
            if i % 2 == 0:  # even index → needs item *with collection*
                if recs_with_collection:
                    result.append(recs_with_collection.pop(0))
                elif recs_without_collection:  # fallback if impossible
                    result.append(recs_without_collection.pop(0))
            else:  # odd index → needs item *without collection*
                if recs_without_collection:
                    result.append(recs_without_collection.pop(0))
                elif recs_with_collection:
                    result.append(recs_with_collection.pop(0))
            i += 1

        return result

    async def get_recommendations_by_status(self, missing: bool) -> List[TranslationRecommendation]:
        base_recs = await self.base.get_recommendations_by_status(missing)
        # Build featured recommendations
        featured_queries = await self.get_featured_collection_query_properties(
            self.base.get_search_query_properties()[0]
        )

        featured_pages: List[Dict] = []
        featured_page_collection: Optional[PageCollection] = self.get_featured_collection()

        for query in featured_queries:
            pages = await self.base.fetch_search_results(query, None)
            featured_pages.extend(pages)

        featured_pages = self.base.filter_by_missing_status(featured_pages, missing)

        featured_recommendations: List[TranslationRecommendation] = [
            TranslationRecommendation(
                title=page["title"],
                langlinks_count=int(page.get("langlinkscount", 0)),
                size=page.get("size", 0),
                lead_section_size=page.get("lead_section_size", None),
                wikidata_id=page.get("pageprops", {}).get("wikibase_item"),
                collection=featured_page_collection.get_metadata(self.base.target_language)
                if featured_page_collection
                else None,
            )
            for page in featured_pages
        ]

        # Interleave base and featured by existing helper
        return interleave_by_ratio(base_recs, featured_recommendations)

    def get_featured_collection(self) -> Optional[PageCollection]:
        page_collection_cache = get_page_collection_cache()
        page_collections: List[PageCollection] = page_collection_cache.get_page_collections()
        for collection in page_collections:
            if collection.name.casefold() == self.featured_collection.casefold():
                return collection
        return None

    @staticmethod
    def build_batched_queries_for_featured_collection_pages(
        base_query: str, page_ids: List[int], max_length: int = 4096
    ) -> List[str]:
        batched_queries = []
        current_batch = []
        current_length = len(base_query)

        for pid in map(str, page_ids):
            additional_length = len(pid) + (1 if current_batch else 0)

            if current_length + additional_length > max_length:
                batched_queries.append(base_query + "|".join(current_batch))
                current_batch = [pid]
                current_length = len(base_query) + len(pid)
            else:
                current_batch.append(pid)
                current_length += additional_length

        if current_batch:
            batched_queries.append(base_query + "|".join(current_batch))

        return batched_queries

    async def get_featured_collection_query_properties(self, base_search_query: str) -> List[str]:
        """Return one or more gsrsearch strings that restrict results to the pages in the featured collection.

        Example return values: ["articletopic:music pageid:123|456|789", "articletopic:food-and-drink pageid:987|..."]
        """
        asked_collection = self.get_featured_collection()
        batched_queries: List[str] = []
        if not asked_collection:
            return batched_queries

        cached_page_ids = [
            wikidata_article.page_ids.get(self.base.source_language)
            for wikidata_article in asked_collection.articles
            if wikidata_article.langlinks.get(self.base.source_language) is not None
            and wikidata_article.page_ids.get(self.base.source_language) is not None
        ]

        titles_without_page_ids = [
            wikidata_article.langlinks.get(self.base.source_language)
            for wikidata_article in asked_collection.articles
            if wikidata_article.page_ids.get(self.base.source_language) is not None
            and wikidata_article.page_ids.get(self.base.source_language) is None
        ]

        response = await get_wikipedia_page_ids(self.base.source_language, titles_without_page_ids)
        page_ids = cached_page_ids + list(response.values())

        # Compose base query and batch
        base_query = (base_search_query + " " if base_search_query else "") + "pageid:"
        batched_queries = self.build_batched_queries_for_featured_collection_pages(base_query, page_ids)

        return batched_queries
