import asyncio
import urllib.parse
from typing import List, Optional

from recommendation.api.translation.models import (
    SectionTranslationRecommendation,
    TranslationRecommendation,
)
from recommendation.cache import get_appendix_titles_cache
from recommendation.external_data.fetcher import fetch_appendix_section_titles, get, set_headers_with_host_header
from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log
from recommendation.utils.size_helper import matches_section_size_filter


async def get_section_suggestions_for_recommendations(
    recommendations: List[TranslationRecommendation],
    source_language: str,
    target_language: str,
    count,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
) -> List[SectionTranslationRecommendation]:
    title_to_collection_map = {recommendation.title: recommendation.collection for recommendation in recommendations}
    titles = list(title_to_collection_map.keys())
    appendix_titles_cache = get_appendix_titles_cache()
    source_appendix_titles = appendix_titles_cache.get_appendix_titles_for_language(source_language)
    if not source_appendix_titles:
        english_appendix_titles = appendix_titles_cache.get_appendix_titles_for_language("en")
        source_appendix_titles = await fetch_appendix_section_titles(source_language, english_appendix_titles)
        appendix_titles_cache.add_appendix_titles_for_language(source_language, source_appendix_titles)

    def is_suggestion_valid(my_result):
        if not (my_result and my_result.get("sections", {}).get("missing")):
            return False

        my_data = my_result["sections"]
        missing_source_sections = my_data["missing"].keys()
        not_appendix_missing = [title for title in missing_source_sections if title not in source_appendix_titles]
        source_section_sizes = my_data.get("sourceSectionSizes", {})
        if min_size is not None or max_size is not None:
            missing_section_sizes = {
                section: source_section_sizes[section]
                for section in not_appendix_missing
                if section in source_section_sizes
            }
            if not matches_section_size_filter(missing_section_sizes, min_size, max_size):
                return False

        return not_appendix_missing

    results = await fetch_section_suggestions(source_language, target_language, titles, count, is_suggestion_valid)
    section_suggestions: List[SectionTranslationRecommendation] = []

    for result in results:
        data = result["sections"]
        source_section_sizes = data.get("sourceSectionSizes", {})

        recommendation = SectionTranslationRecommendation(
            source_title=data["sourceTitle"],
            target_title=data["targetTitle"],
            source_sections=data["sourceSections"],
            target_sections=data["targetSections"],
            present=data["present"],
            missing=data["missing"],
            source_section_sizes=source_section_sizes,
            collection=title_to_collection_map[data["sourceTitle"]],
        )
        section_suggestions.append(recommendation)

    return section_suggestions


async def fetch_section_suggestions(
    source: str,
    target: str,
    candidate_titles: List[str],
    count: int,
    is_suggestion_valid_callback: callable,
):
    """
    Given a source language, a target language, a list of article titles and a "count" limit, this method
    fetches section suggestions for the article titles from CXServer, until the limit is reached.

    Args:
        source (str): The source language for the section suggestions, e.g. "en".
        target (str): The target language for the section suggestions, e.g. "el".
        candidate_titles (List[str]): List of article titles, for which this method will
        try to fetch suggestions for sections to translate.
        count (int): Number of articles for which section suggestions will be fetched.
        is_suggestion_valid_callback: callback that validates a section suggestion

    Returns:
        List: A list of Dicts, containing the section suggestions for each article,
        as returned by the CXServer API. The fields included inside each Dict are:
        "sourceLanguage", "targetLanguage", "sourceTitle", "targetTitle", "sourceSections",
        "targetSections", "present", "missing", "sourceSectionSizes".
    """
    if len(candidate_titles) == 0:
        return []

    # Note: Pydantic AnyUrl type returns trailing slash for the URL
    section_suggestion_api = f"{configuration.CXSERVER_URL}v2/suggest/sections/"
    headers = set_headers_with_host_header(configuration.CXSERVER_HEADER, source)

    def get_url_for_candidate(title):
        encoded_title = urllib.parse.quote(title, safe="")
        url = f"{section_suggestion_api}{encoded_title}/{source}/{target}"
        # Include section sizes to enable difficulty-based filtering
        url += "?include_section_sizes=true"
        return url

    urls = list(map(get_url_for_candidate, candidate_titles))

    semaphore = asyncio.Semaphore(configuration.API_CONCURRENCY_LIMIT)  # Limit to 10 concurrent tasks

    async def fetch_with_semaphore(url):
        async with semaphore:
            return await get(url, headers=headers, treat_404_as_error=False)

    async def process_urls():
        tasks = [asyncio.create_task(fetch_with_semaphore(url)) for url in urls]
        results = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result is not None and is_suggestion_valid_callback(result):
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
