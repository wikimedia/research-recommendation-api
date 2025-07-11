from typing import List

from recommendation.api.translation.models import (
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.external_data.fetcher import get, get_formatted_endpoint, set_headers_with_host_header
from recommendation.recommenders.base_recommender import BaseRecommender
from recommendation.utils.configuration import configuration
from recommendation.utils.language_pairs import get_language_to_domain_mapping, is_missing_in_target_language
from recommendation.utils.logger import log
from recommendation.utils.recommendation_helper import sort_recommendations
from recommendation.utils.section_recommendation_helper import get_section_suggestions_for_recommendations


class PopularRecommender(BaseRecommender):
    def __init__(self, request_model: TranslationRecommendationRequest):
        self.source_language = request_model.source
        self.target_language = request_model.target
        self.count = request_model.count
        self.rank_method = request_model.rank_method

    def match(self) -> bool:
        return True

    async def recommend(self) -> List[TranslationRecommendation]:
        recommendations = await self.get_recommendations_by_status(missing=True)
        recommendations = recommendations[: self.count]

        return recommendations

    async def recommend_sections(self) -> List[SectionTranslationRecommendation]:
        recommendations = await self.get_recommendations_by_status(missing=False)

        return await get_section_suggestions_for_recommendations(
            recommendations, self.source_language, self.target_language, self.count
        )

    async def get_recommendations_by_status(self, missing=True) -> List[TranslationRecommendation]:
        """
        Retrieves the top pageview candidates based on the given source and target language, and the
        given present/missing status - as indicated by the "missing" argument.

        Args:
            missing: A boolean indicating whether we need to return present or missing recommendations.

        Returns:
            list: A list of TranslationRecommendation objects representing the top pageview candidates.
        """
        articles = await self.fetch_most_popular_articles()

        recommendations = []

        for index, article in enumerate(articles):
            if "disambiguation" not in article.get("pageprops", {}):
                languages = [langlink["lang"] for langlink in article.get("langlinks", [])]
                if missing == is_missing_in_target_language(self.target_language, languages):
                    rec = TranslationRecommendation(
                        title=article.get("title"),
                        rank=index,
                        langlinks_count=int(article.get("langlinkscount", 0)),
                        wikidata_id=article.get("pageprops", {}).get("wikibase_item"),
                    )
                    recommendations.append(rec)

        return sort_recommendations(recommendations, self.rank_method)

    async def fetch_most_popular_articles(self):
        endpoint = get_formatted_endpoint(configuration.WIKIPEDIA_API, self.source_language)
        headers = set_headers_with_host_header(configuration.WIKIPEDIA_API_HEADER, self.source_language)
        # langlinks filtering uses the domain code when it differs from the language code
        lllang = get_language_to_domain_mapping().get(self.target_language, self.target_language)
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "langlinks|langlinkscount|pageprops",
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
