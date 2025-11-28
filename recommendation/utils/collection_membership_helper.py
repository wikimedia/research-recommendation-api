from typing import Dict, List, Optional

from recommendation.api.translation.models import PageCollection


def find_collection_by_name(page_collections: List[PageCollection], collection_name: str) -> Optional[PageCollection]:
    """
    Find a page collection by name (case-insensitive).

    Args:
        page_collections: List of PageCollection objects to search
        collection_name: Name of the collection to find

    Returns:
        The matching PageCollection if found, None otherwise
    """
    for collection in page_collections:
        if collection.name.casefold() == collection_name.casefold():
            return collection
    return None


def check_qid_membership(collection: Optional[PageCollection], qids: str) -> Dict[str, bool]:
    """
    Check which Wikidata QIDs are members of a page collection.

    Args:
        collection: The PageCollection to check against (can be None)
        qids: Pipe-delimited string of QIDs (e.g., "Q123|Q456")

    Returns:
        Dictionary mapping each QID to a boolean indicating membership
    """
    qids_list = qids.split("|") if qids else []
    result = dict.fromkeys(qids_list, False)

    if not qids_list or not collection or not collection.articles:
        return result

    # Build a set of QIDs in the collection
    collection_qids = {article.wikidata_id for article in collection.articles}

    # Check membership for each QID
    for qid in qids_list:
        result[qid] = qid in collection_qids

    return result


def check_title_membership(collection: Optional[PageCollection], titles: str, language: str) -> Dict[str, bool]:
    """
    Check which article titles (in a specific language) are members of a page collection.

    Args:
        collection: The PageCollection to check against (can be None)
        titles: Pipe-delimited string of article titles
        language: Language code for the titles

    Returns:
        Dictionary mapping each title to a boolean indicating membership
    """
    titles_list = titles.split("|") if titles else []
    result = dict.fromkeys(titles_list, False)

    if not titles_list or not collection or not collection.articles:
        return result

    # Build a set of titles in the collection for the specified language
    collection_titles = set()
    for article in collection.articles:
        if language in article.langlinks:
            collection_titles.add(article.langlinks[language])

    # Check membership for each title
    for title in titles_list:
        result[title] = title in collection_titles

    return result
