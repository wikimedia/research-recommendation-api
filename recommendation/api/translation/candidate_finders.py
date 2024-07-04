import random
from typing import List

from recommendation.api.translation import models
from recommendation.external_data import fetcher
from recommendation.utils.logger import log


async def get_top_pageview_candidates(
    source: str, _, filter_language: str
) -> List[models.TranslationRecommendationCandidate]:
    """
    Retrieves the top pageview candidates based on the given source and filter language.

    Args:
        source (str): The source of the articles.
        count (int): The number of top candidates to retrieve.
        filter_language (str): The language to filter the articles.

    Returns:
        list: A list of TranslationRecommendationCandidate objects representing the top pageview candidates.
    """
    articles = await fetcher.get_most_popular_articles(source, filter_language)

    # shuffle articles
    articles = sorted(articles, key=lambda x: random.random())

    recommendations = []

    for index, article in enumerate(articles):
        if "disambiguation" not in article.get("pageprops", {}):
            languages = [langlink["lang"] for langlink in article.get("langlinks", [])]
            rec = models.TranslationRecommendationCandidate(
                title=article.get("title"),
                rank=index,
                langlinks_count=int(article.get("langlinkscount", 0)),
                languages=languages,
                wikidata_id=article.get("pageprops", {}).get("wikibase_item"),
            )
            recommendations.append(rec)

    return recommendations


async def get_morelike_candidates(
    source: str, seeds: str, filter_language: str = None
) -> List[models.TranslationRecommendation]:
    """
    Retrieves translation recommendation candidates based on the given source and seeds.

    Args:
        source (str): The source language.
        seeds (str): The seed text used for finding similar articles.
        filter_language (str, optional): The language to filter the results. Defaults to None.

    Returns:
        List[models.TranslationRecommendation]: A list of translation recommendation candidates.

    """
    results = await fetcher.wiki_search(
        source,
        seeds,
        morelike=True,
        filter_language=filter_language,
        filter_disambiguation=True,
    )

    if len(results) == 0:
        log.debug(f"Seed {seeds} in {source} does not map to an article")
        return []

    recommendations = []

    for page in results:
        languages = [langlink["lang"] for langlink in page.get("langlinks", [])]
        rec = models.TranslationRecommendationCandidate(
            title=page["title"],
            rank=page["index"],
            langlinks_count=int(page.get("langlinkscount", 0)),
            languages=languages,
            wikidata_id=page.get("pageprops", {}).get("wikibase_item"),
        )

        recommendations.append(rec)

    return recommendations
