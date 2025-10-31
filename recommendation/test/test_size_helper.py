from recommendation.utils.size_helper import (
    matches_article_size_filter,
    matches_section_size_filter,
)


class TestMatchesArticleSizeFilter:
    def test_no_filter_returns_true(self):
        assert matches_article_size_filter(1000, None, None) is True

    def test_none_size_returns_false(self):
        assert matches_article_size_filter(None, None, None) is False

    def test_min_size_filter_matches(self):
        assert matches_article_size_filter(1000, 500, None) is True

    def test_min_size_filter_does_not_match(self):
        assert matches_article_size_filter(1000, 1500, None) is False

    def test_max_size_filter_matches(self):
        assert matches_article_size_filter(1000, None, 1500) is True

    def test_max_size_filter_does_not_match(self):
        assert matches_article_size_filter(1000, None, 500) is False

    def test_min_and_max_size_filter_matches(self):
        assert matches_article_size_filter(1000, 500, 1500) is True

    def test_min_and_max_size_filter_too_small(self):
        assert matches_article_size_filter(300, 500, 1500) is False

    def test_min_and_max_size_filter_too_large(self):
        assert matches_article_size_filter(2000, 500, 1500) is False

    def test_exactly_at_min_size(self):
        assert matches_article_size_filter(1000, 1000, None) is True

    def test_exactly_at_max_size(self):
        assert matches_article_size_filter(1000, None, 1000) is True

    def test_exactly_at_both_bounds(self):
        assert matches_article_size_filter(1000, 1000, 1000) is True


class TestMatchesSectionSizeFilter:
    def test_no_filter_returns_true(self):
        section_sizes = {"section1": 1000}
        assert matches_section_size_filter(section_sizes, None, None) is True

    def test_empty_sections_returns_true(self):
        assert matches_section_size_filter({}, 1000, 2000) is True

    def test_none_sections_returns_false(self):
        assert matches_section_size_filter(None, 1000, 2000) is False

    def test_none_sections_with_no_filter_returns_false(self):
        assert matches_section_size_filter(None, None, None) is False

    def test_min_size_filter_matches(self):
        section_sizes = {"section1": 1000}
        assert matches_section_size_filter(section_sizes, 500, None) is True

    def test_min_size_filter_does_not_match(self):
        section_sizes = {"section1": 1000}
        assert matches_section_size_filter(section_sizes, 1500, None) is False

    def test_max_size_filter_matches(self):
        section_sizes = {"section1": 1000}
        assert matches_section_size_filter(section_sizes, None, 1500) is True

    def test_max_size_filter_does_not_match(self):
        section_sizes = {"section1": 1000}
        assert matches_section_size_filter(section_sizes, None, 500) is False

    def test_mixed_sections_any_match_returns_true(self):
        # If any section matches the filter, should return True
        section_sizes = {
            "small": 300,  # too small
            "medium": 1000,  # matches
            "large": 2000,  # too large
        }
        assert matches_section_size_filter(section_sizes, 500, 1500) is True

    def test_no_sections_match_filter(self):
        section_sizes = {
            "small1": 100,
            "small2": 200,
        }
        assert matches_section_size_filter(section_sizes, 500, 1500) is False

    def test_multiple_sections_within_range(self):
        section_sizes = {
            "section1": 600,
            "section2": 800,
            "section3": 1200,
        }
        assert matches_section_size_filter(section_sizes, 500, 1500) is True

    def test_exactly_at_min_size(self):
        section_sizes = {"section1": 1000}
        assert matches_section_size_filter(section_sizes, 1000, None) is True

    def test_exactly_at_max_size(self):
        section_sizes = {"section1": 1000}
        assert matches_section_size_filter(section_sizes, None, 1000) is True

    def test_exactly_at_both_bounds(self):
        section_sizes = {"section1": 1000}
        assert matches_section_size_filter(section_sizes, 1000, 1000) is True
