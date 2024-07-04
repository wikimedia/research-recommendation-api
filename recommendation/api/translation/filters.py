from typing import List

from recommendation.api.translation.models import TranslationRecommendationCandidate
from recommendation.utils.logger import timeit


@timeit
def filter_by_missing(source, target, candidates) -> List[TranslationRecommendationCandidate]:
    """
    Filters out which articles from source already exist in target
    using Wikidata sitelinks
    """

    filtered_articles: List[TranslationRecommendationCandidate] = []
    candidate: TranslationRecommendationCandidate
    for candidate in candidates:
        if target not in candidate.languages:
            filtered_articles.append(candidate)

    return filtered_articles
