import asyncio
import re
from typing import Dict, List

from recommendation.api.translation.models import PageCollectionMetadata, WikiDataArticle, WikiPage
from recommendation.external_data.fetcher import get, get_endpoint_and_headers, get_wikipedia_article_sizes_and_page_ids
from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log
from recommendation.utils.sitematrix_helper import get_dbname_by_prefix, get_language_by_dbname, get_language_by_prefix


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

    data = await get(endpoint, params=params, headers=headers)

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
            "formatversion": 2,
            "prop": page_prop,
            "titles": page.title,
            # This param doesn't exist so it has to be filtered below
            # "iwnamespace": 0,
            "iwlimit": "max",
            "iwprop": "url",
        }

    responses = await get(endpoint, params=params, headers=headers, fetch_all=True)

    if len(responses) == 0:
        log.warning(f"No {page_prop} returned for {page.wiki}:{page.title}")
        return []

    # Aggregate all the links from the responses
    links = []
    for response in responses:
        if page_prop in response["query"]["pages"][0]:
            links.extend(response["query"]["pages"][0][page_prop])

    if len(links) == 0:
        log.warning(f"Page collection {page.wiki}:{page.title} contains no valid {page_prop}")
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
        elif title and ":" not in title:  # exclude links outside of NS_MAIN
            # Interwiki links that are not Wikidata QIDs
            language_code = get_language_by_prefix(prefix)
            links_group_by_language.setdefault(language_code, []).append(title)

    # Split the qids into batches of 50
    batches = [qids[i : i + 50] for i in range(0, len(qids), 50)]

    # Create a list to store the results
    wikidata_articles: List[WikiDataArticle] = await process_batches(batches, get_articles_by_qids)

    wikidata_articles_links_by_language = {}
    for wikidata_article in wikidata_articles:
        for language, title in wikidata_article.langlinks.items():
            wikidata_articles_links_by_language.setdefault(language, []).append(title)

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

        if len(titles) == 0:
            log.debug(
                f"All links from {page.wiki}:{page.title} for {language} are already in the cache, skipping fetch"
            )
            continue

        # Split the remaining titles into batches of 50
        batches = [titles[i : i + 50] for i in range(0, len(titles), 50)]

        articles_by_titles = await process_batches(batches, get_articles_by_titles, language)
        wikidata_articles.extend(articles_by_titles)

    wikidata_articles_with_langlinks = [article for article in wikidata_articles if len(article.langlinks) > 0]

    return wikidata_articles_with_langlinks


async def fetch_with_semaphore(batch, fetch_function, *args):
    semaphore = asyncio.Semaphore(configuration.API_CONCURRENCY_LIMIT)  # Limit to 10 concurrent tasks
    async with semaphore:
        return await fetch_function(batch, *args)


async def process_batches(batches, fetch_function, *args) -> List[WikiDataArticle]:
    tasks = [asyncio.create_task(fetch_with_semaphore(batch, fetch_function, *args)) for batch in batches]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    articles = []
    for result in results:
        if isinstance(result, Exception):
            log.error(f"Error fetching articles: {repr(result)}")
        else:
            articles.extend(result)

    return articles


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

    data = await get(endpoint, params=params, headers=headers)

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
    return await fetch_articles(params, endpoint, headers)


async def get_articles_by_titles(titles, source) -> List[WikiDataArticle]:
    """
    Get a list of articles by their titles.

    Args:
        titles (list): A list of Wikidata titles
        source (str): The source language

    Returns:
        list: A list of articles
    """
    if len(titles) == 0:
        return []

    endpoint, headers = get_endpoint_and_headers("wikidata")
    dbname = get_dbname_by_prefix(source)
    if not dbname:
        # Given source is not a valid wiki prefix and can be safely ignored
        # in the context of extracting interwiki links from page collections
        # for the purpose of translation recommendations.
        # Known irrelevant prefixes include: mw, xtools, toollabs
        log.debug(f"Unknown wiki prefix {source}")
        return []

    params = {
        "action": "wbgetentities",
        "format": "json",
        "props": "sitelinks",
        "sites": dbname,
        "titles": "|".join(titles),
        "formatversion": 2,
    }
    return await fetch_articles(params, endpoint, headers)


async def fetch_articles(params: dict, endpoint: str, headers: dict) -> List[WikiDataArticle]:
    """
    Fetch articles from the Wikidata API based on given parameters.

    Args:
        params (dict): Parameters for the API request
        endpoint (str): The API endpoint URL
        headers (dict): The API headers

    Returns:
        list: A list of WikiDataArticle instances
    """
    wikidata_articles: List[WikiDataArticle] = []
    data = await get(endpoint, params=params, headers=headers)

    if "error" in data:
        log.error(f"Error fetching articles (wikidata entities): {data['error']}")
        return []

    if "entities" in data:
        for qid, entity in data["entities"].items():
            sitelinks = entity.get("sitelinks", {})
            interlanguage_links = {
                get_language_by_dbname(dbname): info["title"]
                for dbname, info in sitelinks.items()
                if dbname.endswith("wiki") and get_language_by_dbname(dbname)
            }
            wikidata_articles.append(WikiDataArticle(wikidata_id=qid, langlinks=interlanguage_links))

    # Fetch English Wikipedia article sizes
    await populate_article_sizes_and_page_ids(wikidata_articles, "en")

    return wikidata_articles


async def populate_article_sizes_and_page_ids(wikidata_articles: List[WikiDataArticle], language: str) -> None:
    """
    Helper function to populate Wikipedia article sizes for WikiDataArticle instances.

    Args:
        wikidata_articles: List of WikiDataArticle instances to populate with sizes
        language: Language code to fetch sizes for (e.g., "en", "es", "fr")
    """
    titles = []
    article_to_title = {}

    for article in wikidata_articles:
        if language in article.langlinks:
            title = article.langlinks[language]
            titles.append(title)
            article_to_title[title] = article

    if titles:
        try:
            pages = await get_wikipedia_article_sizes_and_page_ids(language, titles)
            for title, page in pages.items():
                if title in article_to_title:
                    article_to_title[title].sizes[language] = page["length"]
                    article_to_title[title].page_ids[language] = page["pageid"]
        except Exception as e:
            log.warning(f"Failed to fetch {language} Wikipedia article sizes: {repr(e)}")
