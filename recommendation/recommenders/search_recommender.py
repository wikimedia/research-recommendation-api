from typing import Dict, List, Optional

from recommendation.api.translation.models import (
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.external_data.fetcher import get, get_endpoint_and_headers
from recommendation.recommenders.base_recommender import BaseRecommender
from recommendation.utils.language_pairs import get_language_to_domain_mapping, is_missing_in_target_language
from recommendation.utils.lead_section_size_helper import (
    add_lead_section_sizes_to_recommendations,
    get_limited_lead_section_sizes,
)
from recommendation.utils.logger import log
from recommendation.utils.recommendation_helper import sort_recommendations
from recommendation.utils.search_query_builder import build_search_query
from recommendation.utils.section_recommendation_helper import get_section_suggestions_for_recommendations
from recommendation.utils.size_helper import matches_article_size_filter, matches_section_size_filter


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

    async def recommend(self) -> List[TranslationRecommendation]:
        """
        Retrieves translation recommendation candidates based on the request source/target languages, topics and seeds.

        Returns:
            List[TranslationRecommendation]: A list of translation recommendations.
        """
        recommendations = await self.get_recommendations_by_status(True, self.min_size, self.max_size)
        recommendations = recommendations[: self.count]

        if not self.lead_section:
            recommendations = await add_lead_section_sizes_to_recommendations(recommendations, self.source_language)

        return recommendations

    async def recommend_sections(self) -> List[SectionTranslationRecommendation]:
        """
        Retrieves section translation recommendation candidates,
        based on the request source/target languages, topics and seeds.

        Returns:
            List[SectionTranslationRecommendation]: A list of section translation recommendations.
        """
        recommendations = await self.get_recommendations_by_status(False, None, None)

        return await get_section_suggestions_for_recommendations(
            recommendations, self.source_language, self.target_language, self.count, self.min_size, self.max_size
        )

    async def get_recommendations_by_status(
        self, missing: bool, min_size: Optional[int], max_size: Optional[int]
    ) -> List[TranslationRecommendation]:
        results = await self.search_wiki()

        if len(results) == 0:
            log.debug(f"Recommendation request {self.debug_request_params} does not map to an article")
            return []

        # Store initial index as rank, because the index can change after filtering
        # start=1, so that the rank begins at 1
        for index, page in enumerate(results, start=1):
            page["rank"] = index

        # Filter out articles with "disambiguation" page prop
        results = [page for page in results if "disambiguation" not in page.get("pageprops", {})]

        # Filter out based on "missing" status
        results = [
            page
            for page in results
            if missing
            == is_missing_in_target_language(
                self.target_language, [langlink["lang"] for langlink in page.get("langlinks", [])]
            )
        ]

        # Filter by size
        if not self.lead_section:
            results = [page for page in results if matches_article_size_filter(page.get("size", 0), min_size, max_size)]
        else:

            def filter_by_lead_section_size(lead_section_size: Dict[str, int]) -> bool:
                return matches_section_size_filter(lead_section_size, min_size, max_size)

            lead_section_sizes = await get_limited_lead_section_sizes(
                results, self.source_language, self.count, filter_by_lead_section_size
            )
            flat_lead_section_sizes = {
                list(size_info.keys())[0]: list(size_info.values())[0] for size_info in lead_section_sizes
            }
            results = [
                {**page, "lead_section_size": flat_lead_section_sizes[page.get("title")]}
                for page in results
                if page.get("title") in flat_lead_section_sizes
            ]

        recommendations = []
        for page in results:
            rec = TranslationRecommendation(
                title=page["title"],
                rank=page.get("rank", page["index"]),
                langlinks_count=int(page.get("langlinkscount", 0)),
                size=page.get("size", 0),
                lead_section_size=page.get("lead_section_size", None),
                wikidata_id=page.get("pageprops", {}).get("wikibase_item"),
            )
            recommendations.append(rec)

        return sort_recommendations(recommendations, self.rank_method)

    async def search_wiki(self):
        """
        This method sends a request to the source Wikipedia API, to fetch the related pages based on the
        request parameters.

        Returns:
            list: A list of pages that match the search query.
        """
        endpoint, params, headers = self.build_wiki_search()

        try:
            response = await get(endpoint, params=params, headers=headers)
        except ValueError:
            log.error(
                f"Could not search for articles related to search {self.debug_request_params}. Choose another language."
            )
            return []

        if "query" not in response or "pages" not in response["query"]:
            log.debug(f"Recommendation request {self.debug_request_params} does not map to an article")
            return []

        pages = response["query"]["pages"]

        if len(pages) == 0:
            log.debug(f"Recommendation request {self.debug_request_params} does not map to an article")
            return []

        return pages

    def build_wiki_search(self):
        """
        Builds the parameters and headers required for making a Wikipedia search API request.

        Returns:
            tuple: A tuple containing the endpoint URL, parameters, and headers for the API request.
        """
        endpoint, headers = get_endpoint_and_headers(self.source_language)

        # langlinks filtering uses the domain code when it differs from the language code
        lllang = get_language_to_domain_mapping().get(self.target_language, self.target_language)
        params = {
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

        gsrsearch_query = []

        if self.topic:
            params["gsrsort"] = "random"
            topics = self.topic.replace(" ", "-").lower()
            search_expression = build_search_query("articletopic", topics)
            if search_expression:
                gsrsearch_query.append(search_expression)

        if self.country:
            params["gsrsort"] = "random"
            search_expression = build_search_query("articlecountry", self.country)
            if search_expression:
                gsrsearch_query.append(search_expression)

        if self.seed:
            # morelike is a "greedy" keyword, meaning that it cannot be combined with other search queries.
            # To use other search queries, use morelikethis in your search:
            # https://www.mediawiki.org/wiki/Help:CirrusSearch#morelike
            if len(gsrsearch_query):
                gsrsearch_query.append(f"morelikethis:{self.seed}")
            else:
                gsrsearch_query.append(f"morelike:{self.seed}")

        params["gsrsearch"] = " ".join(gsrsearch_query)

        log.debug(f"Search params: {params}")
        return endpoint, params, headers
