from typing import Dict, List, Optional

from recommendation.api.translation.models import (
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.external_data.fetcher import get, get_formatted_endpoint, set_headers_with_host_header
from recommendation.recommenders.base_recommender import BaseRecommender
from recommendation.utils.configuration import configuration
from recommendation.utils.language_codes import get_language_to_domain_mapping, is_missing_in_target_language
from recommendation.utils.lead_section_size_helper import (
    add_lead_section_sizes_to_recommendations,
    get_limited_lead_section_sizes,
)
from recommendation.utils.logger import log
from recommendation.utils.recommendation_helper import sort_recommendations
from recommendation.utils.section_recommendation_helper import get_section_suggestions_for_recommendations
from recommendation.utils.size_helper import matches_article_size_filter, matches_section_size_filter


class PopularRecommender(BaseRecommender):
    def __init__(self, request_model: TranslationRecommendationRequest):
        self.source_language = request_model.source
        self.target_language = request_model.target
        self.count = request_model.count
        self.rank_method = request_model.rank_method
        self.min_size = request_model.min_size
        self.max_size = request_model.max_size
        self.lead_section = request_model.lead_section

    def match(self) -> bool:
        return True

    async def recommend(self) -> List[TranslationRecommendation]:
        recommendations = await self.get_recommendations_by_status(True, self.min_size, self.max_size)
        recommendations = recommendations[: self.count]

        if not self.lead_section:
            recommendations = await add_lead_section_sizes_to_recommendations(recommendations, self.source_language)

        return recommendations

    async def recommend_sections(self) -> List[SectionTranslationRecommendation]:
        recommendations = await self.get_recommendations_by_status(False, None, None)

        return await get_section_suggestions_for_recommendations(
            recommendations, self.source_language, self.target_language, self.count, self.min_size, self.max_size
        )

    async def get_recommendations_by_status(
        self, missing: bool, min_size: Optional[int], max_size: Optional[int]
    ) -> List[TranslationRecommendation]:
        """
        Retrieves the top pageview candidates based on the given source and target language, and the
        given present/missing status - as indicated by the "missing" argument.

        Args:
            missing: A boolean indicating whether we need to return present or missing recommendations.
            min_size: Minimum size in bytes to filter recommendations.
            max_size: Maximum size in bytes to filter recommendations.

        Returns:
            list: A list of TranslationRecommendation objects representing the top pageview candidates.
        """
        articles = await self.fetch_most_popular_articles()

        recommendations = []

        # store initial index as rank, because the index of each article inside the list can change after filtering
        # start=1, so that the rank begins at 1
        for index, article in enumerate(articles, start=1):
            article["rank"] = index

        # filter out articles with "disambiguation" page prop
        articles = [article for article in articles if "disambiguation" not in article.get("pageprops", {})]

        # filter out based on "missing" status
        articles = [
            article
            for article in articles
            if missing
            == is_missing_in_target_language(
                self.target_language, [langlink["lang"] for langlink in article.get("langlinks", [])]
            )
        ]

        # filter by size
        if not self.lead_section:
            articles = [
                article
                for article in articles
                if matches_article_size_filter(article.get("length", 0), min_size, max_size)
            ]
        else:

            def filter_by_lead_section_size(lead_section_size: Dict[str, int]) -> bool:
                return matches_section_size_filter(lead_section_size, min_size, max_size)

            lead_section_sizes = await get_limited_lead_section_sizes(
                articles, self.source_language, self.count, filter_by_lead_section_size
            )
            flat_lead_section_sizes = {
                list(size_info.keys())[0]: list(size_info.values())[0] for size_info in lead_section_sizes
            }
            articles = [
                {**article, "lead_section_size": flat_lead_section_sizes[article.get("title")]}
                for article in articles
                if article.get("title") in flat_lead_section_sizes
            ]

        log.debug(f"articles {articles} ")

        for article in articles:
            rec = TranslationRecommendation(
                title=article.get("title"),
                rank=article.get("rank"),
                langlinks_count=int(article.get("langlinkscount", 0)),
                size=article.get("length", 0),
                lead_section_size=article.get("lead_section_size", None),
                wikidata_id=article.get("pageprops", {}).get("wikibase_item"),
            )
            recommendations.append(rec)

        return sort_recommendations(recommendations, self.rank_method)

    async def fetch_most_popular_articles(self) -> List[Dict]:
        """
        Fetch the most popular articles from Wikipedia for a given source language.

        This method queries the MediaWiki API (`generator=mostviewed`) to retrieve
        the most viewed articles (based on last day's pageview count) in the specified
        source language. It requests metadata including language links, Wikidata item
        IDs, and disambiguation information, and filters the results to only include
        main namespace articles (ns = 0).

        Returns:
            List[Dict]:
                A list of article objects (dictionaries) representing the most viewed
                Wikipedia pages. Each dictionary corresponds to a page and contains keys such as:
                  - "title" (str): Title of the article
                  - "langlinks" (list[dict], optional): Cross-language links
                  - "langlinks_count" (int): Number of cross-language links
                  - "pageprops" (dict, optional): Page properties (e.g., Wikidata item ID, disambiguation)
                  - "length" (int): Article length in bytes
        """
        endpoint = get_formatted_endpoint(configuration.WIKIPEDIA_API, self.source_language)
        headers = set_headers_with_host_header(configuration.WIKIPEDIA_API_HEADER, self.source_language)
        # langlinks filtering uses the domain code when it differs from the language code
        lllang = get_language_to_domain_mapping().get(self.target_language, self.target_language)

        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "langlinks|langlinkscount|pageprops|info",
            "lllimit": "max",
            "lllang": lllang,
            "generator": "mostviewed",
            "gpvimlimit": "max",
            "ppprop": "wikibase_item|disambiguation",
        }

        try:
            data = await get(api_url=endpoint, params=params, headers=headers)
        except ValueError:
            log.info("pageview query failed")
            return []

        if "query" not in data or "pages" not in data["query"]:
            log.info("pageview data is not in a known format")
            return []

        # Filter for main namespace articles
        pages = [page for page in data["query"]["pages"] if page["ns"] == 0]
        return pages
