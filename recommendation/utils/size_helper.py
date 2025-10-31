from typing import Optional


def matches_article_size_filter(size: int, min_size: Optional[int], max_size: Optional[int]) -> bool:
    """
    Check if an article's size matches the requested size filter.

    Args:
        size: Article size in bytes
        min_size: Minimum size in bytes, or None for no minimum
        max_size: Maximum size in bytes, or None for no maximum

    Returns:
        True if the article matches the filter or no filter is applied
    """
    if size is None:
        return False

    if min_size is not None and size < min_size:
        return False

    if max_size is not None and size > max_size:
        return False

    return True


def matches_section_size_filter(
    section_sizes: Optional[dict], min_size: Optional[int], max_size: Optional[int]
) -> bool:
    """
    Check if any section matches the requested size filter.

    Args:
        section_sizes: Dict mapping section titles to their sizes in bytes, or None if it could not be fetched
        min_size: Minimum size in bytes, or None for no minimum
        max_size: Maximum size in bytes, or None for no maximum

    Returns:
        True if any section matches the filter or no filter is applied
    """
    if section_sizes is None:
        return False

    if min_size is None and max_size is None:
        return True

    if not section_sizes:
        return True

    for size in section_sizes.values():
        if matches_article_size_filter(size, min_size, max_size):
            return True

    return False
