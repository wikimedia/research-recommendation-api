from typing import Optional, Tuple

from recommendation.cache import get_interwiki_map_cache, get_sitematrix_cache

cached_interwiki_map = None
cached_sitematrix = None


def get_sitematrix():
    global cached_sitematrix
    if cached_sitematrix is None:
        sitematrix_cache = get_sitematrix_cache()
        cached_sitematrix = sitematrix_cache.get_sitematrix()

    return cached_sitematrix


def find_sitematrix_item_by_prefix(prefix: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Finds the sitematrix item corresponding to a given prefix.

    Args:
        prefix (str): The prefix to search for (e.g., "en", "es", "zh-yue", "yue").

    Returns:
        Tuple[Optional[str], Optional[str]]: A tuple containing the language code
        and dbname associated with the prefix. Returns (None, None) if not found.

    The function first retrieves the interwiki map and searches for the given prefix.
    If found, it gets the wiki URL from there and then checks the sitematrix for matching items.
    It returns the language code and database name of the site that matches the prefix.
    """
    global cached_interwiki_map
    if cached_interwiki_map is None:
        interwiki_map_cache = get_interwiki_map_cache()
        cached_interwiki_map = interwiki_map_cache.get_interwiki_map()

    wiki_url = None
    for item in cached_interwiki_map:
        if item["prefix"] == prefix:
            wiki_url = item["url"]  # e.g. https://en.wikipedia.org/wiki/$1

    sitematrix = get_sitematrix()

    for item in sitematrix:
        for wiki_site in item["site"]:
            if wiki_url and wiki_url.startswith(wiki_site["url"]):
                return item["code"], wiki_site["dbname"]

    return None, None


def get_dbname_by_prefix(prefix: str) -> Optional[str]:
    """
    Retrieves the database name associated with a given prefix.

    Args:
        prefix (str): The prefix to search for (e.g., "en", "es", "zh-yue").

    Returns:
        Optional[str]: The dbname corresponding to the prefix, or None if not found.
    """
    lang_code, dbname = find_sitematrix_item_by_prefix(prefix)
    return dbname


def get_language_by_prefix(prefix: str) -> Optional[str]:
    """
    Retrieves the language code associated with a given prefix.

    Args:
        prefix (str): The prefix to search for (e.g., "en", "es").

    Returns:
        Optional[str]: The language code corresponding to the prefix, or None if not found.
    """
    lang_code, dbname = find_sitematrix_item_by_prefix(prefix)
    return lang_code


def get_language_by_dbname(dbname: str) -> Optional[str]:
    """
    Retrieves the language code associated with a given dbname.

    Args:
        dbname (str): The dbname to search for.

    Returns:
        Optional[str]: The language code corresponding to the dbname, or None if not found.
    """
    sitematrix = get_sitematrix()

    for item in sitematrix:
        for wiki_site in item["site"]:
            if wiki_site["dbname"] == dbname:
                return item["code"]

    return None
