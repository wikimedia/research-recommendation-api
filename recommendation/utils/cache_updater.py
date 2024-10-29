from typing import Dict, List, Optional, Set

from recommendation.api.translation.models import (
    PageCollection,
    PageCollectionMetadata,
    PageCollectionsList,
    WikiPage,
)
from recommendation.cache import get_page_collection_cache
from recommendation.external_data import fetcher
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
        metadata = metadata_by_pages[page.id]
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
    collection_pages: List[WikiPage] = await fetcher.get_collection_pages()

    # Get metadata for each page
    collection_metadata_by_pages = await fetcher.get_collection_metadata_by_pages(collection_pages)

    fetched_page_collections: Set[PageCollection] = combine_collection_pages_and_metadata(
        collection_pages, collection_metadata_by_pages
    )
    page_collection_cache = get_page_collection_cache()
    cached_page_collections: Set[PageCollection] = page_collection_cache.get_page_collections() or set()
    page_collections_list: PageCollectionsList = PageCollectionsList()

    for fetched_page_collection in fetched_page_collections:
        cached_page_collection = find_page_collection_by_cache_key(
            cached_page_collections, fetched_page_collection.cache_key
        )

        if cached_page_collection:
            page_collections_list.add(cached_page_collection)
            log.debug(f"Found page collection {cached_page_collection} in cache")
        else:
            await fetched_page_collection.fetch_articles()
            page_collections_list.add(fetched_page_collection)

    page_collection_cache.set_page_collections(page_collections_list)
