from typing import List

from recommendation.api.translation import candidate_finders, filters, pageviews
from recommendation.api.translation.models import (
    RankMethodEnum,
    RecommendationAlgorithmEnum,
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationCandidate,
    TranslationRecommendationRequest,
)
from recommendation.external_data import fetcher
from recommendation.utils.logger import log, timeit

finder_map = {
    "morelike": candidate_finders.get_candidates_by_search,
    "mostpopular": candidate_finders.get_top_pageview_candidates,
    "collections": candidate_finders.get_collection_candidates,
}


async def find_candidates(rec_req_model: TranslationRecommendationRequest) -> List[TranslationRecommendationCandidate]:
    candidates: List[TranslationRecommendationCandidate]
    if rec_req_model.collections:
        finder = finder_map["collections"]
    elif rec_req_model.topic or rec_req_model.seed:
        finder = finder_map["morelike"]
    else:
        finder = finder_map[RecommendationAlgorithmEnum.mostpopular]

    candidates = await finder(rec_req_model)
    log.debug(f"Using finder {finder.__name__} to get candidates")

    return candidates


@timeit
async def recommend(rec_model: TranslationRecommendationRequest) -> List[TranslationRecommendation]:
    """
    1. Use finder to select a set of candidate articles
    2. Filter out candidates that are not missing, are disambiguation pages, etc
    3. get pageview info for each passing candidate if desired
    """

    candidates = await find_candidates(rec_model)

    missing: List[TranslationRecommendationCandidate] = filters.filter_by_missing(rec_model.target, candidates)

    if rec_model.rank_method == RankMethodEnum.sitelinks:
        # Sort by langlinks count, from highest to lowest
        missing = sorted(missing, key=lambda x: x.langlinks_count, reverse=True)
    else:
        # Sort by rank, from lowest to highest
        missing = sorted(missing, key=lambda x: x.rank, reverse=False)

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
    candidates = await find_candidates(rec_model)

    present: List[TranslationRecommendationCandidate] = filters.filter_by_present(rec_model.target, candidates)

    if rec_model.rank_method == RankMethodEnum.sitelinks:
        # Sort by langlinks count, from highest to lowest
        present = sorted(present, key=lambda x: x.langlinks_count, reverse=True)
    else:
        # Sort by rank, from lowest to highest
        present = sorted(present, key=lambda x: x.rank, reverse=False)

    candidate_titles = [candidate.title for candidate in present]

    results = await fetcher.get_section_suggestions(
        rec_model.source, rec_model.target, candidate_titles, rec_model.count
    )

    def find_by_title(title):
        # Iterate over the list and return the object with the matching title
        for candidate in present:
            if candidate.title == title:
                return candidate
        return None  # Return None if no matching object is found

    section_suggestions: List[SectionTranslationRecommendation] = []

    for result in results:
        data = result["sections"]
        candidate = find_by_title(data["sourceTitle"])

        recommendation = SectionTranslationRecommendation(
            source_title=data["sourceTitle"],
            target_title=data["targetTitle"],
            source_sections=data["sourceSections"],
            target_sections=data["targetSections"],
            present=data["present"],
            missing=data["missing"],
            collection=candidate.collection,
        )
        section_suggestions.append(recommendation)

    return section_suggestions
