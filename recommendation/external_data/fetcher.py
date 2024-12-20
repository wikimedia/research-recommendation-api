import asyncio
import re
import urllib.parse
from typing import Dict, List, Tuple

import httpx

from recommendation.api.translation.models import (
    PageCollectionMetadata,
    WikiDataArticle,
    WikiPage,
)
from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log
from recommendation.utils.sitematrix_helper import get_dbname_by_prefix

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


async def get_articles_by_qids(qids) -> List[WikiDataArticle]:
    """
    Get a list of articles by their Wikidata IDs.

    Args:
        qids (list): A list of Wikidata IDs

    Returns:
        list: A list of articles
    """
    endpoint, headers = get_endpoint_and_headers("wikidata")

    params = {
        "action": "wbgetentities",
        "format": "json",
        "props": "sitelinks",
        "ids": "|".join(qids),
        "formatversion": 2,
    }

    wikidata_articles: List[WikiDataArticle] = []
    try:
        data = await get(endpoint, params=params, headers=headers)
    except ValueError:
        return []
    if "error" in data:
        log.error("Error fetching articles by QIDs: %s", data["error"])
        return []

    if "entities" in data:
        for qid in data["entities"]:
            sitelinks = data["entities"][qid].get("sitelinks", {})
            interlanguage_links = {}
            for site, info in sitelinks.items():
                if site.endswith("wiki"):
                    language = site.split("wiki")[0]
                    title = info["title"]
                    interlanguage_links[language] = title

            wikidata_articles.append(WikiDataArticle(wikidata_id=qid, langlinks=interlanguage_links))

    return wikidata_articles


async def get_articles_by_titles(titles, source) -> List[WikiDataArticle]:
    """
    Get a list of articles by their titles.

    Args:
        titles (list): A list of Wikidata titles
        source (str): The source language

    Returns:
        list: A list of articles
    """
    endpoint, headers = get_endpoint_and_headers("wikidata")
    dbname = get_dbname_by_prefix(source)
    if not dbname:
        log.error(f"Could not find dbname for wiki prefix {source}")
        return []

    params = {
        "action": "wbgetentities",
        "format": "json",
        "props": "sitelinks",
        "sites": dbname,
        "titles": "|".join(titles),
        "formatversion": 2,
    }

    wikidata_articles: List[WikiDataArticle] = []
    try:
        data = await get(endpoint, params=params, headers=headers)
    except ValueError:
        return []
    if "error" in data:
        log.error("Error fetching articles by titles: %s", data["error"])
        return []

    if "entities" in data:
        for qid in data["entities"]:
            sitelinks = data["entities"][qid].get("sitelinks", {})
            interlanguage_links = {}
            for site, info in sitelinks.items():
                if site.endswith("wiki"):
                    language = site.split("wiki")[0]
                    title = info["title"]
                    interlanguage_links[language] = title

            wikidata_articles.append(WikiDataArticle(wikidata_id=qid, langlinks=interlanguage_links))

    return wikidata_articles


async def get_collection_pages() -> List[WikiPage]:
    """
    Get the list of pages that have the 'Pages including a page collection' ('page-collection-tracking-category')
    tracking category.

    Returns:
        list: A list of page titles
    """
    endpoint, headers = get_endpoint_and_headers("meta")
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "categorymembers",
        "gcmlimit": "max",
        "gcmnamespace": configuration.COLLECTIONS_NAMESPACE,
        "gcmtitle": f"Category:{configuration.COLLECTIONS_CATEGORY}",
        "prop": "info",
    }

    try:
        data = await get(endpoint, params=params, headers=headers)
    except ValueError:
        return []

    if "query" not in data or "pages" not in data["query"] or len(data["query"]["pages"]) == 0:
        log.error(f"Could not fetch the list from category Category:{configuration.COLLECTIONS_CATEGORY}")
        return []

    return [
        WikiPage(
            id=page["pageid"],
            title=page["title"],
            revision_id=page["lastrevid"],
            language=page["pagelanguage"],
            namespace=page["ns"],
            wiki="meta",
        )
        for page in data["query"]["pages"]
    ]


async def get_candidates_in_collection_page(page: WikiPage) -> List[WikiDataArticle]:  # noqa: C901
    """
    Get the candidates for translation in a page with page-collection.

    Returns:
        list: A list of candidates for the given page-collection page
    """
    # First query for the interwiki links in the page
    endpoint, headers = get_endpoint_and_headers(page.wiki)
    if page.wiki != "meta":
        page_prop = "links"
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": page_prop,
            "titles": page.title,
            "plnamespace": 0,
            "pllimit": "max",
        }
    else:
        page_prop = "iwlinks"
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": page_prop,
            "titles": page.title,
            # This param doesn't exist so it has to be filtered below
            # "iwnamespace": 0,
            "iwlimit": "max",
            "iwprop": "url",
        }
    try:
        responses = await get(endpoint, params=params, headers=headers, fetch_all=True)
    except ValueError:
        return []

    if len(responses) == 0:
        log.error(f"Could not fetch the list of links for {page.wiki}:{page.title}")
        return []

    # Aggregate all the links from the responses
    links = []
    for response in responses:
        if page_prop in response["query"]["pages"][0]:
            links.extend(response["query"]["pages"][0][page_prop])

    if len(links) == 0:
        log.error(f"No {page_prop} found for {page.wiki}:{page.title}")
        return []

    # Then query each interwiki link to complete the request with langlinks included
    qids = []
    links_group_by_language = {}

    # find all links that are wikidata qids, Check if title is Q followed by a number
    for link in links:
        title = link["title"]
        prefix = link.get("prefix", page.wiki)
        url = link.get("url", "")

        qid_match = re.match(r"(Q[\d]+)", title)
        if qid_match and url.startswith("https://www.wikidata.org"):
            qid = qid_match.group(1)
            qids.append(qid)
        elif ":" not in title:  # exclude links outside of NS_MAIN
            # Interwiki links that are not Wikidata QIDs
            if prefix not in links_group_by_language:
                links_group_by_language[prefix] = []
            links_group_by_language[prefix].append(title)

    # Split the qids into batches of 50
    batches = [qids[i : i + 50] for i in range(0, len(qids), 50)]

    # Create a list to store the results
    wikidata_articles = []

    # Iterate over each batch of qids
    semaphore = asyncio.Semaphore(configuration.API_CONCURRENCY_LIMIT)  # Limit to 10 concurrent tasks

    async def fetch_with_semaphore(batch):
        async with semaphore:
            return await get_articles_by_qids(batch)

    tasks = [asyncio.create_task(fetch_with_semaphore(batch)) for batch in batches]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            log.error(f"Error fetching articles by QIDs: {result}")
        else:
            wikidata_articles.extend(result)

    wikidata_articles_links_by_language = {}
    for wikidata_article in wikidata_articles:
        for language, title in wikidata_article.langlinks.items():
            if language not in wikidata_articles_links_by_language:
                wikidata_articles_links_by_language[language] = []
            wikidata_articles_links_by_language[language].append(title)

    for language in links_group_by_language:
        # Filter out language links that were already retrieve from wikidata
        initial_count = len(links_group_by_language[language])
        titles_from_wikidata = wikidata_articles_links_by_language.get(language, [])
        # Convert titles from wikidata to underscore format
        titles_from_wikidata = [title.replace(" ", "_") for title in titles_from_wikidata]
        titles = list(set(links_group_by_language[language]) - set(titles_from_wikidata))
        final_count = len(titles)
        skipped = initial_count - final_count
        if skipped > 0:
            log.debug(f"Skipped {skipped}/{initial_count} links for {language} as they are already in the cache")

        # Split the remaining titles into batches of 50
        batches = [titles[i : i + 50] for i in range(0, len(titles), 50)]
        semaphore = asyncio.Semaphore(configuration.API_CONCURRENCY_LIMIT)  # Limit to 10 concurrent tasks

        async def fetch_with_semaphore(batch):
            async with semaphore:  # noqa: B023
                return await get_articles_by_titles(batch, language)  # noqa: B023

        tasks = [asyncio.create_task(fetch_with_semaphore(batch)) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                log.error(f"Error fetching articles by titles: {result}")
            else:
                wikidata_articles.extend(result)

    wikidata_articles_with_langlinks = [article for article in wikidata_articles if len(article.langlinks) > 0]

    return wikidata_articles_with_langlinks


async def get_collection_metadata_by_pages(pages: List[WikiPage]) -> Dict[str, PageCollectionMetadata]:
    """
    Get the page collection metadata for a list of pages including the <page-collection> marker
    Args:
        pages (List[WikiPage]): a list of pages including the <page-collection> marker
    Returns:
        Dict[str, PageCollectionMetadata] a dictionary mapping the page id (int) of each page to its metadata
    """
    endpoint, headers = get_endpoint_and_headers("meta")

    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "list": "pagecollectionsmetadata",
        "titles": "|".join(page.title for page in pages),
    }
    try:
        data = await get(endpoint, params=params, headers=headers)
    except ValueError:
        log.error("Could not fetch the page collection metadata for the given pages")
        return {}

    result_property = "page_collections"
    if (
        "query" not in data
        or result_property not in data["query"]
        or not data["query"][result_property]
        or "pages" not in data["query"]
        or not data["query"]["pages"]
    ):
        log.error("No page collection metadata exists for the given pages")
        return {}

    normalization_map: Dict = {item["to"]: item["from"] for item in data["query"].get("normalized", [])}

    metadata: Dict = data["query"][result_property]
    metadata_by_pages = {}

    for page in data["query"]["pages"]:
        page_title = page["title"]
        title = normalization_map.get(page_title) or page_title
        page_metadata = metadata.get(title) or {}

        metadata_by_pages[page.get("pageid")] = PageCollectionMetadata(
            name=page_metadata.get("name") or title,
            description=page_metadata.get("description", None),
            end_date=page_metadata.get("end-date", None),
        )

    return metadata_by_pages


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
