from typing import List

from recommendation.api.translation.models import TranslationRecommendationCandidate
from recommendation.utils.logger import timeit


@timeit
def filter_by_missing(target, candidates) -> List[TranslationRecommendationCandidate]:
    """
    Filters out which articles from source already exist in target
    using Wikidata sitelinks
    """

    missing_articles: List[TranslationRecommendationCandidate] = []
    candidate: TranslationRecommendationCandidate
    for candidate in candidates:
        if target not in candidate.languages:
            missing_articles.append(candidate)

    return missing_articles


@timeit
def filter_by_present(target, candidates) -> List[TranslationRecommendationCandidate]:
    """
    Filters out which articles from source that do not exist in target
    using Wikidata sitelinks
    """

    present_articles: List[TranslationRecommendationCandidate] = []
    candidate: TranslationRecommendationCandidate
    for candidate in candidates:
        if target in candidate.languages:
            present_articles.append(candidate)

    return present_articles
