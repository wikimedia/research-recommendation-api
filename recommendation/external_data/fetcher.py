import asyncio
import urllib.parse
from typing import Dict, List, Optional, Tuple

import httpx

from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log

default_headers = {"user-agent": configuration.USER_AGENT_HEADER}

httpx_client = httpx.AsyncClient(
    timeout=configuration.HTTPX_TIMEOUT_SECONDS,
    limits=httpx.Limits(
        max_keepalive_connections=configuration.HTTPX_MAX_KEEPALIVE_CONNECTIONS,
        max_connections=configuration.HTTPX_MAX_CONNECTIONS,
    ),
)


def _log_http_error(exc: httpx.HTTPError) -> None:
    """Log HTTP error with response body if available."""
    error_message = f"HTTP Exception for {exc.request.url} - {repr(exc)}"

    # Try to include response body if available
    if hasattr(exc, "response") and exc.response is not None:
        try:
            response_body = exc.response.text
            if response_body:
                # Truncate very long response bodies to keep logs manageable
                max_body_length = 1000
                if len(response_body) > max_body_length:
                    response_body = response_body[:max_body_length] + "... [truncated]"
                error_message += f" - Response body: {response_body}"
        except Exception:
            # If we can't read the response body, just continue with the original error
            pass

    log.error(error_message)


async def get(
    api_url: str, params: dict = None, headers: dict = None, fetch_all: bool = False, treat_404_as_error: bool = True
):
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
            # Handle 404s based on the treat_404_as_error parameter
            if response.status_code == 404 and not treat_404_as_error:
                log.debug(f"Resource not found (404): {url}")
                return None

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
            _log_http_error(exc)
            raise ValueError(exc) from exc

    return results


async def post(url, data=None, headers: dict = None, treat_404_as_error: bool = True):
    log.debug(f"POST: {url}")
    if headers:
        headers = {**default_headers, **headers}
    else:
        headers = default_headers
    try:
        response = await httpx_client.post(url, data=data, headers=headers)

        # Handle 404s based on the treat_404_as_error parameter
        if response.status_code == 404 and not treat_404_as_error:
            log.debug(f"Resource not found (404): {url}")
            return None

        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        _log_http_error(exc)
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

    data = await get(endpoint, params=params, headers=headers)
    sitematrix = data.get("sitematrix")
    if not sitematrix:
        raise ValueError(f"Invalid response from fetch sitematrix {data}")
    del sitematrix["count"]
    return list(sitematrix.values())


async def get_interwiki_map() -> List:
    endpoint, headers = get_endpoint_and_headers("meta")
    params = {"action": "query", "format": "json", "formatversion": "2", "meta": "siteinfo", "siprop": "interwikimap"}

    data = await get(endpoint, params=params, headers=headers)
    iwmap = data.get("query", {}).get("interwikimap")
    if not iwmap:
        raise ValueError(f"Invalid response from fetch interwiki map {data}")
    return iwmap


async def fetch_appendix_section_titles(language: str, english_appendix: List[str]) -> List[str]:
    """
    Fetch appendix section titles in the given language.
    """
    title_query_params = "|".join(urllib.parse.quote(title) for title in english_appendix)

    cxserver_path = f"v2/suggest/sections/titles/en/{language}?titles={title_query_params}"
    cxserver_url = f"{configuration.CXSERVER_URL}{cxserver_path}"
    headers = set_headers_with_host_header(configuration.CXSERVER_HEADER)

    try:
        data = await get(cxserver_url, headers=headers, treat_404_as_error=False)
        if data is None:
            return []
        return [item for values in data.values() for item in values]

    except ValueError:
        return []


async def get_wikipedia_article_sizes_and_page_ids(language: str, titles: List[str]) -> Dict[str, Dict]:
    """
    Fetch article sizes from Wikipedia API for a list of titles.

    Args:
        language (str): Language code (e.g., "en", "es", "fr")
        titles (List[str]): List of article titles

    Returns:
        Dict[str, int]: Mapping of article titles to their sizes in bytes
    """
    extra_params = {"prop": "info"}
    pages = await fetch_wikipedia_pages_in_batches(language, titles, extra_params)
    result = {}

    for page in pages:
        result[page["title"]] = {
            "length": page["length"],
            "pageid": page["pageid"],
        }

    return result


async def get_wikipedia_page_ids(language: str, titles: List[str]) -> Dict[str, int]:
    """
    Fetch Wikipedia page IDs for a list of article titles using the Wikipedia API.

    Args:
        language (str): Language code (e.g. "en", "es", "fr").
        titles (List[str]): List of article titles.

    Returns:
        Dict[str, int]: Mapping of article titles to their page IDs.
    """
    pages = await fetch_wikipedia_pages_in_batches(language, titles)
    page_ids = {}

    for page in pages:
        page_ids[page["title"]] = page["pageid"]

    return page_ids


async def fetch_wikipedia_pages_in_batches(
    language: str, titles: List[str], extra_params: Optional[Dict] = None
) -> List[Dict]:
    if not titles:
        return []

    endpoint, headers = get_endpoint_and_headers(language)

    batch_size = 50  # Wikipedia API limit per request
    base_params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
    }

    extra_params = {} if extra_params is None else extra_params
    params = base_params | extra_params

    async def fetch_batch(batch_titles: List[str]) -> List[Dict]:
        params["titles"] = "|".join(batch_titles)

        try:
            data = await get(endpoint, params=params, headers=headers)
            batch_result: List[Dict] = []

            for page in data.get("query", {}).get("pages", []):
                batch_result.append(page)

            return batch_result
        except ValueError:
            log.error(f"Failed Wikipedia pages batch fetch for {language}, titles: {batch_titles}")
            return []

    batches = [titles[i : i + batch_size] for i in range(0, len(titles), batch_size)]
    batch_tasks = [fetch_batch(batch) for batch in batches]
    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

    results: List[Dict] = []
    for result in batch_results:
        results.extend(result)

    return results


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
