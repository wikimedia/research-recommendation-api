import json
import zlib
from functools import lru_cache
from typing import Set

from diskcache import UNKNOWN, Cache, Disk

from recommendation.api.translation.models import TranslationCampaign, TranslationCampaignCollection
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

    def set_translation_campaigns(self, translation_campaign_collection: TranslationCampaignCollection):
        self.set("translation_campaigns", translation_campaign_collection)

    def get_translation_campaigns(self) -> Set[TranslationCampaign] | None:
        collection: str = self.get("translation_campaigns")

        if collection:
            model: TranslationCampaignCollection = TranslationCampaignCollection.model_validate(collection)

            return model.list

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
