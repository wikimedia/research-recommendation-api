def build_search_query(prefix, value) -> str:
    """
    Build a search query for the articletopic or articlecountry
    keywords of the search API.

    See https://www.mediawiki.org/wiki/Help:CirrusSearch#Articletopic
    for search query format.

    Args:
        prefix (str): 'articletopic' or 'articlecountry'.
        value (str): The topics or countries to search, separated by | or +.

    Returns:
        str: The formatted search query.
    """
    if not value:
        return ""

    if prefix not in ["articletopic", "articlecountry"]:
        return ""

    groups = value.split("+")
    return " ".join([f"{prefix}:{group.strip()}" for group in groups])
