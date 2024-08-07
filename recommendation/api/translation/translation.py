import time
from typing import Annotated, List

from fastapi import APIRouter, Depends, Request

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
from recommendation.utils import event_logger
from recommendation.utils.logger import log, timeit

router = APIRouter()


finder_map = {
    "morelike": candidate_finders.get_candidates_by_search,
    "mostpopular": candidate_finders.get_top_pageview_candidates,
}


async def find_candidates(rec_req_model: TranslationRecommendationRequest) -> List[TranslationRecommendationCandidate]:
    candidates: List[TranslationRecommendationCandidate]
    if rec_req_model.topic or rec_req_model.seed:
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

    def get_candidate_titles(candidate):
        return candidate.title

    candidate_titles = list(map(get_candidate_titles, present))

    results = await fetcher.get_section_suggestions(
        rec_model.source, rec_model.target, candidate_titles, rec_model.count
    )

    section_suggestions: List[SectionTranslationRecommendation] = []

    for result in results:
        data = result["sections"]
        recommendation = SectionTranslationRecommendation(
            source_title=data["sourceTitle"],
            target_title=data["targetTitle"],
            source_sections=data["sourceSections"],
            target_sections=data["targetSections"],
            present=data["present"],
            missing=data["missing"],
        )
        section_suggestions.append(recommendation)

    return section_suggestions


@router.get("/translation")
async def get_translation_recommendations(
    rec_model: Annotated[TranslationRecommendationRequest, Depends()],
    request: Request,
) -> List[TranslationRecommendation]:
    """
    Retrieves translation recommendations based on the provided recommendation model.
    """
    t1 = time.time()

    event_logger.log_api_request(
        host=request.client.host, user_agent=request.headers.get("user-agent"), **rec_model.model_dump()
    )

    recs = await recommend(rec_model)
    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)
    return recs


@router.get("/translation/sections")
async def get_section_translation_recommendations(
    rec_model: Annotated[TranslationRecommendationRequest, Depends()],
    request: Request,
) -> List[SectionTranslationRecommendation]:
    """
    Retrieves section translation recommendations based on the provided recommendation model.
    """
    t1 = time.time()

    event_logger.log_api_request(
        host=request.client.host, user_agent=request.headers.get("user-agent"), **rec_model.model_dump()
    )

    section_suggestions = await recommend_sections(rec_model)

    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)

    return section_suggestions
