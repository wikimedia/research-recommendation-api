from recommendation.api.translation.models import DifficultyEnum
from recommendation.utils.configuration import configuration
from recommendation.utils.difficulty_helper import (
    get_article_difficulty,
    get_section_difficulty,
    matches_article_difficulty_filter,
    matches_section_difficulty_filter,
)


class TestGetArticleDifficulty:
    def test_stub_below_easy_threshold(self):
        # Articles below easy threshold should return None (stubs)
        stub_size = configuration.ARTICLE_EASY_THRESHOLD - 1
        assert get_article_difficulty(stub_size) is None

    def test_easy_at_threshold(self):
        # Articles at easy threshold should be easy
        assert get_article_difficulty(configuration.ARTICLE_EASY_THRESHOLD) == DifficultyEnum.easy

    def test_easy_below_medium_threshold(self):
        # Articles just below medium threshold should be easy
        easy_size = configuration.ARTICLE_MEDIUM_THRESHOLD - 1
        assert get_article_difficulty(easy_size) == DifficultyEnum.easy

    def test_medium_at_threshold(self):
        # Articles at medium threshold should be medium
        assert get_article_difficulty(configuration.ARTICLE_MEDIUM_THRESHOLD) == DifficultyEnum.medium

    def test_medium_below_hard_threshold(self):
        # Articles just below hard threshold should be medium
        medium_size = configuration.ARTICLE_HARD_THRESHOLD - 1
        assert get_article_difficulty(medium_size) == DifficultyEnum.medium

    def test_hard_at_threshold(self):
        # Articles at hard threshold should be hard
        assert get_article_difficulty(configuration.ARTICLE_HARD_THRESHOLD) == DifficultyEnum.hard

    def test_hard_above_threshold(self):
        # Articles well above hard threshold should be hard
        hard_size = configuration.ARTICLE_HARD_THRESHOLD * 2
        assert get_article_difficulty(hard_size) == DifficultyEnum.hard

    def test_zero_size(self):
        assert get_article_difficulty(0) is None

    def test_negative_size(self):
        assert get_article_difficulty(-100) is None

    def test_none_size(self):
        assert get_article_difficulty(None) is None


class TestGetSectionDifficulty:
    def test_stub_below_easy_threshold(self):
        # Sections below easy threshold should return None (stubs)
        stub_size = configuration.SECTION_EASY_THRESHOLD - 1
        assert get_section_difficulty(stub_size) is None

    def test_easy_at_threshold(self):
        # Sections at easy threshold should be easy
        assert get_section_difficulty(configuration.SECTION_EASY_THRESHOLD) == DifficultyEnum.easy

    def test_easy_below_medium_threshold(self):
        # Sections just below medium threshold should be easy
        easy_size = configuration.SECTION_MEDIUM_THRESHOLD - 1
        assert get_section_difficulty(easy_size) == DifficultyEnum.easy

    def test_medium_at_threshold(self):
        # Sections at medium threshold should be medium
        assert get_section_difficulty(configuration.SECTION_MEDIUM_THRESHOLD) == DifficultyEnum.medium

    def test_medium_below_hard_threshold(self):
        # Sections just below hard threshold should be medium
        medium_size = configuration.SECTION_HARD_THRESHOLD - 1
        assert get_section_difficulty(medium_size) == DifficultyEnum.medium

    def test_hard_at_threshold(self):
        # Sections at hard threshold should be hard
        assert get_section_difficulty(configuration.SECTION_HARD_THRESHOLD) == DifficultyEnum.hard

    def test_hard_above_threshold(self):
        # Sections well above hard threshold should be hard
        hard_size = configuration.SECTION_HARD_THRESHOLD * 2
        assert get_section_difficulty(hard_size) == DifficultyEnum.hard

    def test_zero_size(self):
        assert get_section_difficulty(0) is None

    def test_negative_size(self):
        assert get_section_difficulty(-100) is None

    def test_none_size(self):
        assert get_section_difficulty(None) is None


class TestMatchesArticleDifficultyFilter:
    def test_no_filter_returns_true(self):
        # Any size should match when no filter is applied
        test_size = configuration.ARTICLE_EASY_THRESHOLD + 100
        assert matches_article_difficulty_filter(test_size, None) is True

    def test_easy_article_matches_easy_filter(self):
        easy_size = configuration.ARTICLE_EASY_THRESHOLD + 100
        assert matches_article_difficulty_filter(easy_size, DifficultyEnum.easy) is True

    def test_medium_article_matches_medium_filter(self):
        medium_size = configuration.ARTICLE_MEDIUM_THRESHOLD + 100
        assert matches_article_difficulty_filter(medium_size, DifficultyEnum.medium) is True

    def test_hard_article_matches_hard_filter(self):
        hard_size = configuration.ARTICLE_HARD_THRESHOLD + 100
        assert matches_article_difficulty_filter(hard_size, DifficultyEnum.hard) is True

    def test_easy_article_does_not_match_medium_filter(self):
        easy_size = configuration.ARTICLE_EASY_THRESHOLD + 100
        assert matches_article_difficulty_filter(easy_size, DifficultyEnum.medium) is False

    def test_medium_article_does_not_match_easy_filter(self):
        medium_size = configuration.ARTICLE_MEDIUM_THRESHOLD + 100
        assert matches_article_difficulty_filter(medium_size, DifficultyEnum.easy) is False

    def test_hard_article_does_not_match_easy_filter(self):
        hard_size = configuration.ARTICLE_HARD_THRESHOLD + 100
        assert matches_article_difficulty_filter(hard_size, DifficultyEnum.easy) is False

    def test_stub_article_does_not_match_any_filter(self):
        stub_size = configuration.ARTICLE_EASY_THRESHOLD - 1
        assert matches_article_difficulty_filter(stub_size, DifficultyEnum.easy) is False
        assert matches_article_difficulty_filter(stub_size, DifficultyEnum.medium) is False
        assert matches_article_difficulty_filter(stub_size, DifficultyEnum.hard) is False

    def test_zero_size_does_not_match_any_filter(self):
        assert matches_article_difficulty_filter(0, DifficultyEnum.easy) is False

    def test_none_size_does_not_match_any_filter(self):
        assert matches_article_difficulty_filter(None, DifficultyEnum.easy) is False


class TestMatchesSectionDifficultyFilter:
    def test_no_filter_returns_true(self):
        section_sizes = {"section1": configuration.SECTION_EASY_THRESHOLD + 100}
        assert matches_section_difficulty_filter(section_sizes, None) is True

    def test_empty_sections_returns_true(self):
        assert matches_section_difficulty_filter({}, DifficultyEnum.easy) is True
        assert matches_section_difficulty_filter({}, None) is True

    def test_easy_section_matches_easy_filter(self):
        easy_size = configuration.SECTION_EASY_THRESHOLD + 100
        section_sizes = {"section1": easy_size}
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.easy) is True

    def test_medium_section_matches_medium_filter(self):
        medium_size = configuration.SECTION_MEDIUM_THRESHOLD + 100
        section_sizes = {"section1": medium_size}
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.medium) is True

    def test_hard_section_matches_hard_filter(self):
        hard_size = configuration.SECTION_HARD_THRESHOLD + 100
        section_sizes = {"section1": hard_size}
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.hard) is True

    def test_mixed_sections_any_match_returns_true(self):
        # If any section matches the filter, should return True
        section_sizes = {
            "stub": configuration.SECTION_EASY_THRESHOLD - 1,  # stub (no difficulty)
            "easy": configuration.SECTION_EASY_THRESHOLD + 100,  # easy
            "medium": configuration.SECTION_MEDIUM_THRESHOLD + 100,  # medium
        }
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.easy) is True
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.medium) is True

    def test_no_sections_match_filter(self):
        # Only stub sections should not match any difficulty filter
        section_sizes = {
            "stub1": configuration.SECTION_EASY_THRESHOLD - 1,
            "stub2": configuration.SECTION_EASY_THRESHOLD - 50,
        }
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.easy) is False
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.medium) is False
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.hard) is False

    def test_easy_sections_do_not_match_medium_filter(self):
        easy_size = configuration.SECTION_EASY_THRESHOLD + 100
        section_sizes = {"section1": easy_size}
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.medium) is False

    def test_medium_sections_do_not_match_easy_filter(self):
        medium_size = configuration.SECTION_MEDIUM_THRESHOLD + 100
        section_sizes = {"section1": medium_size}
        assert matches_section_difficulty_filter(section_sizes, DifficultyEnum.easy) is False
