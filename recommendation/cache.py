import json
import zlib
from functools import lru_cache

from diskcache import UNKNOWN, Cache, Disk

from recommendation.api.translation.models import TranslationCampaign
from recommendation.utils.configuration import configuration

CACHE_DIRECTORY = ".cache"


class JSONDisk(Disk):
    def __init__(self, directory, compress_level=1, **kwargs):
        self.compress_level = compress_level
        super().__init__(directory, **kwargs)

    def put(self, key):
        json_bytes = json.dumps(key).encode("utf-8")
        data = zlib.compress(json_bytes, self.compress_level)
        return super().put(data)

    def get(self, key, raw):
        data = super().get(key, raw)
        return json.loads(zlib.decompress(data).decode("utf-8"))

    def store(self, value, read, key=UNKNOWN):
        if not read:
            if value.model_dump_json:
                # pydantic model
                json_bytes = value.model_dump_json().encode("utf-8")
            else:
                json_bytes = json.dumps(value).encode("utf-8")
            value = zlib.compress(json_bytes, self.compress_level)
        return super().store(value, read, key=key)

    def fetch(self, mode, filename, value, read):
        data = super().fetch(mode, filename, value, read)
        if not read:
            data = json.loads(zlib.decompress(data).decode("utf-8"))
        return data


class CampaignCache(Cache):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def set_campaign_page(self, campaign: TranslationCampaign):
        self.set(campaign.id, campaign)

    def get_campaign_page(self, campaign_id) -> TranslationCampaign | None:
        cached_campaign: str = self.get(campaign_id)
        if cached_campaign:
            model: TranslationCampaign = TranslationCampaign.model_validate(cached_campaign)
            return model

        return None


@lru_cache
def get_campaign_cache():
    return CampaignCache(
        disk=JSONDisk,
        disk_compress_level=6,  # zlib compression level,
        directory=configuration.CACHE_DIRECTORY,
        size_limit=1e9,
    )


__all__ = ["get_campaign_cache"]
