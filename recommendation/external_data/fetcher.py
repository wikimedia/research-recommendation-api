import urllib.parse
from typing import Dict, List, Tuple

import httpx

from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log

default_headers = {"user-agent": configuration.USER_AGENT_HEADER}

httpx_client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_keepalive_connections=5, max_connections=5))


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
        encoded_params = urllib.parse.urlencode(queryparams, safe=":+|") if params else ""

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
