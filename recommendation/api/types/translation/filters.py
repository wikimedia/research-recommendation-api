import logging

from recommendation.api.external_data import fetcher
from recommendation.api.external_data import wikidata
from recommendation.utils import logger

log = logging.getLogger(__name__)


@logger.timeit
def filter_by_missing(source, target, candidates):
    """
    Filters out which articles from source already exist in target
    using Wikidata sitelinks
    """
    titles = [article.title for article in candidates]
    titles_to_items = wikidata.get_items_in_source_missing_in_target_by_titles(
        source, target, titles
    )

    filtered_articles = []

    for article in candidates:
        if article.title in titles_to_items:
            # TODO: change this side-effect to be more explicit / non-stateful
            article.incorporate_wikidata_item(titles_to_items[article.title])
            filtered_articles.append(article)

    return filtered_articles


@logger.timeit
def filter_by_disambiguation(source, candidates):
    """
    Filters out disambiguation pages
    """
    titles = [article.title for article in candidates]
    disambiguation_pages = fetcher.get_disambiguation_pages(source, titles)
    return [
        article for article in candidates if article.title not in disambiguation_pages
    ]


@logger.timeit
def filter_by_title(candidates):
    """
    Filters articles based on the properties of the title
    """
    return [
        article
        for article in candidates
        if ":" not in article.title and not article.title.startswith("List")
    ]


@logger.timeit
def filter_by_campaign(source, target, candidates, campaign=""):
    """TODO: Think about moving the hardcoded items to a configuration file."""
    if campaign == "WikiGapFinder":
        wikidata_ids = [article.wikidata_id for article in candidates]
        campaign_candidates = wikidata.get_wikigapfinder_campaign_candidates(
            source, target, wikidata_ids
        )
        ids_of_campaign_candidates = {x.id for x in campaign_candidates}
        return [x for x in candidates if x.wikidata_id in ids_of_campaign_candidates]
    return candidates


@logger.timeit
def apply_filters(source, target, candidates, campaign):
    log.debug("Number of candidates: %d", len(candidates))
    candidates = filter_by_title(candidates)
    log.debug("Number of candidates after title: %d", len(candidates))
    candidates = filter_by_missing(source, target, candidates)
    log.debug("Number of candidates after missing: %d", len(candidates))
    candidates = filter_by_disambiguation(source, candidates)
    log.debug("Number of candidates after disambiguation: %d", len(candidates))
    candidates = filter_by_campaign(source, target, candidates, campaign)
    log.debug("Number of candidates after campaign: %d", len(candidates))
    return candidates
