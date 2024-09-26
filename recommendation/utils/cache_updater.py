from typing import Dict, List, Optional, Set

from recommendation.api.translation.models import (
    CampaignMetadata,
    TranslationCampaign,
    TranslationCampaignCollection,
    WikiPage,
)
from recommendation.cache import get_campaign_cache
from recommendation.external_data import fetcher
from recommendation.utils.logger import log


def find_translation_campaign_by_cache_key(
    cached_translation_campaigns: Set[TranslationCampaign], campaign_key: str
) -> Optional[TranslationCampaign]:
    for campaign in cached_translation_campaigns:
        if campaign.cache_key == campaign_key:
            return campaign  # Return the campaign when found

    return None  # Return None if no match is found


# stub method. Should be moved to fetcher.py file and use "campaignsdata" API to fetch them
async def get_campaign_metadata_by_pages(pages: List[WikiPage]) -> Dict[str, CampaignMetadata]:
    metadata_by_pages = {}
    for page in pages:
        metadata_by_pages[page.id] = CampaignMetadata(
            name=str(page.id),
            source="en",
            targets=[],
        )

    return metadata_by_pages


def combine_campaign_pages_and_metadata(
    pages: List[WikiPage], metadata_by_pages: Dict[str, CampaignMetadata]
) -> Set[TranslationCampaign]:
    translation_campaigns: Set[TranslationCampaign] = set()
    for page in pages:
        metadata = metadata_by_pages[page.id]
        translation_campaign = TranslationCampaign(
            name=metadata.name, source=metadata.source, targets=metadata.targets, pages={page}
        )
        translation_campaigns.add(translation_campaign)

    return translation_campaigns


async def update_campaign_cache():
    """
    Update the campaign cache with campaign pages and their articles
    """

    # Get all pages containing a campaign marker
    campaign_pages: List[WikiPage] = await fetcher.get_campaign_pages()

    # Get metadata for each page
    campaign_metadata_by_pages = await get_campaign_metadata_by_pages(campaign_pages)

    fetched_translation_campaigns: Set[TranslationCampaign] = combine_campaign_pages_and_metadata(
        campaign_pages, campaign_metadata_by_pages
    )
    campaign_cache = get_campaign_cache()
    cached_translation_campaigns: Set[TranslationCampaign] = campaign_cache.get_translation_campaigns() or set()
    translation_campaigns_collection: TranslationCampaignCollection = TranslationCampaignCollection()

    for fetched_campaign in fetched_translation_campaigns:
        cached_translation_campaign = find_translation_campaign_by_cache_key(
            cached_translation_campaigns, fetched_campaign.cache_key
        )

        if cached_translation_campaign:
            translation_campaigns_collection.add(cached_translation_campaign)
            log.debug(f"Found campaign {cached_translation_campaign} in cache")
        else:
            await fetched_campaign.fetch_articles()
            translation_campaigns_collection.add(fetched_campaign)

    campaign_cache.set_translation_campaigns(translation_campaigns_collection)
