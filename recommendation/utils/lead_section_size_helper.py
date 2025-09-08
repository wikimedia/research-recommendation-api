import asyncio
from typing import Dict, List, Optional

from recommendation.api.translation.models import TranslationRecommendation
from recommendation.external_data.fetcher import get, get_endpoint_and_headers
from recommendation.utils.logger import log


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
        "page": page_title,  # we assume section_title is also the page title
    }

    try:
        response = await get(endpoint, params=params, headers=headers)
    except ValueError:
        log.error(f"Could not fetch section sizes for page {page_title} and language {lang}")
        return None

    if "parse" not in response or "sections" not in response["parse"]:
        log.error(f"Could not fetch section sizes for page {page_title} and language {lang}")
        return None

    sections = response["parse"]["sections"]

    return {page_title: sections[0]["byteoffset"]}


async def add_lead_section_sizes_to_recommendations(
    recommendations: List[TranslationRecommendation], language: str
) -> List[TranslationRecommendation]:
    """
    Concurrently fetch lead section sizes and assign them to TranslationRecommendation models.
    """
    tasks = [get_lead_section_size(rec.title, language) for rec in recommendations]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for rec, result in zip(recommendations, results):
        if isinstance(result, Exception):
            # log the error and skip
            log.error(f"Error fetching lead section size for {rec.title}: {result}")
            continue
        if result and rec.title in result:
            rec.lead_section_size = result[rec.title]

    return recommendations
