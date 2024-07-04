import time
from typing import Annotated, List

from fastapi import APIRouter, Depends, Request

from recommendation.api.translation import candidate_finders, filters, pageviews
from recommendation.api.translation.models import (
    RankMethodEnum,
    RecommendationAlgorithmEnum,
    TranslationRecommendation,
    TranslationRecommendationCandidate,
    TranslationRecommendationRequest,
)
from recommendation.utils import event_logger
from recommendation.utils.logger import log, timeit

router = APIRouter()


finder_map = {
    "morelike": candidate_finders.get_morelike_candidates,
    "mostpopular": candidate_finders.get_top_pageview_candidates,
}


@timeit
async def recommend(
    rec_model: TranslationRecommendationRequest,
) -> List[TranslationRecommendation]:
    """
    1. Use finder to select a set of candidate articles
    2. Filter out candidates that are not missing, are disambiguation pages, etc
    3. get pageview info for each passing candidate if desired
    """

    candidates: List[TranslationRecommendationCandidate] = []

    if rec_model.seed:
        finder = finder_map[rec_model.search_algorithm]
    else:
        finder = finder_map[RecommendationAlgorithmEnum.mostpopular]
    candidates = await finder(rec_model.source, rec_model.seed, filter_language=rec_model.target)

    recs: List[TranslationRecommendation] = filters.filter_by_missing(rec_model.source, rec_model.target, candidates)

    if rec_model.rank_method == RankMethodEnum.sitelinks:
        # Sort by langlinks count, from highest to lowest
        recs = sorted(recs, key=lambda x: x.langlinks_count, reverse=True)
    else:
        # Sort by rank, from lowest to highest
        recs = sorted(recs, key=lambda x: x.rank, reverse=False)

    recs = recs[: rec_model.count]

    if recs and rec_model.include_pageviews:
        log.debug("Getting pageviews for %d recommendations", len(recs))
        recs = await pageviews.set_pageview_data(rec_model.source, recs)

    return recs


@router.get("/translation")
async def get_translation_recommendations(
    rec_model: Annotated[TranslationRecommendationRequest, Depends()],
    request: Request,
) -> List[TranslationRecommendation]:
    t1 = time.time()

    event_logger.log_api_request(
        host=request.client.host, user_agent=request.headers.get("user-agent"), **rec_model.model_dump()
    )

    recs = await recommend(rec_model)
    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)
    return recs
