import random
from typing import List

from recommendation.api.translation.models import (
    TranslationRecommendation,
    TranslationRecommendationCandidate,
    TranslationRecommendationRequest,
    WikiDataArticle,
)
from recommendation.external_data import fetcher
from recommendation.utils.logger import log


async def get_top_pageview_candidates(
    rec_req_model: TranslationRecommendationRequest,
) -> List[TranslationRecommendationCandidate]:
    """
    Retrieves the top pageview candidates based on the given source and filter language.

    Args:
        rec_req_model (TranslationRecommendationRequest): The translation recommendation request model.

    Returns:
        list: A list of TranslationRecommendationCandidate objects representing the top pageview candidates.
    """
    articles = await fetcher.get_most_popular_articles(rec_req_model.source, rec_req_model.target)

    # shuffle articles
    articles = sorted(articles, key=lambda x: random.random())

    recommendations = []

    for index, article in enumerate(articles):
        if "disambiguation" not in article.get("pageprops", {}):
            languages = [langlink["lang"] for langlink in article.get("langlinks", [])]
            rec = TranslationRecommendationCandidate(
                title=article.get("title"),
                rank=index,
                langlinks_count=int(article.get("langlinkscount", 0)),
                languages=languages,
                wikidata_id=article.get("pageprops", {}).get("wikibase_item"),
            )
            recommendations.append(rec)

    return recommendations


async def get_candidates_by_search(
    rec_req_model: TranslationRecommendationRequest,
) -> List[TranslationRecommendation]:
    """
    Retrieves translation recommendation candidates based on the given source and seeds.

    Args:
        rec_req_model (TranslationRecommendationRequest): The translation recommendation request model.

    Returns:
        List[TranslationRecommendation]: A list of translation recommendation candidates.

    """
    results = await fetcher.wiki_search(rec_req_model)

    if len(results) == 0:
        log.debug(f"Recommendation request {rec_req_model} does not map to an article")
        return []

    recommendations = []

    for page in results:
        languages = [langlink["lang"] for langlink in page.get("langlinks", [])]
        rec = TranslationRecommendationCandidate(
            title=page["title"],
            rank=page["index"],
            langlinks_count=int(page.get("langlinkscount", 0)),
            languages=languages,
            wikidata_id=page.get("pageprops", {}).get("wikibase_item"),
        )

        recommendations.append(rec)

    return recommendations


async def get_campaign_candidates(
    rec_req_model: TranslationRecommendationRequest,
) -> List[TranslationRecommendationCandidate]:
    """
    1. Find campaign pages marked with the translation campaign template
    2. Get article candidates for each campaign page
    """
    campaign_candidates = []
    campaign_pages = await fetcher.get_campaign_pages("meta")
    for page in campaign_pages:
        wikidata_articles: List[WikiDataArticle] = await fetcher.get_campaign_page_candidates(page, "meta")
        log.debug(f"Found {len(wikidata_articles)} articles for campaign {page}")
        for wikidata_article in wikidata_articles:
            candidate_source_article_title = wikidata_article.langlinks.get(rec_req_model.source)

            if candidate_source_article_title:
                campaign_candidate = TranslationRecommendationCandidate(
                    title=candidate_source_article_title,
                    wikidata_id=wikidata_article.wikidata_id,
                    langlinks_count=len(wikidata_article.langlinks),
                    languages=wikidata_article.langlinks.keys(),
                )
                campaign_candidates.append(campaign_candidate)

    return campaign_candidates
