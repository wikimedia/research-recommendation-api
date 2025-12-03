import asyncio
import urllib.parse
from collections.abc import Callable
from typing import List, Optional

from recommendation.api.translation.models import (
    SectionTranslationRecommendation,
    TranslationRecommendation,
)
from recommendation.cache import get_appendix_titles_cache
from recommendation.external_data.fetcher import fetch_appendix_section_titles, get, set_headers_with_host_header
from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log
from recommendation.utils.recommendation_helper import collect_results_ordered
from recommendation.utils.size_helper import matches_section_size_filter


async def get_appendix_titles(language):
    """
    Retrieves appendix section titles for a given language, with caching.

    Checks cache first. If not found, fetches by translating English appendix
    titles to the target language and caches the result.
    """
    appendix_titles_cache = get_appendix_titles_cache()
    appendix_titles = appendix_titles_cache.get_appendix_titles_for_language(language)

    if not appendix_titles:
        english_appendix_titles = appendix_titles_cache.get_appendix_titles_for_language("en")
        appendix_titles = await fetch_appendix_section_titles(language, english_appendix_titles)
        appendix_titles_cache.add_appendix_titles_for_language(language, appendix_titles)

    return appendix_titles


async def create_suggestion_validator(language: str, min_size: Optional[int], max_size: Optional[int]) -> Callable:
    """
    Creates a validator function for section translation suggestions.

    Fetches appendix titles for the language and returns a validator that filters
    suggestions based on non-appendix sections and optional size constraints.

    Returns:
        Callable: Validator function that takes a suggestion result and returns it
            if valid, or None if it should be filtered out.

    Validation logic:
        - Rejects if no valid "missing" sections found
        - Filters out appendix sections (e.g., "References", "See also")
        - Applies size filter if min_size or max_size specified
    """
    source_appendix_titles = await get_appendix_titles(language)

    def process_suggestion_result(title, result):
        if not (result and result.get("sections", {}).get("missing")):
            return None

        my_data = result["sections"]
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
                return None

        return result

    return process_suggestion_result


def create_section_suggestion_fetcher(source: str, target: str):
    """
    Creates a fetch function for section translation suggestions from CXServer.

    Sets up API configuration and returns a reusable async function that fetches
    section suggestions for article titles with bounded concurrency.
    """
    section_suggestion_api = f"{configuration.CXSERVER_URL}v2/suggest/sections/"
    headers = set_headers_with_host_header(configuration.CXSERVER_HEADER, source)
    semaphore = asyncio.Semaphore(configuration.API_CONCURRENCY_LIMIT)

    async def fetch_with_semaphore(recommendation_title: str):
        encoded_title = urllib.parse.quote(recommendation_title, safe="")
        url = f"{section_suggestion_api}{encoded_title}/{source}/{target}?include_section_sizes=true"

        async with semaphore:
            return await get(url, headers=headers, treat_404_as_error=False)

    return fetch_with_semaphore


async def get_section_suggestions_for_recommendations(
    recommendations: List[TranslationRecommendation],
    source_language: str,
    target_language: str,
    count,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    should_preserve_order: bool = False,
) -> List[SectionTranslationRecommendation]:
    """
    Fetches section translation suggestions for the given recommendations.

    Retrieves section suggestions that can be translated from source to target language,
    filtering by size constraints if specified.

    Args:
        recommendations: List of article recommendations to get section suggestions for.
        source_language (str): Source language code (e.g., "en").
        target_language (str): Target language code (e.g., "es").
        count (int): Maximum number of section suggestions to return.
        min_size (int, optional): Minimum section size in bytes. Defaults to None.
        max_size (int, optional): Maximum section size in bytes. Defaults to None.
        should_preserve_order (bool): If True, maintains input order; if False,
            returns fastest results first. Defaults to False.

    Returns:
        List[SectionTranslationRecommendation]: Section suggestions with source/target
            titles, missing sections, and collection metadata.
    """
    title_to_collection_map = {recommendation.title: recommendation.collection for recommendation in recommendations}
    titles = list(title_to_collection_map.keys())

    if should_preserve_order:
        results = await fetch_section_suggestions_ordered(
            source_language, target_language, titles, count, min_size, max_size
        )
    else:
        results = await fetch_section_suggestions_unordered(
            source_language, target_language, titles, count, min_size, max_size
        )

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


async def fetch_section_suggestions_unordered(
    source_language: str,
    target_language: str,
    candidate_titles: List[str],
    count: int,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
) -> List:
    """
    Fetches section translation suggestions from CXServer, returning fastest results first.

    Retrieves section suggestions for article titles in parallel, stopping once the count
    limit is reached. Results are returned in completion order (fastest-first), not input order.

    Returns:
        List[Dict]: Section suggestion dictionaries with the following fields:
            - sourceLanguage (str): Source language code
            - targetLanguage (str): Target language code
            - sourceTitle (str): Source article title
            - targetTitle (str): Target article title
            - sourceSections (list): Sections in source article
            - targetSections (list): Sections in target article
            - present (dict): Sections present in both articles
            - missing (dict): Sections missing in target article
            - sourceSectionSizes (dict): Size of each source section in bytes

    Note:
        - All fetch requests start immediately (no bounded startup)
        - Filters out appendix sections and applies size constraints
        - Cancels remaining requests once count limit is reached
        - Results are unordered; use fetch_section_suggestions_ordered for ordered results
    """
    if not candidate_titles:
        return []

    fetch_section = create_section_suggestion_fetcher(source_language, target_language)
    validate_result = await create_suggestion_validator(source_language, min_size, max_size)

    # Fire all tasks at once
    tasks = [asyncio.create_task(fetch_section(title)) for title in candidate_titles]
    results = []

    for task in asyncio.as_completed(tasks):
        try:
            result = await task
            result = validate_result(None, result)
            if result:
                results.append(result)
        except Exception as e:
            log.error(f"Error fetching section suggestions: {repr(e)}")

        if len(results) >= count:
            # Cancel remaining tasks
            [task.cancel() for task in tasks if not task.done()]
            break

    return results[:count]


async def fetch_section_suggestions_ordered(
    source_language: str,
    target_language: str,
    candidate_titles: List[str],
    count: int,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
) -> List:
    """
    Fetches section translation suggestions from CXServer, preserving input order.

    Retrieves section suggestions for article titles with bounded concurrency, maintaining
    the order of the input list. Only keeps (successful + pending) ≤ count tasks active
    at any time for efficiency.

    Returns:
        List[Dict]: Section suggestion dictionaries with the following fields:
            - sourceLanguage (str): Source language code
            - targetLanguage (str): Target language code
            - sourceTitle (str): Source article title
            - targetTitle (str): Target article title
            - sourceSections (list): Sections in source article
            - targetSections (list): Sections in target article
            - present (dict): Sections present in both articles
            - missing (dict): Sections missing in target article
            - sourceSectionSizes (dict): Size of each source section in bytes

    Note:
        - Maintains bounded concurrency: successful + pending ≤ count
        - Results preserve input order, unlike the unordered variant
        - Filters out appendix sections and applies size constraints
        - Stops fetching once count valid suggestions are found
    """
    if not candidate_titles:
        return []

    fetch_section_suggestion = create_section_suggestion_fetcher(source_language, target_language)
    validate_result = await create_suggestion_validator(source_language, min_size, max_size)

    return await collect_results_ordered(candidate_titles, fetch_section_suggestion, validate_result, count)
