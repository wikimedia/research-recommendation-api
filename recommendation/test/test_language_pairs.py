from recommendation.utils.language_pairs import is_missing_in_target_language


def test_is_missing_in_target_language():
    available_languages = ["en", "es", "fr", "nb", "bho", "be-x-old"]
    assert not is_missing_in_target_language("nb", available_languages)
    assert not is_missing_in_target_language("no", available_languages)
    assert not is_missing_in_target_language("bho", available_languages)
    assert not is_missing_in_target_language("bh", available_languages)
    assert is_missing_in_target_language("ml", available_languages)
    assert not is_missing_in_target_language("be-tarask", available_languages)
    assert not is_missing_in_target_language("be-x-old", available_languages)
