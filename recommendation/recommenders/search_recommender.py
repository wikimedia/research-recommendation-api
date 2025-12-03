from typing import Dict, List, Optional, Tuple

from recommendation.api.translation.models import (
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.external_data.fetcher import get, get_endpoint_and_headers
from recommendation.recommenders.base_recommender import BaseRecommender
from recommendation.utils.language_codes import get_language_to_domain_mapping, is_missing_in_target_language
from recommendation.utils.logger import log
from recommendation.utils.recommendation_helper import sort_recommendations
from recommendation.utils.search_query_builder import build_search_query


class SearchRecommender(BaseRecommender):
    def __init__(self, request_model: TranslationRecommendationRequest):
        self.source_language = request_model.source
        self.target_language = request_model.target
        self.seed = request_model.seed
        self.topic = request_model.topic
        self.country = request_model.country
        self.count = request_model.count
        self.rank_method = request_model.rank_method
        self.include_pageviews = request_model.include_pageviews
        self.min_size = request_model.min_size
        self.max_size = request_model.max_size
        self.lead_section = request_model.lead_section

    @property
    def debug_request_params(self) -> Dict:
        return {
            "source_language": self.source_language,
            "target_language": self.target_language,
            "seed": self.seed,
            "topic": self.topic,
            "country": self.country,
            "count": self.count,
            "rank_method": self.rank_method,
            "include_pageviews": self.include_pageviews,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "lead_section": self.lead_section,
        }

    def match(self) -> bool:
        return bool(self.topic or self.seed or self.country)

    async def get_recommendations_by_status(self, missing: bool) -> List[TranslationRecommendation]:
        base_search_query, gsrsort = self.get_search_query_properties()
        pages = await self.fetch_search_results(base_search_query, gsrsort)

        if len(pages) == 0:
            log.debug(f"Recommendation request {self.debug_request_params} does not map to an article")
            return []

        # Store initial index as rank, because the index can change after filtering
        # start=1, so that the rank begins at 1
        for index, page in enumerate(pages, start=1):
            page["rank"] = index

        pages = self.filter_by_missing_status(pages, missing)
        recs = [
            TranslationRecommendation(
                title=page["title"],
                rank=page.get("rank", page.get("index")),
                langlinks_count=int(page.get("langlinkscount", 0)),
                size=page.get("size", 0),
                lead_section_size=page.get("lead_section_size", None),
                wikidata_id=page.get("pageprops", {}).get("wikibase_item"),
            )
            for page in pages
        ]

        return sort_recommendations(recs, self.rank_method)

    def filter_by_missing_status(self, pages: List[Dict], missing: bool) -> List[Dict]:
        # Filter out based on "missing" status
        return [
            page
            for page in pages
            if missing
            == is_missing_in_target_language(
                self.target_language, [langlink["lang"] for langlink in page.get("langlinks", [])]
            )
        ]

    def get_base_search_payload(self) -> Dict:
        """Construct common search payload used by fetch_search_results."""
        lllang = get_language_to_domain_mapping().get(self.target_language, self.target_language)

        return {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "langlinks|langlinkscount|pageprops",
            "lllimit": "max",
            "lllang": lllang,
            "generator": "search",
            "gsrprop": "size",
            "gsrnamespace": 0,
            "gsrwhat": "text",
            "gsrlimit": "max",
            "ppprop": "wikibase_item|disambiguation",
            "gsrqiprofile": "classic_noboostlinks",
        }

    def get_search_query_properties(self) -> Tuple[str, Optional[str]]:
        """Build the base search query string and optional sort order."""
        base_search_query_strings = []
        gsrsort = None
        if self.topic:
            gsrsort = "random"
            topics = self.topic.replace(" ", "-").lower()
            search_expression = build_search_query("articletopic", topics)
            if search_expression:
                base_search_query_strings.append(search_expression)

        if self.country:
            gsrsort = "random"
            search_expression = build_search_query("articlecountry", self.country)
            if search_expression:
                base_search_query_strings.append(search_expression)

        if self.seed:
            # morelike is a "greedy" keyword, meaning that it cannot be combined with other search queries.
            # To use other search queries, use morelikethis in your search:
            # https://www.mediawiki.org/wiki/Help:CirrusSearch#morelike
            if len(base_search_query_strings):
                base_search_query_strings.append(f"morelikethis:{self.seed}")
            else:
                base_search_query_strings.append(f"morelike:{self.seed}")

        base_search_query = " ".join(base_search_query_strings)
        return base_search_query, gsrsort

    async def fetch_search_results(self, query: str, gsrsort: Optional[str]) -> List[Dict]:
        """Execute the Wikipedia search API request and return filtered pages."""
        endpoint, headers = get_endpoint_and_headers(self.source_language)
        base_params = self.get_base_search_payload()

        params = {**base_params, "gsrsearch": query}
        if gsrsort:
            params["gsrsort"] = gsrsort

        log.debug(f"Sending search query {params}")
        try:
            response = await get(endpoint, params=params, headers=headers)
        except ValueError:
            log.error(f"Could not search for articles related to search {self.debug_request_params}.")
            return []

        if "query" not in response or "pages" not in response["query"]:
            log.debug(f"Search query '{query}' returned no pages.")
            return []

        pages = response["query"]["pages"]
        if not pages:
            log.debug(f"Search query '{query}' returned empty pages.")
            return []

        # Filter out `disambiguation` pages
        pages = [page for page in pages if "disambiguation" not in page.get("pageprops", {})]

        return pages
