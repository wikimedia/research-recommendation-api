from typing import Dict, List

from recommendation.api.translation.models import (
    PageCollection,
    TranslationRecommendationCandidate,
    WikiDataArticle,
)
from recommendation.utils.logger import log


def get_candidates_for_page_collections(
    page_collections: List[PageCollection], source_language: str, target_language: str
) -> List[TranslationRecommendationCandidate]:
    collection_candidates = []

    for page_collection in page_collections:
        collection_candidates.extend(
            create_candidates_for_collection(page_collection, source_language, target_language)
        )

    return collection_candidates


def create_candidates_for_collection(
    page_collection: PageCollection, source_language: str, target_language: str
) -> List[TranslationRecommendationCandidate]:
    if len(page_collection.articles) == 0:
        log.warning(f"Found empty page-collection {page_collection}")

    collection_candidates = []

    wikidata_article: WikiDataArticle
    for wikidata_article in page_collection.articles:
        candidate_source_article_title = wikidata_article.langlinks.get(source_language)
        if candidate_source_article_title:
            collection_candidate = TranslationRecommendationCandidate(
                title=candidate_source_article_title,
                wikidata_id=wikidata_article.wikidata_id,
                langlinks_count=len(wikidata_article.langlinks),
                languages=wikidata_article.langlinks.keys(),
                collection=page_collection.get_metadata(target_language),
            )
            collection_candidates.append(collection_candidate)

    return collection_candidates


def reorder_page_collection_recommendations(
    recommendations: List[TranslationRecommendationCandidate],
) -> List[TranslationRecommendationCandidate]:
    """
    Reorders a list of recommendations such that recommendations from different collections are
    interleaved. The method distributes the recommendations by cycling through their collections,
    ensuring that each collection's recommendations are listed in a round-robin fashion.

    Args:
        recommendations (List[TranslationRecommendationCandidate]):
            A list of recommendations.

    Returns:
        List[TranslationRecommendationCandidate]: A reordered list of recommendations.

    Example:
        >>> collection1 = PageCollectionMetadata( name="Collection One" )
        >>> collection2 = PageCollectionMetadata( name="Collection Two" )
        >>> collection3 = PageCollectionMetadata( name="Collection Three" )

        >>> rec1 = TranslationRecommendationCandidate( title="Article 1", collection=collection1 )
        >>> rec2 = TranslationRecommendationCandidate( title="Article 2", collection=collection1 )
        >>> rec3 = TranslationRecommendationCandidate( title="Article 3", collection=collection2 )
        >>> rec4 = TranslationRecommendationCandidate( title="Article 4", collection=collection2 )
        >>> rec5 = TranslationRecommendationCandidate( title="Article 5", collection=collection3 )
        >>> recommendations = [rec1, rec2, rec3, rec4, rec5]
        >>> reorder_recommendations(recommendations)
        [rec1, rec3, rec5, rec2, rec4]
    """
    recommendations_by_collection: Dict[str, List[TranslationRecommendationCandidate]] = {}
    for recommendation in recommendations:
        collection_name = recommendation.collection.name
        if collection_name not in recommendations_by_collection:
            recommendations_by_collection[collection_name] = []  # Initialize a list for this collection
        recommendations_by_collection[collection_name].append(recommendation)

    collection_groups: List[TranslationRecommendationCandidate] = recommendations_by_collection.values()
    max_len = max((len(group) for group in collection_groups), default=0)

    # Interleave the recommendations so each one has a different collection
    recommendations = []
    for i in range(max_len):
        for group in collection_groups:
            if i < len(group):
                recommendations.append(group[i])

    return recommendations
