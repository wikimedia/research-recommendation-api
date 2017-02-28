import logging
import random

from recommendation.api.external_data import fetcher
from recommendation.api.types.translation import recommendation

log = logging.getLogger(__name__)


def get_top_pageview_candidates(source, _, count):
    articles = fetcher.get_most_popular_articles(source)

    # shuffle articles
    articles = sorted(articles, key=lambda x: random.random())

    recommendations = []

    for index, article in enumerate(articles):
        rec = recommendation.Recommendation(article['title'])
        rec.rank = index
        rec.pageviews = article['pageviews']
        recommendations.append(rec)

    return recommendations[:count]


def get_morelike_candidates(source, seed, count):
    seed_list = fetcher.wiki_search(source, seed, 1)

    if len(seed_list) == 0:
        log.info('seed does not map to an article')
        return []
    if seed != seed_list[0]:
        log.debug('seed parameter of %s mapped to article %s', seed, seed_list[0])

    results = fetcher.wiki_search(source, seed_list[0], count, morelike=True)
    if results:
        results.insert(0, seed_list[0])
        log.info('morelike returned %d results', len(results))
    else:
        log.info('morelike search failed; reverting to standard search')
        results = fetcher.wiki_search(source, seed, count)

    recommendations = []

    for index, title in enumerate(results):
        rec = recommendation.Recommendation(title)
        rec.rank = index
        recommendations.append(rec)

    return recommendations[:count]


def get_related_articles(source, seed, count):
    results = fetcher.get_related_articles(source, seed)
    if len(results) == 0:
        log.info('Failed related_articles search. Reverting to morelike. Source: %s Seed: %s', source, seed)
        return get_morelike_candidates(source, seed, count)

    recommendations = []
    for item in results:
        rec = recommendation.Recommendation(item['title'])
        rec.wikidata_id = item['wikidata_id']
        rec.rank = item['score']
        recommendations.append(rec)

    return recommendations[:count]


def get_category_candidates(source, seed, count):
    results = fetcher.get_pages_in_category_tree(source, seed, count)
    if len(results) == 0:
        log.info('Failed category search. Source: %s Seed: %s', source, seed)
        return []

    recommendations = []
    for title in results:
        rec = recommendation.Recommendation(title)
        rec.rank = 0
        recommendations.append(rec)

    return recommendations
