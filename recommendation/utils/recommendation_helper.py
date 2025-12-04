import asyncio
import random
from typing import List, Set

from recommendation.api.translation.models import (
    RankMethodEnum,
    SectionTranslationRecommendation,
    TranslationRecommendation,
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
            log.error(f"Error fetching lead section size: {repr(e)}")

        if max_results and len(filtered_recommendations) >= max_results:
            # Cancel remaining tasks
            for t in tasks:
                if not t.done():
                    t.cancel()
            break

    return filtered_recommendations


def do_interleave_recommendations(
    primary: List[TranslationRecommendation | SectionTranslationRecommendation],
    featured: List[TranslationRecommendation | SectionTranslationRecommendation],
    featured_positions: List[int],
) -> List[TranslationRecommendation | SectionTranslationRecommendation]:
    """
    Merges two recommendation lists by inserting featured items at specific positions.

    Takes two lists of recommendations and interleaves them according to precomputed
    positions, ensuring no duplicates appear in the result. Featured items are inserted
    at their designated positions, with primary items filling the remaining slots.

    Args:
        primary (List[TranslationRecommendation]): Base list of recommendations that
            forms the backbone of the result.
        featured (List[TranslationRecommendation]): Special recommendations to be
            inserted at specific positions (e.g., promoted or curated content).
        featured_positions (List[int]): Indices where featured items should be inserted
            into the result list. Must have length ≤ len(featured).

    Returns:
        List[TranslationRecommendation]: Interleaved list with featured items at their
            designated positions and primary items in remaining slots, with duplicates
            removed.

    Note:
        - Duplicates between primary and featured are automatically removed
        - Featured items take precedence if a duplicate exists
        - Order of primary items is preserved in non-featured positions
    """
    result: List[TranslationRecommendation | SectionTranslationRecommendation] = []
    seen: Set[TranslationRecommendation | SectionTranslationRecommendation] = set()
    featured_index = 0
    total_featured = len(featured)

    for position, primary_item in enumerate(primary):
        # Insert featured item first if this position requires it
        if position in featured_positions and featured_index < total_featured:
            featured_item = featured[featured_index]
            if featured_item not in seen:
                result.append(featured_item)
                seen.add(featured_item)
            featured_index += 1

        # Now insert primary item
        if primary_item not in seen:
            result.append(primary_item)
            seen.add(primary_item)

    return result


def interleave_by_ratio(
    primary_recommendations: List[TranslationRecommendation | SectionTranslationRecommendation],
    featured_recommendations: List[TranslationRecommendation | SectionTranslationRecommendation],
    ratio: float = 0.5,
) -> List[TranslationRecommendation | SectionTranslationRecommendation]:
    """
    Interleaves two recommendation lists according to a specified ratio.

    Merges primary and featured recommendations by distributing featured items
    evenly throughout the result based on the ratio parameter. Truncates lists
    to equal length for interleaving, then appends remaining items.

    Args:
        primary_recommendations (List): Base list of
            recommendations that forms the majority of the result.
        featured_recommendations (List): Special
            recommendations to be distributed throughout the result.
        ratio (float): Target proportion of featured items in the interleaved portion.
            Must be between 0 and 1. For example, 0.5 means aim for 50% featured items.
            Defaults to 0.5.

    Returns:
        List[TranslationRecommendation|SectionTranslationRecommendation]: Merged list with featured items evenly
            distributed, followed by any leftover items from either list.

    Algorithm:
        1. Edge cases: Returns appropriate list if ratio is 0, 1, or lists are empty
        2. Truncates both lists to the length of the shorter one
        3. Calculates evenly-spaced positions for featured items based on ratio
        4. Interleaves the truncated lists with featured items at computed positions
        5. Appends leftover items from both lists (duplicates removed)

    Note:
        - Ratio determines featured item density: ratio / (1 - ratio)
        - Duplicates between lists are automatically removed (by title)
        - Featured items take precedence if duplicates exist
        - Leftover items maintain their original order
    """
    # Edge cases
    if ratio <= 0 or not featured_recommendations:
        return primary_recommendations
    if ratio >= 1 or not primary_recommendations:
        return featured_recommendations

    # Truncate both lists to the shorter length for interleaving
    min_length = min(len(primary_recommendations), len(featured_recommendations))
    truncated_primary = primary_recommendations[:min_length]
    truncated_featured = featured_recommendations[:min_length]

    leftover_items = primary_recommendations[min_length:] + featured_recommendations[min_length:]

    # Calculate number of featured items to insert during interleaving
    num_featured_to_insert = min(round(min_length * ratio / (1 - ratio)), min_length)

    # Compute evenly-spaced positions for featured items
    spacing_step = (min_length + 1) / (num_featured_to_insert + 1)
    featured_positions = [round(spacing_step * (k + 1)) - 1 for k in range(num_featured_to_insert)]

    # Interleave truncated lists with featured items at computed positions
    result = do_interleave_recommendations(truncated_primary, truncated_featured, featured_positions)

    # Append leftover items, avoiding duplicates
    seen_titles = {rec.title for rec in result}
    for item in leftover_items:
        if item.title not in seen_titles:
            result.append(item)
            seen_titles.add(item.title)

    return result
