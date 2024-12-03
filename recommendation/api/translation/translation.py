import time
from typing import Annotated, List

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from recommendation.api.translation.models import (
    PageCollection,
    PageCollectionResponse,
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.cache import get_page_collection_cache
from recommendation.utils import event_logger
from recommendation.utils.logger import log
from recommendation.utils.recommendation_helper import recommend, recommend_sections

router = APIRouter()


@router.get("/translation")
async def get_translation_recommendations(
    rec_model: Annotated[TranslationRecommendationRequest, Depends()],
    request: Request,
    background_tasks: BackgroundTasks,
) -> List[TranslationRecommendation]:
    """
    Retrieves translation recommendations based on the provided recommendation model.
    """
    t1 = time.time()

    background_tasks.add_task(
        event_logger.log_api_request,
        host=request.client.host,
        user_agent=request.headers.get("user-agent"),
        **rec_model.model_dump(),
    )

    recs = await recommend(rec_model)
    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)
    return recs


@router.get("/translation/sections")
async def get_section_translation_recommendations(
    rec_model: Annotated[TranslationRecommendationRequest, Depends()],
    request: Request,
    background_tasks: BackgroundTasks,
) -> List[SectionTranslationRecommendation]:
    """
    Retrieves section translation recommendations based on the provided recommendation model.
    """
    t1 = time.time()

    background_tasks.add_task(
        event_logger.log_api_request,
        host=request.client.host,
        user_agent=request.headers.get("user-agent"),
        **rec_model.model_dump(),
    )

    section_suggestions = await recommend_sections(rec_model)

    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)

    return section_suggestions


@router.get("/translation/page-collections", response_model=List[PageCollectionResponse])
async def get_page_collections(
    request: Request,
    background_tasks: BackgroundTasks,
) -> List[PageCollectionResponse]:
    """
    Retrieves page collections from cache and returns them, including only their metadata
    """
    t1 = time.time()

    background_tasks.add_task(
        event_logger.log_api_request,
        host=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )

    page_collection_cache = get_page_collection_cache()
    page_collections: List[PageCollection] = page_collection_cache.get_page_collections()

    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)

    return page_collections
