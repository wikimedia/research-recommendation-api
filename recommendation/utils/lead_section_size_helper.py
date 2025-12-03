import asyncio
from typing import Callable, Dict, List, Optional

from recommendation.api.translation.models import TranslationRecommendation
from recommendation.external_data.fetcher import get, get_endpoint_and_headers
from recommendation.utils.configuration import configuration
from recommendation.utils.logger import log
from recommendation.utils.recommendation_helper import collect_results_ordered
from recommendation.utils.size_helper import matches_section_size_filter


async def get_lead_section_size(page_title: str, lang: str) -> Optional[Dict[str, int]]:
    """
    Fetch the size of the lead section of a given page.

    Args:
        page_title (str): The title of the page to retrieve the lead section size from.
        lang (str): The page language code

    Returns:
        Optional[Dict[str, int]]: A dictionary containing the page title as the key and the size of the
        lead section in bytes as the value.
        Returns None if the page information cannot be fetched.
    """
    endpoint, headers = get_endpoint_and_headers(lang)

    params = {
        "action": "parse",
        "format": "json",
        "formatversion": 2,
        "prop": "sections",
        "redirects": True,
        "page": page_title,
    }

    try:
        response = await get(endpoint, params=params, headers=headers)
    except ValueError as e:
        log.error(f"Could not fetch section sizes for page {page_title} and language {lang}: {repr(e)}")
        return None

    if "parse" not in response or "sections" not in response["parse"]:
        log.error(f"Invalid response from fetch section sizes for page {page_title} and language {lang}")
        return None

    sections = response["parse"]["sections"]
    if not sections:
        log.error(f"No sections returned for page {page_title} and language {lang}")
        return None

    return {page_title: sections[0]["byteoffset"]}


async def add_lead_section_sizes_to_recommendations(
    recommendations: List[TranslationRecommendation], language: str
) -> List[TranslationRecommendation]:
    """
    Concurrently fetch lead section sizes and assign them to TranslationRecommendation models.
    """
    tasks = [get_lead_section_size(rec.title, language) for rec in recommendations]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for rec, result in zip(recommendations, results, strict=True):
        if isinstance(result, Exception):
            # log the error and skip
            log.error(f"Error fetching lead section size for {rec.title}: {result}")
            continue
        if result and rec.title in result:
            rec.lead_section_size = result[rec.title]

    return recommendations


async def filter_recommendations_by_lead_section_size(
    recommendations: List[TranslationRecommendation],
    language: str,
    min_size: int,
    max_size: int,
    max_results: int = None,
    should_preserve_order: bool = False,
) -> List:
    """
    Filters recommendations based on lead section size.

    Args:
        recommendations: List of recommendation objects with a 'title' attribute.
        language: Language code for fetching lead section sizes.
        min_size: Minimum allowed lead section size.
        max_size: Maximum allowed lead section size.
        max_results: Optional limit on the number of filtered recommendations.
        should_preserve_order: Whether to preserve order of recommendations.

    Returns:
        List of recommendation objects that match the size criteria,
        each with a 'lead_section_size' attribute set.
    """
    if should_preserve_order:
        filtered_recommendations = await filter_recommendations_by_lead_section_size_ordered(
            recommendations,
            language,
            min_size,
            max_size,
            max_results,
        )
    else:
        filtered_recommendations = await filter_recommendations_by_lead_section_size_unordered(
            recommendations,
            language,
            min_size,
            max_size,
            max_results,
        )

    return filtered_recommendations


def create_lead_section_fetcher(language: str) -> Callable:
    """
    Creates a fetch function for lead section sizes with shared semaphore.
    Args:
        language: Language code for fetching sizes

    Returns:
        Async function that fetches lead section size for a recommendation
    """
    semaphore = asyncio.Semaphore(configuration.API_CONCURRENCY_LIMIT)

    async def fetch_size(rec) -> Optional[Dict[str, int]]:
        async with semaphore:
            title = rec["title"] if isinstance(rec, dict) else getattr(rec, "title", None)
            return await get_lead_section_size(title, language)

    return fetch_size


def create_lead_section_result_processor(min_size: int, max_size: int):
    """
    Creates a processor function for filtering lead section fetch results by size.

    Args:
        min_size (int): Minimum allowed lead section size in bytes.
        max_size (int): Maximum allowed lead section size in bytes.

    Returns:
        callable: A processor function that takes (rec, size_dict) and returns
                  the recommendation with lead_section_size set if it passes
                  the size filter, otherwise None.

    Note:
        The returned processor mutates the recommendation object by adding
        the lead_section_size attribute if the filter passes.
    """

    def process_result(rec, size_dict: Optional[Dict[str, int]]):
        if not size_dict or not isinstance(size_dict, dict):
            return None

        lead_size = list(size_dict.values())[0]
        section_sizes = {"__LEAD_SECTION__": lead_size}

        if not matches_section_size_filter(section_sizes, min_size, max_size):
            return None

        if hasattr(rec, "lead_section_size"):
            rec.lead_section_size = lead_size
        else:
            rec["lead_section_size"] = lead_size

        return rec

    return process_result


async def filter_recommendations_by_lead_section_size_ordered(
    recommendations: List,
    language: str,
    min_size: int,
    max_size: int,
    max_results: int = None,
) -> List:
    """
    Filters recommendations based on lead section size, preserving input order.

    Fetches lead section sizes in parallel with bounded concurrency, returning
    only recommendations whose lead sections fall within the specified size range.
    The order of recommendations in the input list is preserved in the output.

    Returns:
        List: Filtered recommendations that match the size criteria, each with a
            'lead_section_size' attribute added. Order matches input order.
    """
    if not recommendations:
        return []

    fetch_size = create_lead_section_fetcher(language)
    process_lead_section_result = create_lead_section_result_processor(min_size, max_size)

    return await collect_results_ordered(recommendations, fetch_size, process_lead_section_result, max_results)


async def filter_recommendations_by_lead_section_size_unordered(
    recommendations: List[TranslationRecommendation],
    language: str,
    min_size: int,
    max_size: int,
    max_results: int = None,
) -> List:
    """
    Filters recommendations based on lead section size, returning fastest results first.

    Fetches lead section sizes for all recommendations in parallel, returning results
    as they complete. Unlike the ordered variant, this does not preserve input order
    but may complete faster by returning quick responses immediately.

    Returns:
        List: Filtered recommendations that match the size criteria, each with a
            'lead_section_size' attribute added. Results are ordered by completion
            time, not input order.
    """
    if not recommendations:
        return []

    fetch_size = create_lead_section_fetcher(language)
    process_lead_section_result = create_lead_section_result_processor(min_size, max_size)

    tasks = [asyncio.create_task(fetch_size(rec)) for rec in recommendations]
    title_to_recommendation_map = {rec.title: rec for rec in recommendations}
    filtered_recommendations = []

    for task in asyncio.as_completed(tasks):
        try:
            size_dict = await task
            # size_dict is a dict in this format: { "Moon": 1000 }
            title = list(size_dict.keys())[0]
            rec = title_to_recommendation_map[title]
            result = process_lead_section_result(rec, size_dict)
            if result is not None:
                filtered_recommendations.append(result)
        except Exception as e:
            log.error(f"Error fetching lead section size: {repr(e)}")

        if max_results and len(filtered_recommendations) >= max_results:
            # Cancel remaining tasks
            for t in tasks:
                if not t.done():
                    t.cancel()
            break

    return filtered_recommendations
