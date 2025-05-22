import pytest

from recommendation.utils.search_query_builder import build_search_query


@pytest.mark.parametrize(
    "prefix,value,search_query",
    [
        ("articletopic", "arts|books|sports", "articletopic:arts|books|sports"),  # OR
        ("articlecountry", "usa+can+mex", "articlecountry:usa articlecountry:can articlecountry:mex"),  # AND
        ("articlecountry", "fra|esp+ita", "articlecountry:fra|esp articlecountry:ita"),  # OR AND
        ("articletopic", "  space  ", "articletopic:space"),  # leading/trailing spaces
        ("articletopic", "", ""),  # no value
        ("articlecountry", None, ""),  # no value
        ("foo", "bar", ""),  # unrecognized prefix
    ],
)
def test_build_search_query(prefix, value, search_query):
    """
    Test the build_search_query function with various inputs.


    Args:
        prefix (str): The prefix to use in the search query.
        value (str): The value to use in the search query.
        search_query (str): The expected output of the search query.
    """
    assert build_search_query(prefix, value) == search_query
