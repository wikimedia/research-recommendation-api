import asyncio
import random
from typing import List

from recommendation.api.translation.models import (
    RankMethodEnum,
)
from recommendation.utils.configuration import configuration
from recommendation.utils.lead_section_size_helper import get_lead_section_size
from recommendation.utils.logger import log
from recommendation.utils.size_helper import matches_section_size_filter


def sort_recommendations(recommendations, rank_method):
    if rank_method == RankMethodEnum.sitelinks:
        # Sort by langlinks count, from highest to lowest
        return sorted(recommendations, key=lambda x: x.langlinks_count, reverse=True)
    else:
        # shuffle recommendations
        return sorted(recommendations, key=lambda x: random.random())


async def filter_recommendations_by_lead_section_size(
    recommendations: List, language: str, min_size: int, max_size: int, max_results: int = None
) -> List:
    """
    Filters recommendations based on lead section size.

    Args:
        recommendations: List of recommendation objects with a 'title' attribute.
        language: Language code for fetching lead section sizes.
        min_size: Minimum allowed lead section size.
        max_size: Maximum allowed lead section size.
        max_results: Optional limit on the number of filtered recommendations.

    Returns:
        List of recommendation objects that match the size criteria,
        each with a 'lead_section_size' attribute set.
    """
    semaphore = asyncio.Semaphore(configuration.API_CONCURRENCY_LIMIT)

    async def fetch_size(rec):
        async with semaphore:
            title = rec["title"] if isinstance(rec, dict) else getattr(rec, "title", None)
            return rec, await get_lead_section_size(title, language)

    filtered_recommendations = []
    tasks = [asyncio.create_task(fetch_size(rec)) for rec in recommendations]

    for task in asyncio.as_completed(tasks):
        try:
            rec, size_dict = await task
            lead_size = list(size_dict.values())[0]  # assume single-key dict
            section_sizes = {"__LEAD_SECTION__": lead_size}
            if matches_section_size_filter(section_sizes, min_size, max_size):
                if hasattr(rec, "lead_section_size"):
                    rec.lead_section_size = lead_size
                else:
                    rec["lead_section_size"] = lead_size
                filtered_recommendations.append(rec)
        except Exception as e:
            log.error(f"Error fetching lead section size: {e}")

        if max_results and len(filtered_recommendations) >= max_results:
            # Cancel remaining tasks
            for t in tasks:
                if not t.done():
                    t.cancel()
            break

    return filtered_recommendations
