import time
from typing import Annotated, List

from fastapi import APIRouter, Depends, Request

from recommendation.api.translation.models import (
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.utils import event_logger
from recommendation.utils.logger import log
from recommendation.utils.recommendation_helper import recommend, recommend_sections

router = APIRouter()


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
