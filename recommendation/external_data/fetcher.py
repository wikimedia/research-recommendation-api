import urllib.parse
from typing import Dict

import httpx

from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log

default_headers = {"user-agent": configuration.USER_AGENT_HEADER}

httpx_client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_keepalive_connections=5, max_connections=5))


async def get(url: str, params: dict = None, headers: dict = None):
    log.debug("Get: %s", url)
    if headers:
        headers = {**default_headers, **headers}
    else:
        headers = default_headers

    encoded_params = urllib.parse.urlencode(params, safe=":+|")
    url = f"{url}?{encoded_params}"
    # We are encoding the params outside httpx since the httpx encoding
    # is very strict and does not allow some characters in the params
    try:
        response = await httpx_client.get(
            url,
            # params=params,
            headers=headers,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.RequestError, ValueError) as exc:
        log.error(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.")
        raise ValueError(exc) from exc


async def post(url, data=None, headers: dict = None):
    log.debug("Post: %s", url)
    if headers:
        headers = {**default_headers, **headers}
    else:
        headers = default_headers
    try:
        response = await httpx_client.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except (httpx.RequestError, ValueError) as exc:
        log.error(f"Error response {exc.response.status_code} while posting to {exc.request.url!r}.")
        raise ValueError(exc) from exc


async def get_pageviews(source, titles) -> Dict[str, int]:
    """
    Get pageview counts for a given list of titles from the Wikipedia API.
    """
    endpoint = get_formatted_endpoint(configuration.WIKIPEDIA_API, source)
    headers = set_headers_with_host_header(configuration.WIKIPEDIA_API_HEADER, source)
    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "prop": "pageviews",  # description|pageimages if we need more data
        "titles": "|".join(titles),
        "pvipdays": 1,
    }
    try:
        data = await get(url=endpoint, params=params, headers=headers)
    except ValueError:
        data = {}

    pages = data.get("query", {}).get("pages", [])
    pageviews = {}
    for page in pages:
        pageviews[page.get("title")] = sum(filter(None, page.get("pageviews", {}).values()))

    return pageviews


async def wiki_search(source, seeds, morelike=False, filter_disambiguation=False, filter_language=None):
    """
    A client to the Mediawiki search API
    """
    endpoint, params, headers = build_wiki_search(source, seeds, morelike, None, filter_disambiguation, filter_language)

    try:
        response = await get(endpoint, params=params, headers=headers)
    except ValueError:
        log.error(
            "Could not search for articles related to seed in %s. Choose another language.",
            source,
        )
        return []

    if "query" not in response or "pages" not in response["query"]:
        log.info(
            "Could not search for articles related to seed in %s. Choose another language.",
            source,
        )
        return []

    pages = response["query"]["pages"]

    if len(pages) == 0:
        log.info("No articles similar to %s in %s. Try another seed.", seeds, source)
        return []

    return pages


async def wiki_topic_search(source, topics, filter_disambiguation=False, filter_language=None):
    """
    A client to the Mediawiki search API
    """
    endpoint, params, headers = build_wiki_search(
        source=source,
        seeds=None,
        topics=topics,
        morelike=False,
        filter_disambiguation=filter_disambiguation,
        filter_language=filter_language,
    )
    try:
        response = await get(endpoint, params=params, headers=headers)
    except ValueError:
        log.error(
            f"Could not search for articles related to topic {topics} in {source}. Choose another language.",
        )
        return []

    if "query" not in response or "pages" not in response["query"]:
        log.info(
            f"Could not search for articles related to topic {topics} in {source}. Choose another language.",
        )
        return []

    pages = response["query"]["pages"]

    if len(pages) == 0:
        log.info("No articles similar to %s in %s. Try another seed.", topics, source)
        return []

    return pages


async def get_most_popular_articles(source, filter_language):
    endpoint = get_formatted_endpoint(configuration.WIKIPEDIA_API, source)
    headers = set_headers_with_host_header(configuration.WIKIPEDIA_API_HEADER, source)
    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "prop": "langlinks|langlinkscount|pageprops",
        "lllimit": "max",
        "lllang": filter_language,
        "generator": "mostviewed",
        "gpvimlimit": "max",
        "ppprop": "wikibase_item|disambiguation",
    }

    try:
        data = await get(url=endpoint, params=params, headers=headers)
    except ValueError:
        log.info("pageview query failed")
        return []

    if "query" not in data or "pages" not in data["query"]:
        log.info("pageview data is not in a known format")
        return []

    # Filter for main namespace articles
    pages = [page for page in data["query"]["pages"] if page["ns"] == 0]
    return pages


def build_wiki_search(source, seeds, morelike, topics, filter_disambiguation, filter_language):
    """
    Builds the parameters and headers required for making a Wikipedia search API request.

    Args:
        source (str): The source of the search.
        seed (str): The search term or seed.
        morelike (bool): Flag indicating whether to search for pages similar to the seed.
        topics (str): The topics to search.
        filter_disambiguation (bool): Flag indicating whether to filter out disambiguation pages.
        filter_language (str): The language code to filter the search results.
            Only return language links with this language code.

    Returns:
        tuple: A tuple containing the endpoint URL, parameters, and headers for the API request.
    """
    endpoint = get_formatted_endpoint(configuration.WIKIPEDIA_API, source)
    headers = set_headers_with_host_header(configuration.WIKIPEDIA_API_HEADER, source)

    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "prop": "langlinks|langlinkscount|pageprops",
        "lllimit": "max",
        "generator": "search",
        "gsrprop": "wordcount",
        "gsrnamespace": 0,
        "gsrwhat": "text",
        "gsrlimit": "max",
        "ppprop": "wikibase_item",
    }
    params["gsrsearch"] = ""
    if morelike:
        params["gsrsearch"] += f"morelike:{seeds}"

    if topics:
        topics = topics.replace(" ", "-").lower()
        topic_and_items = topics.split("+")
        search_expression = "+".join([f"articletopic:{topic_and_item.strip()}" for topic_and_item in topic_and_items])
        params["gsrsearch"] += search_expression

    if filter_language:
        params["lllang"] = filter_language

    if filter_disambiguation:
        params["ppprop"] = "wikibase_item|disambiguation"
    log.info(params)
    return endpoint, params, headers


def get_related_articles(source, seed):
    endpoint = configuration.get_config_value("endpoints", "related_articles")
    headers = set_headers_with_host_header(configuration, "related_articles")
    try:
        response = get(endpoint, {"source": source, "seed": seed, "count": 500}, headers=headers)
    except ValueError:
        return []
    return response


def set_headers_with_host_header(configuration, source=""):
    """
    Sets headers with host header if .ini configuration has the 'endpoint_host_headers'
    section that runs on LiftWing. (see T348607)

    Args:
        configuration (Configuration): The configuration object.
        endpoint_name (str): The name of the endpoint, e.g. "wikipedia" or "pageviews".
        source (str): The source of the data, e.g. "en" or "fr". This parameter defaults to ''
        so that this function can be used for host headers that don't require it.

    Returns:
        dict: The updated headers dictionary.
    """
    headers = {}
    if configuration:
        host_header = str(configuration).format(source=source)
        headers["Host"] = host_header
    return headers


def get_formatted_endpoint(configuration, source=""):
    """
    Get formatted endpoint with the appropriate source based on whether it runs on
    LiftWing or wmflabs.
    (see T348607)

    Args:
        configuration (Configuration): The configuration object.
        endpoint_name (str): The name of the endpoint.
        source (str): The source of the data, e.g. "en".
        This parameter defaults to '' so that this function can be used for endpoints that don't
        require it e.g the source is not set for LiftWing wikipedia endpoints but it's set
        for wmflabs.

    Returns:
        str: The endpoint.
    """
    endpoint = str(configuration).format(source=source)
    return endpoint
