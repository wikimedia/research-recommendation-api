"""
Usage: pytest test_performance.py -vs
"""

import cProfile
import pstats

import pytest
import memory_profiler

from recommendation.api.types.translation import translation
from recommendation.api.types.related_articles import related_articles, candidate_finder
from recommendation.utils import logger


@pytest.fixture(scope='module', autouse=True)
def initialize():
    logger.initialize_logging()
    candidate_finder.initialize_embedding()


@pytest.fixture(params=[
    'Apple', 'Banana'
])
def seed(request):
    return request.param


@pytest.fixture(params=[
    'Q89', 'Q90'
])
def item(request):
    return request.param


def test_translation_without_seed():
    run_call(translation.recommend, 'en', 'de', None, None, 400, include_pageviews=False)


def test_translation_with_seed(seed):
    run_call(translation.recommend, 'en', 'de', 'morelike', seed, 400, include_pageviews=False)


def test_related_articles(seed):
    run_call(related_articles.recommend, 'en', seed, 400)


def test_related_articles_by_items(item):
    run_call(related_articles.recommend_items, item)


def run_call(*args, **kwargs):
    profile_time(*args, **kwargs)
    profile_memory(*args, **kwargs)


def profile_time(*args, **kwargs):
    profile = cProfile.Profile()
    profile.runcall(*args, **kwargs)
    stats = pstats.Stats(profile)
    print_stats(stats)


def profile_memory(*args, **kwargs):
    memory_profiler.profile(args[0], precision=4)(*args[1:], **kwargs)
    memory_profiler.memory_usage((args[0], args[1:], kwargs))


def print_stats(stats):
    for basis in ('tottime', 'cumtime'):
        stats.sort_stats(basis)
        stats.print_stats(10)
        stats.print_stats('recommendation-api', 10)
