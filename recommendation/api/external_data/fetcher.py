import requests
import logging
import datetime
from multiprocessing import dummy as multiprocessing

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


def get_most_popular_articles(source, campaign=''):
    days = configuration.get_config_int('popular_pageviews', 'days')
    # For the WikiGapFinder campaign we may not have enough data for the
    # number of preconfigured days. So increase the number so that when
    # we filter out undesirable items we at least have some good
    # results:
    if campaign == 'WikiGapFinder':
        days = days * 2
    date_format = configuration.get_config_value('popular_pageviews', 'date_format')
    query = configuration.get_config_value('popular_pageviews', 'query')
    date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).strftime(date_format)
    query = query.format(source=source, date=date)
    try:
        data = get(query)
    except ValueError:
        log.info('pageview query failed')
        return []

    if 'items' not in data or len(data['items']) < 1 or 'articles' not in data['items'][0]:
        log.info('pageview data is not in a known format')
        return []

    articles = []

    for article in data['items'][0]['articles']:
        articles.append({'title': article['article'], 'pageviews': article['views']})

    return articles


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
    try:
        response = get(endpoint, dict(source=source, seed=seed, count=500))
    except ValueError:
        return []
    return response


def get_pages_in_category_tree(source, category, count):
    pages = set()
    seen_categories = set()
    current_categories = {category}
    while len(pages) < count:
        log.debug(len(pages))
        if not current_categories:
            break
        next_categories = set()
        with multiprocessing.Pool(processes=len(current_categories)) as pool:
            results = pool.map(lambda category: get_category_members(source, category), current_categories)
        for result in results:
            next_categories.update(result['subcats'])
            pages.update(result['pages'])
        seen_categories.update(current_categories)
        current_categories = next_categories - seen_categories
    log.debug(len(pages))
    return list(pages)


def get_category_members(source, category):
    log.debug(category)
    endpoint = configuration.get_config_value('endpoints', 'wikipedia').format(source=source)
    params = configuration.get_config_dict('category_search_params')
    params['cmtitle'] = category

    members = dict(pages=set(), subcats=set())

    try:
        response = get(endpoint, params=params)
    except ValueError:
        return []
    results = response.get('query', {}).get('categorymembers', [])
    for member in results:
        if member.get('type', None) == 'page':
            members['pages'].add(member.get('title'))
        if member.get('type', None) == 'subcat':
            members['subcats'].add(member.get('title'))
    return members
