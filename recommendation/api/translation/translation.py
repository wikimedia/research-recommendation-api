import inspect
import time
from typing import Annotated, List

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from recommendation.api.translation import pageviews
from recommendation.api.translation.models import (
    PageCollection,
    PageCollectionResponse,
    SectionTranslationRecommendation,
    TranslationRecommendation,
    TranslationRecommendationRequest,
)
from recommendation.cache import get_page_collection_cache
from recommendation.recommenders.recommender_factory import RecommenderFactory
from recommendation.utils import event_logger
from recommendation.utils.logger import log

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

    # Initialize the factory with the request model
    factory = RecommenderFactory(rec_model)
    recommender = factory.get_recommender()
    if inspect.iscoroutinefunction(recommender.recommend):
        recs = await recommender.recommend()  # Await async method
    else:
        recs = recommender.recommend()  # Call sync method directly

    if recs and rec_model.include_pageviews:
        log.debug("Getting pageviews for %d recommendations", len(recs))
        recs = await pageviews.set_pageview_data(rec_model.source, recs)

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

    factory = RecommenderFactory(rec_model)
    recommender = factory.get_recommender()
    if inspect.iscoroutinefunction(recommender.recommend_sections):
        section_suggestions = await recommender.recommend_sections()  # Await async method
    else:
        section_suggestions = recommender.recommend_sections()  # Call sync method directly

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
        source=None,
        target=None,
    )

    page_collection_cache = get_page_collection_cache()
    page_collections: List[PageCollection] = page_collection_cache.get_page_collections()

    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)

    return page_collections
