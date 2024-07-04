from typing import List

from recommendation.api.translation.models import TranslationRecommendation
from recommendation.external_data import fetcher


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
    pageviews = await fetcher.get_pageviews(source, titles)
    for article in articles:
        article.pageviews = pageviews.get(article.title, 0)

    return articles
