import collections
import logging
import itertools
from multiprocessing import dummy as multiprocessing

from recommendation.utils import configuration
from recommendation.api.external_data import fetcher

log = logging.getLogger(__name__)

WikidataItem = collections.namedtuple('WikidataItem', ['id', 'title', 'url'])


def query(params, expected_sitelinks=1):
    """
    Query the wikidata endpoint and return a list of WikidataItem

     This only includes items that have exactly expected_sitelinks sitelink
    """
    endpoint = configuration.get_config_value('endpoints', 'wikidata')
    try:
        data = fetcher.post(endpoint, data=params)
        if 'warnings' in data:
            raise ValueError()
    except ValueError:
        log.info('Bad Wikidata API response')
        return {}

    entities = data.get('entities', {})

    items = []

    for id, entity in entities.items():
        sitelinks = entity.get('sitelinks', {})
        if len(sitelinks.keys()) != expected_sitelinks:
            continue
        sitelink = sitelinks.popitem()[1]

        item = WikidataItem(id=id,
                            title=sitelink['title'].replace(' ', '_'),
                            url=sitelink['url'])
        items.append(item)

    return items


def chunk_query_for_parameter(params, parameter, values):
    chunk_size = configuration.get_config_int('external_api_parameters', 'wikidata_chunk_size')

    param_groups = []
    for group in itertools.zip_longest(*[iter(values)] * chunk_size):
        p = params.copy()
        p[parameter] = '|'.join(item for item in group if item is not None)
        param_groups.append(p)

    if param_groups:
        with multiprocessing.Pool(processes=len(param_groups)) as pool:
            result = pool.map(query, param_groups)
        return list(itertools.chain(*result))
    else:
        return []


def get_items_in_source_missing_in_target_by_titles(source, target, titles):
    params = configuration.get_config_dict('wikidata_titles_to_items_params')
    params['sites'] = params['sites'].format(source=source)
    # We want the sitefilter to include both the source and target
    # wikis. This sets up the scenario where if there is only 1 sitelink
    # present, that means that the article is missing in the target (since
    # the title will have come from the source wiki)
    params['sitefilter'] = params['sitefilter'].format(target=target)
    params['sitefilter'] += '|{}wiki'.format(source)

    items = chunk_query_for_parameter(params, 'titles', titles)

    return {item.title: item.id for item in items}


def get_wikidata_items_from_titles(source, titles):
    params = configuration.get_config_dict('wikidata_titles_to_items_params')
    params['sites'] = params['sites'].format(source=source)
    params['sitefilter'] = params['sitefilter'].format(target=source)

    items = chunk_query_for_parameter(params, 'titles', titles)

    return items


def get_titles_from_wikidata_items(source, items):
    params = configuration.get_config_dict('wikidata_items_to_titles_params')
    params['sitefilter'] = params['sitefilter'].format(source=source)

    items = chunk_query_for_parameter(params, 'ids', items)

    return items
