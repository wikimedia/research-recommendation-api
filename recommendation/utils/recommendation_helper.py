from typing import List

from recommendation.api.translation import candidate_finders, filters, pageviews
from recommendation.api.translation.models import (
    RankMethodEnum,
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationCandidate,
    TranslationRecommendationRequest,
)
from recommendation.external_data import fetcher
from recommendation.utils.collection_helper import (
    get_collection_page_recommendations,
    get_collection_section_recommendations,
    reorder_page_collection_section_recommendations,
)
from recommendation.utils.logger import log, timeit


@timeit
async def recommend(rec_model: TranslationRecommendationRequest) -> List[TranslationRecommendation]:
    """
    1. Use finder to select a set of candidate articles
    2. Filter out candidates that are not missing, are disambiguation pages, etc
    3. get pageview info for each passing candidate if desired
    """

    if rec_model.collections:
        missing = get_collection_page_recommendations(rec_model)
    elif rec_model.topic or rec_model.seed:
        candidates = await candidate_finders.get_candidates_by_search(rec_model)
        missing: List[TranslationRecommendationCandidate] = filters.filter_by_missing(rec_model.target, candidates)
    else:
        candidates = await candidate_finders.get_top_pageview_candidates(rec_model)
        missing: List[TranslationRecommendationCandidate] = filters.filter_by_missing(rec_model.target, candidates)

    if not rec_model.collections:
        missing = sort_recommendations(missing, rec_model.rank_method)

    missing = missing[: rec_model.count]

    if missing and rec_model.include_pageviews:
        log.debug("Getting pageviews for %d recommendations", len(missing))
        missing = await pageviews.set_pageview_data(rec_model.source, missing)

    return missing


@timeit
async def recommend_sections(rec_model: TranslationRecommendationRequest) -> List[SectionTranslationRecommendation]:
    """
    1. Use finder to select a set of candidate articles
    2. Filter out candidates that are not present, are disambiguation pages, etc
    3. get the section suggestions for the candidate articles from CXServer API
    """
    if rec_model.collections:
        present = await get_collection_section_recommendations(rec_model)
    elif rec_model.topic or rec_model.seed:
        candidates = await candidate_finders.get_candidates_by_search(rec_model)
        present: List[TranslationRecommendationCandidate] = filters.filter_by_present(rec_model.target, candidates)
    else:
        candidates = await candidate_finders.get_top_pageview_candidates(rec_model)
        present: List[TranslationRecommendationCandidate] = filters.filter_by_present(rec_model.target, candidates)

    if not rec_model.collections:
        present = sort_recommendations(present, rec_model.rank_method)

    candidate_titles = [candidate.title for candidate in present]

    results = await fetcher.get_section_suggestions(
        rec_model.source, rec_model.target, candidate_titles, rec_model.count
    )

    section_suggestions: List[SectionTranslationRecommendation] = []

    for result in results:
        data = result["sections"]
        candidate = next((c for c in present if c.title == data["sourceTitle"]), None)

        recommendation = SectionTranslationRecommendation(
            source_title=data["sourceTitle"],
            target_title=data["targetTitle"],
            source_sections=data["sourceSections"],
            target_sections=data["targetSections"],
            present=data["present"],
            missing=data["missing"],
            collection=candidate.collection if candidate else None,
        )
        section_suggestions.append(recommendation)

    if rec_model.collections:
        section_suggestions = reorder_page_collection_section_recommendations(section_suggestions)

    return section_suggestions


def sort_recommendations(recommendations, rank_method):
    if rank_method == RankMethodEnum.sitelinks:
        # Sort by langlinks count, from highest to lowest
        return sorted(recommendations, key=lambda x: x.langlinks_count, reverse=True)
    else:
        # Sort by rank, from lowest to highest
        return sorted(recommendations, key=lambda x: x.rank, reverse=False)
