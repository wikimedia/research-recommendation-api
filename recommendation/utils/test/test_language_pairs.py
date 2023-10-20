import pytest
import responses

from recommendation.utils import language_pairs
from recommendation.utils import configuration

LANGUAGE_PAIRS = {"source": ["aa", "bb"], "target": ["cc", "dd"]}


def setup_function(function):
    language_pairs._language_pairs = None
    responses.add(
        responses.GET,
        configuration.get_config_value("endpoints", "language_pairs"),
        json=LANGUAGE_PAIRS,
        status=200,
    )


@pytest.mark.parametrize("source", LANGUAGE_PAIRS["source"])
@pytest.mark.parametrize("target", LANGUAGE_PAIRS["target"])
def test_language_pairs_valid(source, target):
    assert True is language_pairs.is_valid_language_pair(source, target)


@pytest.mark.parametrize(
    "source,target",
    [
        ("xx", LANGUAGE_PAIRS["target"][0]),
        (LANGUAGE_PAIRS["source"][0], "xx"),
        ("xx", "xx"),
    ],
)
def test_language_pairs_invalid(source, target):
    assert False is language_pairs.is_valid_language_pair(source, target)


def test_language_pairs_valid_only_fetches_once():
    assert 0 == len(responses.calls)
    assert True is language_pairs.is_valid_language_pair(
        LANGUAGE_PAIRS["source"][0], LANGUAGE_PAIRS["target"][0]
    )
    assert 1 == len(responses.calls)
    assert True is language_pairs.is_valid_language_pair(
        LANGUAGE_PAIRS["source"][0], LANGUAGE_PAIRS["target"][0]
    )
    assert 1 == len(responses.calls)


@pytest.mark.parametrize(
    "json_value",
    [
        "This isn't valid json and contains { weird _ // characters :;[]}|\\",
        ["it should be a dict"],
        {"there should be source and target keys": 123},
        {"source": 123},
        {"target": 123},
        {"source": "this should be a list", "target": ["like", "this"]},
    ],
)
def test_language_pairs_when_fetch_is_invalid(json_value):
    responses.reset()
    responses.add(
        responses.GET,
        configuration.get_config_value("endpoints", "language_pairs"),
        json=json_value,
        status=200,
    )
    assert None is language_pairs.get_language_pairs()
    assert True is language_pairs.is_valid_language_pair("any", "combination")
