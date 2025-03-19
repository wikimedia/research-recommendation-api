import logging
from typing import List

import httpx

from recommendation.external_data import fetcher
from recommendation.utils.configuration import configuration

log = logging.getLogger(__name__)

httpx_sync_client = httpx.Client(timeout=30.0, limits=httpx.Limits(max_keepalive_connections=5, max_connections=5))


_language_pairs = None

# Copied from https://phabricator.wikimedia.org/diffusion/ECTX/browse/master/extension.json
_language_to_domain_mapping = {
    "be-x-old": "be-tarask",
    "bho": "bh",
    "en-simple": "simple",
    "gsw": "als",
    "lzh": "zh-classical",
    "nan": "zh-min-nan",
    "nb": "no",
    "rup": "roa-rup",
    "sgs": "bat-smg",
    "simple": "simple",
    "vro": "fiu-vro",
    "yue": "zh-yue",
}


def is_valid_source_language(source):
    pairs = get_language_pairs()
    if pairs is None:
        return True
    return source in pairs["source"] or source in get_language_to_domain_mapping().values()


def is_valid_target_language(target):
    pairs = get_language_pairs()
    if pairs is None:
        return True
    return target in pairs["target"] or target in get_language_to_domain_mapping().values()


def initialize_language_pairs():
    global _language_pairs
    if _language_pairs is None:
        language_pairs_endpoint = configuration.LANGUAGE_PAIRS_API
        headers = fetcher.set_headers_with_host_header(configuration.LANGUAGE_PAIRS_API_HEADER)

        try:
            result = httpx_sync_client.get(str(language_pairs_endpoint), headers=headers)
            result.raise_for_status()
            pairs = result.json()
            if {"source", "target"} ^ set(pairs.keys()):
                raise ValueError()
            if not all(isinstance(v, list) for v in pairs.values()):
                raise ValueError()
            _language_pairs = pairs
        except httpx.RequestError as e:
            log.warning(f"Unable to load data from {language_pairs_endpoint}. {e}")
        except (AttributeError, ValueError):
            log.warning("language pairs were invalid")


def get_language_pairs():
    initialize_language_pairs()
    return _language_pairs


def get_language_to_domain_mapping():
    return _language_to_domain_mapping


def is_missing_in_target_language(language, available_languages: List[str]) -> bool:
    """
    Check if a language is missing both as is and after domain mapping in a list of available languages.

    This function verifies whether a given language is missing from the available languages list
    in two ways:
    1. Direct match - checking if the language exists in available_languages
    2. Domain mapping match - checking if any available language maps to the given language

    Args:
        language (str): The language code to check for
        available_languages (List[str]): List of available language codes

    Returns:
        bool: True if the language is missing (both directly and after mapping), False otherwise
    """
    language_to_domain_mapping = get_language_to_domain_mapping()
    return language not in available_languages and language not in [
        language_to_domain_mapping.get(language, language) for language in available_languages
    ]
