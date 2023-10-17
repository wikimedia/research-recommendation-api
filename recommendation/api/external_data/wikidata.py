import collections
import logging
import itertools
from multiprocessing import dummy as multiprocessing

from recommendation.utils import configuration
from recommendation.utils import logger
from recommendation.api.external_data import fetcher

log = logging.getLogger(__name__)

_RawWikidataItem = collections.namedtuple(
    "RawWikidataItem", ["id", "sitelinks", "claims"]
)
WikidataItem = collections.namedtuple(
    "WikidataItem", ["id", "title", "url", "sitelink_count"]
)


def wikigapfinder_campaign_filter(item):
    """People who are women or identify themselves as women"""
    return (
        item.claims.get("P31", [{}])[0]
        .get("mainsnak", {})
        .get("datavalue", {})
        .get("value", {})
        .get("id", "")
        == "Q5"
    ) and (
        item.claims.get("P21", [{}])[0]
        .get("mainsnak", {})
        .get("datavalue", {})
        .get("value", {})
        .get("id", "")
        in ("Q1052281", "Q6581072")
    )


@logger.timeit
def get_wikigapfinder_campaign_candidates(source, target, wikidata_ids):
    """Candidates for the WikiGapFinder campaign"""
    return get_items(
        source,
        ids=wikidata_ids,
        raw_filter=wikigapfinder_campaign_filter,
        props="claims|sitelinks/urls",
    )


@logger.timeit
def get_items_in_source_missing_in_target_by_titles(source, target, titles):
    target_wiki = f"{target}wiki"
    items = get_items(
        source, titles=titles, raw_filter=lambda item: target_wiki not in item.sitelinks
    )
    return {item.title: item for item in items}


@logger.timeit
def get_wikidata_items_from_titles(source, titles):
    return get_items(source, titles=titles)


@logger.timeit
def get_titles_from_wikidata_items(source, items):
    return get_items(source, ids=items)


def default_filter(_):
    return True


def get_items(source, titles=None, ids=None, raw_filter=default_filter, props=None):
    params = configuration.get_config_dict("wikidata_query_params")
    if props:
        params["props"] = props
    params["sites"] = params["sites"].format(source=source)
    items = []
    if titles is not None:
        items = chunk_query_for_parameter(params, "titles", titles)
    if ids is not None:
        items = chunk_query_for_parameter(params, "ids", ids)
    items = [
        extract_from_raw(item, params["sites"]) for item in items if raw_filter(item)
    ]
    items = [item for item in items if item is not None]
    return items


def chunk_query_for_parameter(params, parameter, values):
    """
    This takes in general params for a query that needs to be performed
     for a set of values, and then adds a specified parameter with the
     chunked values until all the values have been in a query.

     Ex:
        chunk_query_for_parameter(
            {'foo': 'bar'},
            'additional',
            ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'])

        results in the following queries if chunk_size is 3:

        query({'foo': 'bar',
               'additional': 'a|b|c'})
        query({'foo': 'bar',
               'additional': 'd|e|f'})
        query({'foo': 'bar',
               'additional': 'g|h|i'})
        query({'foo': 'bar',
               'additional': 'j'})

        the results are appended in the appropriate order and returned
    """
    chunk_size = configuration.get_config_int(
        "external_api_parameters", "wikidata_chunk_size"
    )

    param_groups = []
    for group in itertools.zip_longest(*[iter(values)] * chunk_size):
        p = params.copy()
        p[parameter] = "|".join(item for item in group if item is not None)
        param_groups.append(p)

    if param_groups:
        with multiprocessing.Pool(processes=len(param_groups)) as pool:
            result = pool.map(query, param_groups)
        return list(itertools.chain(*result))
    else:
        return []


def query(params):
    entities = get_entities(params)
    raw_items = get_raw_items_from_entities(entities)
    return raw_items


def get_entities(params):
    endpoint = configuration.get_config_value("endpoints", "wikidata")
    headers = fetcher.set_headers_with_host_header(configuration, "wikidata")

    try:
        data = fetcher.post(endpoint, data=params, headers=headers)
        if "warnings" in data:
            raise ValueError()
    except ValueError:
        log.info("Bad Wikidata API response")
        return {}

    return data.get("entities", {})


def get_raw_items_from_entities(entities):
    items = []
    for id, entity in entities.items():
        sitelinks = entity.get("sitelinks", {})
        claims = entity.get("claims", {})
        items.append(_RawWikidataItem(id=id, sitelinks=sitelinks, claims=claims))
    return items


def extract_from_raw(raw_item, site):
    try:
        sitelink = raw_item.sitelinks[site]
    except KeyError:
        return None
    return WikidataItem(
        id=raw_item.id,
        title=sitelink["title"].replace(" ", "_"),
        url=sitelink["url"],
        sitelink_count=len(raw_item.sitelinks),
    )
