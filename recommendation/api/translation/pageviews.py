from typing import Dict, List

from recommendation.api.translation.models import TranslationRecommendation
from recommendation.external_data.fetcher import get, get_formatted_endpoint, set_headers_with_host_header
from recommendation.utils.configuration import configuration


async def set_pageview_data(source: str, articles: List[TranslationRecommendation]):
    """
    Sets the pageview data for a list of articles.

    Args:
        source (str): The source of the pageviews data.
        articles (List[TranslationRecommendation]): A list of TranslationRecommendation objects
          representing the articles.

    Returns:
        List[TranslationRecommendation]: The updated list of articles with pageview data.

    """
    titles = [article.title for article in articles]
    pageviews = await fetch_pageviews(source, titles)
    for article in articles:
        article.pageviews = pageviews.get(article.title, 0)

    return articles


async def fetch_pageviews(source, titles) -> Dict[str, int]:
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
        data = await get(api_url=endpoint, params=params, headers=headers)
    except ValueError:
        data = {}

    pages = data.get("query", {}).get("pages", [])
    pageviews = {}
    for page in pages:
        pageviews[page.get("title")] = sum(filter(None, page.get("pageviews", {}).values()))

    return pageviews
