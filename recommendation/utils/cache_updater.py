import asyncio
from typing import Dict, List, Optional, Set

from recommendation.api.translation.models import (
    PageCollection,
    PageCollectionMetadata,
    PageCollectionsList,
    WikiPage,
)
from recommendation.cache import get_interwiki_map_cache, get_page_collection_cache, get_sitematrix_cache
from recommendation.external_data import fetcher
from recommendation.utils.collection_fetcher import get_collection_metadata_by_pages, get_collection_pages
from recommendation.utils.logger import log


def find_page_collection_by_cache_key(
    cached_page_collections: Set[PageCollection], collection_key: str
) -> Optional[PageCollection]:
    for collection in cached_page_collections:
        if collection.cache_key == collection_key:
            return collection  # Return the collection when found

    return None  # Return None if no match is found


def combine_collection_pages_and_metadata(
    pages: List[WikiPage], metadata_by_pages: Dict[str, PageCollectionMetadata]
) -> Set[PageCollection]:
    page_collections: Set[PageCollection] = set()
    for page in pages:
        metadata = metadata_by_pages.get(page.id)
        if not metadata:
            log.warning(f"Collection metadata not found for: {page.title}")
            continue
        page_collection = PageCollection(
            name=metadata.name,
            pages={page},
            description=metadata.description,
            end_date=metadata.end_date,
        )
        page_collections.add(page_collection)

    return page_collections


async def update_page_collection_cache():
    """
    Update the page-collection cache with the page-collection pages and their articles
    """
    # Get all pages containing a page-collection marker
    collection_pages: List[WikiPage] = await get_collection_pages()

    # Get metadata for each page
    batch_size = 20
    collection_metadata_by_pages: Dict[str, PageCollectionMetadata] = {}
    semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent tasks

    async def limited_task(task):
        async with semaphore:
            return await task

    tasks = [
        limited_task(get_collection_metadata_by_pages(collection_pages[i : i + batch_size]))
        for i in range(0, len(collection_pages), batch_size)
    ]
    try:
        batch_results = await asyncio.gather(*tasks)
        for result in batch_results:
            collection_metadata_by_pages.update(result)
    except Exception as e:
        log.error(f"Failed to fetch page collection metadata: {e}")
        return

    fetched_page_collections: Set[PageCollection] = combine_collection_pages_and_metadata(
        collection_pages, collection_metadata_by_pages
    )
    page_collection_cache = get_page_collection_cache()
    cached_page_collections: Set[PageCollection] = page_collection_cache.get_page_collections() or set()
    page_collections_list: PageCollectionsList = PageCollectionsList()

    for live_page_collection in fetched_page_collections:
        cached_page_collection = find_page_collection_by_cache_key(
            cached_page_collections, live_page_collection.cache_key
        )

        if cached_page_collection and cached_page_collection.articles_count > 0:
            page_collections_list.add(cached_page_collection)
            log.debug(f"Found page collection {cached_page_collection} in cache")
        else:
            await live_page_collection.fetch_articles()
            if live_page_collection.articles_count > 0:
                page_collections_list.add(live_page_collection)

    page_collection_cache.set_page_collections(page_collections_list)


async def initialize_interwiki_map_cache():
    interwiki_map = await fetcher.get_interwiki_map()
    # log.debug(f"interwiki_map {interwiki_map}")

    interwiki_map_cache = get_interwiki_map_cache()
    interwiki_map_cache.set_interwiki_map(interwiki_map)


async def initialize_sitematrix_cache():
    sitematrix = await fetcher.get_sitematrix()

    sitematrix_cache = get_sitematrix_cache()
    sitematrix_cache.set_sitematrix(sitematrix)


def start():
    import asyncio

    async def initialize_cache():
        await initialize_interwiki_map_cache()
        await initialize_sitematrix_cache()
        await update_page_collection_cache()

    asyncio.run(initialize_cache())
