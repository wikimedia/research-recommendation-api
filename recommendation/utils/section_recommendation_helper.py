import asyncio
import urllib.parse
from typing import List

from recommendation.api.translation.models import SectionTranslationRecommendation, TranslationRecommendation
from recommendation.external_data.fetcher import get, set_headers_with_host_header
from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log


async def get_section_suggestions_for_recommendations(
    recommendations: List[TranslationRecommendation], source_language: str, target_language: str, count
) -> List[SectionTranslationRecommendation]:
    title_to_collection_map = {recommendation.title: recommendation.collection for recommendation in recommendations}
    titles = list(title_to_collection_map.keys())

    results = await fetch_section_suggestions(source_language, target_language, titles, count)
    section_suggestions: List[SectionTranslationRecommendation] = []

    for result in results:
        data = result["sections"]
        recommendation = SectionTranslationRecommendation(
            source_title=data["sourceTitle"],
            target_title=data["targetTitle"],
            source_sections=data["sourceSections"],
            target_sections=data["targetSections"],
            present=data["present"],
            missing=data["missing"],
            collection=title_to_collection_map[data["sourceTitle"]],
        )
        section_suggestions.append(recommendation)

    return section_suggestions


async def fetch_section_suggestions(source: str, target: str, candidate_titles: List[str], count: int):
    """
    Given a source language, a target language, a list of article titles and a "count" limit, this method
    fetches section suggestions for the article titles from CXServer, until the limit is reached.

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

    semaphore = asyncio.Semaphore(configuration.API_CONCURRENCY_LIMIT)  # Limit to 10 concurrent tasks

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
