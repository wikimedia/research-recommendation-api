import recommendation.utils.sitematrix_helper as sm_helper
from recommendation.utils.sitematrix_helper import get_dbname_by_prefix, get_language_by_dbname, get_language_by_prefix

# Set the caches directly
sm_helper.cached_interwiki_map = [
    {"prefix": "en", "url": "https://en.wikipedia.org/wiki/$1"},
    {"prefix": "fr", "url": "https://fr.wikipedia.org/wiki/$1"},
    {"prefix": "de", "url": "https://de.wikipedia.org/wiki/$1"},
    {"prefix": "yue", "url": "https://zh-yue.wikipedia.org/wiki/$1"},
    {"prefix": "zh-yue", "url": "https://zh-yue.wikipedia.org/wiki/$1"},
]

sm_helper.cached_sitematrix = [
    {
        "code": "en",
        "site": [{"url": "https://en.wikipedia.org", "dbname": "enwiki"}],
    },
    {
        "code": "fr",
        "site": [{"url": "https://fr.wikipedia.org", "dbname": "frwiki"}],
    },
    {
        "code": "de",
        "site": [{"url": "https://de.wikipedia.org", "dbname": "dewiki"}],
    },
    {
        "code": "yue",
        "site": [{"url": "https://zh-yue.wikipedia.org", "dbname": "zh_yuewiki"}],
    },
    {"code": "zh-yue", "site": []},
]


def test_get_dbname_by_prefix():
    """
    Test get_dbname_by_prefix using known prefixes to validate dbnames from interwiki_map and sitematrix caches.
    """
    test_cases = {"en": "enwiki", "fr": "frwiki", "de": "dewiki", "zh-yue": "zh_yuewiki", "yue": "zh_yuewiki"}

    for prefix, expected_dbname in test_cases.items():
        dbname = get_dbname_by_prefix(prefix)
        assert dbname == expected_dbname, (
            f"Expected dbname '{expected_dbname}' for prefix '{prefix}', but got '{dbname}' instead."
        )

    # Test an unknown prefix to ensure the function handles it correctly
    unknown_prefix = "zzz"
    dbname = get_dbname_by_prefix(unknown_prefix)
    assert dbname is None, f"Expected None for unknown prefix '{unknown_prefix}', but got '{dbname}'"


def test_get_language_by_prefix():
    """
    Test get_language_by_prefix using known prefixes to validate lang codes from interwiki_map and sitematrix caches.
    """
    test_cases = {"en": "en", "fr": "fr", "de": "de", "zh-yue": "yue", "yue": "yue"}

    for prefix, expected_code in test_cases.items():
        code = get_language_by_prefix(prefix)
        assert code == expected_code, (
            f"Expected language code {expected_code} for prefix '{prefix}', but '{code}' returned"
        )

    # Test an unknown prefix
    unknown_prefix = "zzz"
    code = get_language_by_prefix(unknown_prefix)
    assert code is None, f"Expected None for unknown prefix '{unknown_prefix}', but got '{code}'"


def test_get_language_by_dbname():
    """
    Test get_language_by_dbname using known dbnames to validate lang codes from interwiki_map and sitematrix caches.
    """
    test_cases = {
        "enwiki": "en",
        "frwiki": "fr",
        "dewiki": "de",
        "zh_yuewiki": "yue",
    }

    for dbname, expected_code in test_cases.items():
        code = get_language_by_dbname(dbname)
        assert code == expected_code, (
            f"Expected language code {expected_code} for dbname '{dbname}', but '{code}' returned"
        )

    # Test an unknown dbname
    unknown_dbname = "unknownwiki"
    code = get_language_by_dbname(unknown_dbname)
    assert code is None, f"Expected None for unknown dbname '{unknown_dbname}', but got '{code}'"
