import inspect
import time
from collections import defaultdict
from typing import Annotated, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from recommendation.api.translation import pageviews
from recommendation.api.translation.models import (
    PageCollection,
    PageCollectionMembershipRequest,
    PageCollectionResponse,
    SectionTranslationRecommendationResponse,
    TranslationRecommendationRequest,
    TranslationRecommendationResponse,
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
) -> TranslationRecommendationResponse:
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
        recommendation_response: TranslationRecommendationResponse = await recommender.recommend()  # Await async method
    else:
        recommendation_response: TranslationRecommendationResponse = (
            recommender.recommend()
        )  # Call sync method directly

    if recommendation_response.recommendations and rec_model.include_pageviews:
        log.debug("Getting pageviews for %d recommendations", len(recommendation_response.recommendations))
        recommendation_response.recommendations = await pageviews.set_pageview_data(
            rec_model.source, recommendation_response.recommendations
        )

    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)
    return recommendation_response


@router.get("/translation/sections")
async def get_section_translation_recommendations(
    rec_model: Annotated[TranslationRecommendationRequest, Depends()],
    request: Request,
    background_tasks: BackgroundTasks,
) -> SectionTranslationRecommendationResponse:
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
        section_recommendation_response: SectionTranslationRecommendationResponse = (
            await recommender.recommend_sections()
        )  # Await async method
    else:
        section_recommendation_response: SectionTranslationRecommendationResponse = (
            recommender.recommend_sections()
        )  # Call sync method directly

    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)

    return section_recommendation_response


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
        else:
            # Move single-item "slash collections" to ungrouped
            ungrouped.extend(group_collections)
    # Sort ungrouped collections alphabetically by name (case-insensitive)
    ungrouped.sort(key=lambda collection: collection.name.lower())

    grouped = {**final_groups, "ungrouped": ungrouped}

    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)

    return grouped


@router.get("/translation/page-collection-membership")
async def check_page_collection_membership(
    request_model: Annotated[PageCollectionMembershipRequest, Depends()],
    request: Request,
) -> Dict[str, bool]:
    """
    Checks which Wikidata QIDs are contained in a specific page collection.

    Returns a dictionary mapping each provided QID to a boolean indicating
    whether it exists in the specified collection.
    """
    t1 = time.time()

    # Parse QIDs from pipe-delimited string
    qids_list = request_model.qids.split("|") if request_model.qids else []

    # Initialize result with all QIDs as False
    result = dict.fromkeys(qids_list, False)

    # If no QIDs provided, return empty dict
    if not qids_list:
        t2 = time.time()
        log.info("Request processed in %f seconds", t2 - t1)
        return result

    # Get page collections from cache
    page_collection_cache = get_page_collection_cache()
    page_collections: List[PageCollection] = page_collection_cache.get_page_collections()

    # Find the matching collection (case-insensitive)
    matching_collection = None
    for collection in page_collections:
        if collection.name.casefold() == request_model.collection.casefold():
            matching_collection = collection
            break

    # If collection not found or empty, return all False
    if not matching_collection or not matching_collection.articles:
        t2 = time.time()
        log.info("Request processed in %f seconds", t2 - t1)
        return result

    # Build a set of QIDs in the collection
    collection_qids = {article.wikidata_id for article in matching_collection.articles}

    # Check membership for each QID
    for qid in qids_list:
        result[qid] = qid in collection_qids

    t2 = time.time()
    log.info("Request processed in %f seconds", t2 - t1)

    return result
