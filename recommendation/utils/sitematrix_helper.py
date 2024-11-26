from recommendation.cache import get_interwiki_map_cache, get_sitematrix_cache


def get_dbname_by_prefix(prefix) -> str | None:
    interwiki_map_cache = get_interwiki_map_cache()
    interwiki_map = interwiki_map_cache.get_interwiki_map()

    wiki_url = None
    for item in interwiki_map:
        if item["prefix"] == prefix:
            wiki_url = item["url"]  # e.g. https://en.wikipedia.org/wiki/$1

    sitematrix_cache = get_sitematrix_cache()
    sitematrix = sitematrix_cache.get_sitematrix()

    for item in sitematrix:
        for wiki_site in item["site"]:
            if wiki_url.startswith(wiki_site["url"]):
                return wiki_site["dbname"]

    return None
