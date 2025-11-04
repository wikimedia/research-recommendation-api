from recommendation.utils.language_codes import is_missing_in_target_language


def test_is_missing_in_target_language():
    available_languages = [
        "en",
        "es",
        "be-x-old",
        "bh",
        "als",
        "zh-classical",
        "zh-min-nan",
        "nb",
        "roa-rup",
        "bat-smg",
        "fiu-vro",
        "zh-yue",
    ]
    assert not is_missing_in_target_language("en", available_languages)
    assert not is_missing_in_target_language("nb", available_languages)
    assert not is_missing_in_target_language("bho", available_languages)
    assert not is_missing_in_target_language("gsw", available_languages)
    assert not is_missing_in_target_language("lzh", available_languages)
    assert not is_missing_in_target_language("nan", available_languages)
    assert not is_missing_in_target_language("rup", available_languages)
    assert not is_missing_in_target_language("sgs", available_languages)
    assert not is_missing_in_target_language("vro", available_languages)
    assert not is_missing_in_target_language("yue", available_languages)
    assert is_missing_in_target_language("ml", available_languages)
    assert not is_missing_in_target_language("be-tarask", available_languages)
