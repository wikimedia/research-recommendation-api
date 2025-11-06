import inspect
import time
from collections import defaultdict
from typing import Annotated, Dict, List

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


@router.get("/translation/page-collection-groups", response_model=Dict[str, List[PageCollectionResponse]])
async def get_page_collection_groups(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, List[PageCollectionResponse]]:
    """
    Retrieves page collections from cache, groups them based on their name and returns the groups
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

    grouped = defaultdict(list)
    ungrouped = []

    for collection in page_collections:
        if "/" in collection.name:
            prefix = collection.name.split("/", 1)[0]
            grouped[prefix].append(collection)
        else:
            ungrouped.append(collection)

    # Step 2: Filter groups that have at least 2 items and sort collections within each group
    final_groups = {}
    for group_name, group_collections in grouped.items():
        if len(group_collections) > 1:
            # Sort collections within each group alphabetically by name (case-insensitive)
            group_collections.sort(key=lambda collection: collection.name.lower())
            final_groups[group_name] = group_collections

    # Sort ungrouped collections alphabetically by name (case-insensitive)
    ungrouped.sort(key=lambda collection: collection.name.lower())

    grouped = {**final_groups, "ungrouped": ungrouped}

    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)

    return grouped
