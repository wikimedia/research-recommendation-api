import asyncio
import urllib.parse
from typing import Dict, List, Tuple

import httpx

from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log

default_headers = {"user-agent": configuration.USER_AGENT_HEADER}

httpx_client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_keepalive_connections=5, max_connections=20))


async def get(api_url: str, params: dict = None, headers: dict = None, fetch_all: bool = False):
    if headers:
        headers = {**default_headers, **headers}
    else:
        headers = default_headers

    if "Host" not in headers:
        log.error(f"Host header is missing in the request headers for {api_url}")
        raise ValueError("Host header is required.")

    results = []
    # Clone original request params to avoid modifying the original dict
    last_continue = {}
    while True:
        queryparams = params.copy() if params else {}
        queryparams.update(last_continue)

        # We are encoding the params outside httpx since the httpx encoding
        # is very strict and does not allow some characters in the params
        encoded_params = urllib.parse.urlencode(queryparams, safe=":|") if params else ""

        url = f"{api_url}?{encoded_params}" if encoded_params else api_url
        log.debug(f"GET: {url}, {headers}")
        try:
            # follow_redirects is disabled to avoid proxy bypass.
            # All requests must go through the proxy and have a proper host header.
            response = await httpx_client.get(
                url,
                # params=params,
                headers=headers,
                follow_redirects=False,
            )
            response.raise_for_status()
            result = response.json()

            # this is a single fetch, return the result
            if not fetch_all:
                return result

            # this is a fetch all, append the result and try to continue
            results.append(result)
            if "continue" not in result:
                break
            log.debug("Continue: %s", result["continue"])
            last_continue = result["continue"]
        except httpx.HTTPError as exc:
            log.error(f"HTTP Exception for {exc.request.url} - {exc}")
            raise ValueError(exc) from exc

    return results


async def post(url, data=None, headers: dict = None):
    log.debug(f"POST: {url}")
    if headers:
        headers = {**default_headers, **headers}
    else:
        headers = default_headers
    try:
        response = await httpx_client.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        log.error(f"HTTP Exception for {exc.request.url} - {exc}")
        raise ValueError(exc) from exc


def set_headers_with_host_header(configuration, source=""):
    """
    Sets headers with host header if .ini configuration has the 'endpoint_host_headers'
    section that runs on LiftWing. (see T348607)

    Args:
        configuration (Configuration): The configuration object.
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
        source (str): The source of the data, e.g. "en".
        This parameter defaults to '' so that this function can be used for endpoints that don't
        require it e.g the source is not set for LiftWing wikipedia endpoints but it's set
        for wmflabs.

    Returns:
        str: The endpoint.
    """
    endpoint = str(configuration).format(source=source)
    return endpoint


async def get_sitematrix() -> List:
    endpoint, headers = get_endpoint_and_headers("meta")
    params = {
        "action": "sitematrix",
        "format": "json",
        "formatversion": "2",
        "smtype": "language",
        "smlangprop": "code|site",
    }

    try:
        data = await get(endpoint, params=params, headers=headers)
        sitematrix = data["sitematrix"]
        del sitematrix["count"]
        return list(sitematrix.values())
    except ValueError:
        return []


async def get_interwiki_map() -> List:
    endpoint, headers = get_endpoint_and_headers("meta")
    params = {"action": "query", "format": "json", "formatversion": "2", "meta": "siteinfo", "siprop": "interwikimap"}

    try:
        data = await get(endpoint, params=params, headers=headers)
        return data["query"]["interwikimap"]
    except ValueError:
        return []


async def fetch_appendix_section_titles(language: str, english_appendix: List[str]) -> List[str]:
    """
    Fetch appendix section titles in the given language.
    """
    title_query_params = "|".join(urllib.parse.quote(title) for title in english_appendix)

    cxserver_path = f"v2/suggest/sections/titles/en/{language}?titles={title_query_params}"
    cxserver_url = f"{configuration.CXSERVER_URL}{cxserver_path}"
    headers = set_headers_with_host_header(configuration.CXSERVER_HEADER)

    try:
        response = await get(cxserver_url, headers=headers)
        response.raise_for_status()

        data = response.json()
        return [item for values in data.values() for item in values]

    except ValueError:
        return []


async def get_wikipedia_article_sizes(language: str, titles: List[str]) -> Dict[str, int]:
    """
    Fetch article sizes from Wikipedia API for a list of titles.

    Args:
        language (str): Language code (e.g., "en", "es", "fr")
        titles (List[str]): List of article titles

    Returns:
        Dict[str, int]: Mapping of article titles to their sizes in bytes
    """
    if not titles:
        return {}

    endpoint, headers = get_endpoint_and_headers(language)

    # Wikipedia API can handle up to 50 titles per request
    batch_size = 50

    async def fetch_batch_sizes(batch_titles: List[str]) -> Dict[str, int]:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "info",
            "titles": "|".join(batch_titles),
        }

        try:
            data = await get(endpoint, params=params, headers=headers)
            batch_sizes = {}
            if "query" in data and "pages" in data["query"]:
                for page in data["query"]["pages"]:
                    if "length" in page and "title" in page:
                        batch_sizes[page["title"]] = page["length"]
            return batch_sizes
        except ValueError:
            log.error(f"Failed to fetch article sizes for language {language}, batch: {batch_titles}")
            return {}

    # Create batches and tasks
    batches = [titles[i : i + batch_size] for i in range(0, len(titles), batch_size)]
    batch_tasks = [fetch_batch_sizes(batch) for batch in batches]

    # Execute all batches concurrently
    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

    # Merge results
    all_sizes = {}
    for result in batch_results:
        if isinstance(result, dict):
            all_sizes.update(result)
        elif isinstance(result, Exception):
            log.error(f"Error fetching article sizes batch: {result}")

    return all_sizes


def get_endpoint_and_headers(source: str) -> Tuple[str, Dict[str, str]]:
    """
    Retrieves the API endpoint and headers based on the given source.

    Args:
        source (str): The source for which the endpoint and headers are to be fetched.
                      Possible values are "meta", "wikidata", and others.

    Returns:
        Tuple[str, Dict[str, str]]: A tuple containing the formatted endpoint URL and the headers dictionary.
    """
    if source == "meta":
        endpoint = get_formatted_endpoint(configuration.WIKIMEDIA_API, source)
        headers = set_headers_with_host_header(configuration.WIKIMEDIA_API_HEADER, source)
    elif source == "wikidata":
        endpoint = get_formatted_endpoint(configuration.WIKIDATA_API)
        headers = set_headers_with_host_header(configuration.WIKIDATA_API_HEADER)
    else:
        endpoint = get_formatted_endpoint(configuration.WIKIPEDIA_API, source)
        headers = set_headers_with_host_header(configuration.WIKIPEDIA_API_HEADER, source)
    return endpoint, headers
