from typing import Optional

from recommendation.api.translation.models import DifficultyEnum
from recommendation.utils.configuration import configuration


def _get_difficulty_by_thresholds(
    size: int, easy_threshold: int, medium_threshold: int, hard_threshold: int
) -> Optional[DifficultyEnum]:
    """
    Helper function to determine difficulty level based on size and three thresholds.

    Args:
        size: Content size in bytes
        easy_threshold: Minimum size for easy difficulty
        medium_threshold: Minimum size for medium difficulty
        hard_threshold: Minimum size for hard difficulty

    Returns:
        DifficultyEnum or None if size is below easy threshold or invalid
    """
    if size is None or size < easy_threshold:
        return None
    elif size < medium_threshold:
        return DifficultyEnum.easy
    elif size < hard_threshold:
        return DifficultyEnum.medium
    else:
        return DifficultyEnum.hard


def get_article_difficulty(size: int) -> Optional[DifficultyEnum]:
    """
    Determine the difficulty level of an article based on its size in bytes.

    Args:
        size: Article size in bytes

    Returns:
        DifficultyEnum or None if size is invalid

    Note:
        Size in bytes is used to determine article complexity/length.
    """
    return _get_difficulty_by_thresholds(
        size,
        configuration.ARTICLE_EASY_THRESHOLD,
        configuration.ARTICLE_MEDIUM_THRESHOLD,
        configuration.ARTICLE_HARD_THRESHOLD,
    )


def matches_article_difficulty_filter(size: int, requested_difficulty: Optional[DifficultyEnum]) -> bool:
    """
    Check if an article's size matches the requested difficulty filter.

    Args:
        size: Article size in bytes
        requested_difficulty: The difficulty level to filter for, or None for no filtering

    Returns:
        True if the article matches the filter or no filter is applied
    """
    if requested_difficulty is None:
        return True

    article_difficulty = get_article_difficulty(size)
    return article_difficulty == requested_difficulty


def get_section_difficulty(size: int) -> Optional[DifficultyEnum]:
    """
    Determine the difficulty level of a section based on its size in bytes.

    Args:
        size: Section size in bytes

    Returns:
        DifficultyEnum or None if size is invalid
    """
    return _get_difficulty_by_thresholds(
        size,
        configuration.SECTION_EASY_THRESHOLD,
        configuration.SECTION_MEDIUM_THRESHOLD,
        configuration.SECTION_HARD_THRESHOLD,
    )


def matches_section_difficulty_filter(section_sizes: dict, requested_difficulty: Optional[DifficultyEnum]) -> bool:
    """
    Check if any section matches the requested difficulty filter.

    Args:
        section_sizes: Dict mapping section titles to their sizes in bytes
        requested_difficulty: The difficulty level to filter for, or None for no filtering

    Returns:
        True if any section matches the filter or no filter is applied
    """
    if requested_difficulty is None or not section_sizes:
        return True

    for size in section_sizes.values():
        section_difficulty = get_section_difficulty(size)
        if section_difficulty == requested_difficulty:
            return True

    return False
