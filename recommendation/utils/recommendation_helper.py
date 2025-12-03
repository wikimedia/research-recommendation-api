import asyncio
import random
from typing import Callable, List, Set

from recommendation.api.translation.models import (
    RankMethodEnum,
    SectionTranslationRecommendation,
    TranslationRecommendation,
)
from recommendation.utils.logger import log


async def collect_results_ordered(items: List, fetch_fn: Callable, process_fn: Callable, limit: int) -> List:
    """
    Fetches and processes items in parallel with bounded concurrency, preserving input order.

    This is a generic async utility that applies a fetch-process pipeline to a list of items.
    It maintains bounded concurrency by only keeping (successful + pending) ≤ limit tasks
    active at any time. Results maintain their original position in the input list, even
    though tasks complete in arbitrary order.

    Args:
        items (List): List of items to fetch and process. Can be any type that fetch_fn accepts.
        fetch_fn (Callable): Async function that takes an item and returns raw data.
            Signature: async def fetch_fn(item) -> raw_result
        process_fn (Callable): Sync function that validates/transforms fetched data.
            Should return the processed item if valid, or None to filter it out.
            Signature: def process_fn(item, raw_result) -> processed_item | None
        limit (int): Maximum number of successful (non-None) results to return.
            Also controls maximum concurrent tasks: successful + pending ≤ limit.

    Returns:
        List: Processed items that passed validation (process_fn returned non-None),
            in the same order as the input list. Length ≤ limit.

    Note:
        - Failed fetches are logged but don't stop processing
        - Process function can filter by returning None
        - Use this when order matters; use asyncio.as_completed for speed

    See Also:
        filter_recommendations_by_lead_section_size_ordered: Specialized use case
    """
    if not items:
        return []

    items_length = len(items)
    total_limit = min(limit, items_length)
    ordered_results = [None] * items_length

    running_tasks = {i: asyncio.create_task(fetch_fn(items[i])) for i in range(total_limit)}

    task_to_idx = {task: i for i, task in running_tasks.items()}
    next_to_start = total_limit

    successful = 0

    while running_tasks and successful < total_limit:
        done, _ = await asyncio.wait(
            running_tasks.values(),
            return_when=asyncio.FIRST_COMPLETED,
        )

        for finished in done:
            idx = task_to_idx.pop(finished)
            del running_tasks[idx]

            try:
                raw_result = await finished
                processed = process_fn(items[idx], raw_result)
                if processed is not None:
                    ordered_results[idx] = processed
                    successful += 1
            except Exception as e:
                log.error(f"Error in ordered fetch: {repr(e)}")

            if successful >= total_limit:
                break

            if next_to_start < items_length and successful + len(running_tasks) < total_limit:
                new_task = asyncio.create_task(fetch_fn(items[next_to_start]))
                running_tasks[next_to_start] = new_task
                task_to_idx[new_task] = next_to_start
                next_to_start += 1

    for task in running_tasks.values():
        task.cancel()

    return [result for result in ordered_results if result is not None][:total_limit]


def sort_recommendations(recommendations, rank_method):
    if rank_method == RankMethodEnum.sitelinks:
        # Sort by langlinks count, from highest to lowest
        return sorted(recommendations, key=lambda x: x.langlinks_count, reverse=True)
    else:
        # shuffle recommendations
        return sorted(recommendations, key=lambda x: random.random())


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
