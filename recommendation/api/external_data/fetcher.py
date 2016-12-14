import requests
import logging
import datetime

from recommendation.utils import configuration

log = logging.getLogger(__name__)


def get(url, params=None):
    log.debug('Get: %s', url)
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        log.info('Request failed: {"url": "%s", "error": "%s"}', url, e)
        raise ValueError(e)


def post(url, data=None):
    log.debug('Post: %s', url)
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        log.info('Request failed: {"url": "%s", "error": "%s"}', url, e)
        raise ValueError(e)


def get_disambiguation_pages(source, titles):
    """
    Returns the subset of titles that are disambiguation pages
    """
    endpoint = configuration.get_config_value('endpoints', 'wikipedia').format(source=source)
    params = configuration.get_config_dict('disambiguation_params')
    params['titles'] = '|'.join(titles)

    try:
        data = post(endpoint, data=params)
    except ValueError:
        log.info('Bad Disambiguation API response')
        return []

    pages = data.get('query', {}).get('pages', {}).values()
    return list(set(page['title'].replace(' ', '_') for page in pages if 'disambiguation' in page.get('pageprops', {})))


def get_pageviews(source, title):
    """
    Get pageview counts for a single article from pageview api
    """
    query = get_pageview_query_url(source, title)

    try:
        response = get(query)
    except ValueError:
        response = {}

    return sum(item['views'] for item in response.get('items', {}))


def get_pageview_query_url(source, title):
    start_days = configuration.get_config_int('single_article_pageviews', 'start_days')
    end_days = configuration.get_config_int('single_article_pageviews', 'end_days')
    query = configuration.get_config_value('single_article_pageviews', 'query')
    start = get_relative_timestamp(start_days)
    end = get_relative_timestamp(end_days)
    query = query.format(source=source, title=title, start=start, end=end)
    return query


def get_relative_timestamp(relative_days):
    date_format = configuration.get_config_value('single_article_pageviews', 'date_format')
    return (datetime.datetime.utcnow() + datetime.timedelta(days=relative_days)).strftime(date_format)


def wiki_search(source, seed, count, morelike=False):
    """
    A client to the Mediawiki search API
    """
    endpoint, params = build_wiki_search(source, seed, count, morelike)
    try:
        response = get(endpoint, params=params)
    except ValueError:
        log.info('Could not search for articles related to seed in %s. Choose another language.', source)
        return []

    if 'query' not in response or 'search' not in response['query']:
        log.info('Could not search for articles related to seed in %s. Choose another language.', source)
        return []

    response = response['query']['search']
    results = [r['title'].replace(' ', '_') for r in response]
    if len(results) == 0:
        log.info('No articles similar to %s in %s. Try another seed.', seed, source)
        return []

    return results


def build_wiki_search(source, seed, count, morelike):
    endpoint = configuration.get_config_value('endpoints', 'wikipedia').format(source=source)
    params = configuration.get_config_dict('wiki_search_params')
    params['srlimit'] = count
    if morelike:
        seed = 'morelike:' + seed
    params['srsearch'] = seed
    return endpoint, params


def get_related_articles(source, seed):
    endpoint = configuration.get_config_value('endpoints', 'related_articles')
    return get(endpoint, dict(source=source, seed=seed, count=500))
