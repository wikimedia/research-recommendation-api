import asyncio
import re
import urllib.parse
from typing import Dict, List

import httpx

from recommendation.api.translation.models import TranslationRecommendationRequest, WikiDataArticle, WikiPage
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

    encoded_params = urllib.parse.urlencode(params, safe=":+|") if params else ""
    url = f"{url}?{encoded_params}" if encoded_params else url
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


async def wiki_search(rec_req_model: TranslationRecommendationRequest):
    """
    A client to the Mediawiki search API

    Args:
        rec_req_model (TranslationRecommendationRequest): The translation recommendation request model.

    Returns:
        list: A list of pages that match the search query.
    """
    endpoint, params, headers = build_wiki_search(rec_req_model)

    try:
        response = await get(endpoint, params=params, headers=headers)
    except ValueError:
        log.error(
            f"Could not search for articles related to search {rec_req_model}. Choose another language.",
        )
        return []

    if "query" not in response or "pages" not in response["query"]:
        log.debug(f"Recommendation request {rec_req_model} does not map to an article")
        return []

    pages = response["query"]["pages"]

    if len(pages) == 0:
        log.debug(f"Recommendation request {rec_req_model} does not map to an article")
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


def build_wiki_search(rec_req_model: TranslationRecommendationRequest):
    """
    Builds the parameters and headers required for making a Wikipedia search API request.

    Args:
        rec_req_model (TranslationRecommendationRequest): The translation recommendation request model.

    Returns:
        tuple: A tuple containing the endpoint URL, parameters, and headers for the API request.
    """
    endpoint = get_formatted_endpoint(configuration.WIKIPEDIA_API, rec_req_model.source)
    headers = set_headers_with_host_header(configuration.WIKIPEDIA_API_HEADER, rec_req_model.source)

    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "prop": "langlinks|langlinkscount|pageprops",
        "lllimit": "max",
        "lllang": rec_req_model.target,
        "generator": "search",
        "gsrprop": "wordcount",
        "gsrnamespace": 0,
        "gsrwhat": "text",
        "gsrlimit": "max",
        "ppprop": "wikibase_item|disambiguation",
        "gsrqiprofile": "classic_noboostlinks",
        "gsrsort": "random",
    }

    gsrsearch_query = []

    if rec_req_model.topic:
        topics = rec_req_model.topic.replace(" ", "-").lower()
        topic_and_items = topics.split("+")
        search_expression = "+".join([f"articletopic:{topic_and_item.strip()}" for topic_and_item in topic_and_items])
        gsrsearch_query.append(search_expression)

    if rec_req_model.seed:
        # morelike is a "greedy" keyword, meaning that it cannot be combined with other search queries.
        # To use other search queries, use morelikethis in your search:
        # https://www.mediawiki.org/wiki/Help:CirrusSearch#morelike
        if len(gsrsearch_query):
            gsrsearch_query.append(f"morelikethis:{rec_req_model.seed}")
        else:
            gsrsearch_query.append(f"morelike:{rec_req_model.seed}")

    params["gsrsearch"] = " ".join(gsrsearch_query)

    log.debug(f"Search params: {params}")
    return endpoint, params, headers


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


async def get_section_suggestions(source: str, target: str, candidate_titles: List[str], count: int):
    """
    Get formatted endpoint with the appropriate source based on whether it runs on
    LiftWing or wmflabs.
    (see T348607)

    Args:
        source (str): The source language for the section suggestions, e.g. "en".
        target (str): The target language for the section suggestions, e.g. "el".
        candidate_titles (List[str]): List of article titles, for which this method will
        try to fetch suggestions for sections to translate.
        count (str): Number of articles for which section suggestions will be fetched.

    Returns:
        List: A list of Dicts, containing the section suggestions for each article,
        as returned by the CXServer API. The fields included inside each Dict are:
        "sourceLanguage", "targetLanguage", "sourceTitle", "targetTitle", "sourceSections",
        "targetSections", "present", "missing".
    """
    if len(candidate_titles) == 0:
        return []

    # Note: Pydantic AnyUrl type returns trailing slash for the URL
    section_suggestion_api = f"{configuration.CXSERVER_URL}v2/suggest/sections/"
    headers = set_headers_with_host_header(configuration.CXSERVER_HEADER, source)

    def get_url_for_candidate(title):
        encoded_title = urllib.parse.quote(title, safe="")
        return f"{section_suggestion_api}{encoded_title}/{source}/{target}"

    urls = list(map(get_url_for_candidate, candidate_titles))

    semaphore = asyncio.Semaphore(configuration.CXSERVER_API_CONCURRENCY)  # Limit to 10 concurrent tasks

    async def fetch_with_semaphore(url):
        async with semaphore:
            return await get(url, headers=headers)

    async def process_urls():
        tasks = [asyncio.create_task(fetch_with_semaphore(url)) for url in urls]
        results = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result:
                    results.append(result)
            except Exception as e:
                log.error(f"Error fetching section suggestions: {e}")

            if len(results) >= count:
                # Cancel remaining tasks
                [task.cancel() for task in tasks if not task.done()]
                break
        return results

    successful_results = await process_urls()
    return successful_results[:count]


async def get_articles_by_qids(qids) -> List[WikiDataArticle]:
    """
    Get a list of articles by their Wikidata IDs.

    Args:
        qids (list): A list of Wikidata IDs

    Returns:
        list: A list of articles
    """
    endpoint = get_formatted_endpoint(configuration.WIKIDATA_API)
    headers = set_headers_with_host_header(configuration.WIKIDATA_API_HEADER)

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
        return ""
    if "error" in data:
        log.error("Error fetching articles by QIDs: %s", data["error"])
        return

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
    endpoint = get_formatted_endpoint(configuration.WIKIDATA_API)
    headers = set_headers_with_host_header(configuration.WIKIDATA_API_HEADER)

    params = {
        "action": "wbgetentities",
        "format": "json",
        "props": "sitelinks",
        "sites": f"{source}wiki",
        "titles": "|".join(titles),
        "formatversion": 2,
    }

    wikidata_articles: List[WikiDataArticle] = []
    try:
        data = await get(endpoint, params=params, headers=headers)
    except ValueError:
        return ""
    if "error" in data:
        log.error("Error fetching articles by QIDs: %s", data["error"])
        return

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
    Get the list of pages that have the 'Pages including a page collection' tracking category.

    Returns:
        list: A list of page titles
    """
    endpoint = get_formatted_endpoint(configuration.WIKIMEDIA_API)
    headers = set_headers_with_host_header(configuration.WIKIMEDIA_API_HEADER)
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
        return ""

    if "query" not in data or "pages" not in data["query"] or len(data["query"]["pages"]) == 0:
        log.error("Could not fetch the list")
        return ""

    return [
        WikiPage(
            id=page["pageid"],
            title=page["title"],
            revision_id=page["lastrevid"],
            language=page["pagelanguage"],
            namespace=page["ns"],
        )
        for page in data["query"]["pages"]
    ]


async def get_candidates_in_collection_page(page: WikiPage) -> List[WikiDataArticle]:
    """
    Get the candidates for translation in a page with page-collection.

    Returns:
        list: A list of candidates for the given page-collection page
    """
    # First query for the interwiki links in the page
    endpoint = get_formatted_endpoint(configuration.WIKIMEDIA_API)
    headers = set_headers_with_host_header(configuration.WIKIMEDIA_API_HEADER)
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "iwlinks",
        "titles": page.title,
        "iwlimit": "max",
        "iwprop": "url",
    }

    try:
        data = await get(endpoint, params=params, headers=headers)
    except ValueError:
        return []

    if "query" not in data or "pages" not in data["query"]:
        log.error("Could not fetch the list")
        return []

    if "iwlinks" not in data["query"]["pages"][0]:
        log.error("No candidates found")
        return []

    # Then query each interwiki link to complete the request with langlinks included
    iwlinks = data["query"]["pages"][0]["iwlinks"]

    qids = []
    iwlinks_group_by_language = {}

    # find all links that are wikidata qids, Check if title is Q followed by a number
    for link in iwlinks:
        title = link["title"]
        prefix = link["prefix"]
        url = link["url"]
        qid_match = re.match(r"(Q[\d]+)", title)
        if qid_match and url.startswith("https://www.wikidata.org") and link["prefix"] == "d":
            qid = qid_match.group(1)
            qids.append(qid)
        else:
            # Interwiki links that are not Wikidata QIDs
            if prefix not in iwlinks_group_by_language:
                iwlinks_group_by_language[prefix] = []
            iwlinks_group_by_language[prefix].append(title)

    # Split the qids into batches of 50
    batches = [qids[i : i + 50] for i in range(0, len(qids), 50)]

    # Create a list to store the results
    wikidata_articles = []

    # Iterate over each batch of qids
    for batch in batches:
        articles = await get_articles_by_qids(batch)
        wikidata_articles.extend(articles)

    for language in iwlinks_group_by_language:
        titles = iwlinks_group_by_language[language]
        # Split the qids into batches of 50
        batches = [titles[i : i + 50] for i in range(0, len(titles), 50)]
        for batch in batches:
            articles = await get_articles_by_titles(batch, language)
            wikidata_articles.extend(articles)

    return wikidata_articles
