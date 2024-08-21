import json
from functools import lru_cache

from diskcache import Cache

from recommendation.api.translation.models import TranslationCampaign
from recommendation.utils.configuration import configuration

CACHE_DIRECTORY = ".cache"


class CampaignCache(Cache):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def set_campaign_page(self, campaign: TranslationCampaign):
        self.set(campaign.id, json.dumps(campaign.model_dump()))

    def get_campaign_page(self, campaign_id) -> TranslationCampaign | None:
        cached_campaign: str = self.get(campaign_id)
        if cached_campaign:
            model: TranslationCampaign = TranslationCampaign.model_validate_json(cached_campaign)
            return model

        return None


@lru_cache
def get_campaign_cache():
    return CampaignCache(directory=configuration.CACHE_DIRECTORY, size_limit=1e9)


__all__ = ["get_campaign_cache"]
