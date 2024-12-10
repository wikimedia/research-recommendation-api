from itertools import cycle
from typing import Dict, List

from recommendation.api.translation.models import (
    PageCollection,
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.cache import get_page_collection_cache
from recommendation.utils.logger import log


def get_collection_page_recommendations(req_model: TranslationRecommendationRequest) -> List[TranslationRecommendation]:
    return get_collection_recommendations_by_status(
        req_model.source, req_model.target, req_model.count, req_model.seed, missing=True
    )


async def get_collection_section_recommendations(
    req_model: TranslationRecommendationRequest,
) -> List[SectionTranslationRecommendation]:
    return get_collection_recommendations_by_status(
        req_model.source, req_model.target, req_model.count, req_model.seed, missing=False
    )


def get_collection_recommendations_by_status(source_language, target_language, count, collection_name, missing=True):
    page_collection_cache = get_page_collection_cache()
    page_collections: List[PageCollection] = page_collection_cache.get_page_collections()

    if collection_name:
        page_collections = [
            collection for collection in page_collections if collection.name.casefold() == collection_name.casefold()
        ]

    active_collections = []
    for page_collection in page_collections:
        if len(page_collection.articles) == 0:
            log.warning(f"Found empty page-collection {page_collection}")
        else:
            active_collections.append(page_collection)

    if not active_collections:
        return []  # Exit early if no page collections have articles

    # Create iterators for the articles of each page collection, paired with their collection
    article_iterators = [(iter(collection.articles), collection) for collection in active_collections]
    # Use cycle to iterate through the iterators in a round-robin fashion
    active_iterators = cycle(article_iterators)

    recommendations = []
    while article_iterators and len(recommendations) < count:
        try:
            # Get the next iterator and its associated page collection
            article_iterator, page_collection = next(active_iterators)
            valid_recommendation_for_collection = None
            while not valid_recommendation_for_collection:
                # Fetch the next article from the current iterator
                wikidata_article = next(article_iterator)
                candidate_source_article_title = wikidata_article.langlinks.get(source_language)
                candidate_target_article_title = wikidata_article.langlinks.get(target_language)
                already_exists = any(
                    wikidata_article.wikidata_id == recommendation.wikidata_id for recommendation in recommendations
                )
                if (
                    candidate_source_article_title
                    and bool(candidate_target_article_title) != missing
                    and not already_exists
                ):
                    valid_recommendation_for_collection = TranslationRecommendation(
                        title=candidate_source_article_title,
                        wikidata_id=wikidata_article.wikidata_id,
                        langlinks_count=len(wikidata_article.langlinks),
                        collection=page_collection.get_metadata(target_language),
                    )
            recommendations.append(valid_recommendation_for_collection)
        except StopIteration:
            # Remove exhausted iterators
            iterator_to_remove = next(active_iterators)
            article_iterators.remove(iterator_to_remove)
            active_iterators = cycle(article_iterators)
            if not article_iterators:
                break
    return recommendations


def reorder_page_collection_section_recommendations(
    recommendations: List[SectionTranslationRecommendation],
) -> List[SectionTranslationRecommendation]:
    """
    Reorders a list of recommendations such that recommendations from different collections are
    interleaved. The method distributes the recommendations by cycling through their collections,
    ensuring that each collection's recommendations are listed in a round-robin fashion.

    Args:
        recommendations (List[SectionTranslationRecommendation]): A list of section translation recommendations.

    Returns:
        List[SectionTranslationRecommendation]: A reordered list of recommendations.

    Example:
        >>> collection1 = PageCollectionMetadata( name="Collection One" )
        >>> collection2 = PageCollectionMetadata( name="Collection Two" )
        >>> collection3 = PageCollectionMetadata( name="Collection Three" )

        >>> rec1 = SectionTranslationRecommendation( source_title="Article 1", collection=collection1 )
        >>> rec2 = SectionTranslationRecommendation( source_title="Article 2", collection=collection1 )
        >>> rec3 = SectionTranslationRecommendation( source_title="Article 3", collection=collection2 )
        >>> rec4 = SectionTranslationRecommendation( source_title="Article 4", collection=collection2 )
        >>> rec5 = SectionTranslationRecommendation( source_title="Article 5", collection=collection3 )
        >>> test_recommendations = [rec1, rec2, rec3, rec4, rec5]
        >>> reorder_page_collection_section_recommendations(test_recommendations)
        [rec1, rec3, rec5, rec2, rec4]
    """
    recommendations_by_collection: Dict[str, List[SectionTranslationRecommendation]] = {}
    for recommendation in recommendations:
        collection_name = recommendation.collection.name
        if collection_name not in recommendations_by_collection:
            recommendations_by_collection[collection_name] = []  # Initialize a list for this collection
        recommendations_by_collection[collection_name].append(recommendation)

    collection_groups: List[List[SectionTranslationRecommendation]] = list(recommendations_by_collection.values())
    max_len = max((len(group) for group in collection_groups), default=0)

    # Interleave the recommendations so each one has a different collection
    recommendations = []
    for i in range(max_len):
        for group in collection_groups:
            if i < len(group):
                recommendations.append(group[i])

    return recommendations
