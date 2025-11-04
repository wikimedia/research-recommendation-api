from typing import List

from recommendation.cache import get_sitematrix_cache

# Copied from https://phabricator.wikimedia.org/diffusion/ECTX/browse/master/extension.json
_language_to_domain_mapping = {
    "be-tarask": "be-x-old",
    "bho": "bh",
    "gsw": "als",
    "lzh": "zh-classical",
    "nan": "zh-min-nan",
    "nb": "no",
    "rup": "roa-rup",
    "sgs": "bat-smg",
    "vro": "fiu-vro",
    "yue": "zh-yue",
}


def is_valid_language(language):
    """
    Validate if a language code is valid using cached sitematrix data.

    Args:
        language (str): Language code to validate

    Returns:
        bool: True if valid or cache unavailable (skip validation), False if invalid
    """
    sitematrix_cache = get_sitematrix_cache()
    language_codes = sitematrix_cache.get_language_codes()

    # Skip validation if cache is not available
    if language_codes is None:
        return True

    # Check if language is in cached language codes or domain mapping (keys or values)
    domain_mapping = get_language_to_domain_mapping()
    return language in language_codes or language in domain_mapping.keys() or language in domain_mapping.values()


def get_language_to_domain_mapping():
    return _language_to_domain_mapping


def is_missing_in_target_language(language, available_languages: List[str]) -> bool:
    """
    Check if a language is missing both as is and after domain mapping in a list of available languages.

    This function verifies whether a given language is missing from the available languages list
    in two ways:
    1. Direct match - checking if the language exists in available_languages
    2. Domain mapping match - checking if the language, mapped to domain, exists in available_languages

    Args:
        language (str):
            The language code to check for. Should be a valid code supported by the sitematrix.
            Examples for all special codes: "be-tarask", "bho", "gsw", "lzh", "nan", "nb", "rup", "sgs", "vro", "yue".
        available_languages (List[str]):
            List of available language codes coming from Wikipedia Action API.
            Examples for all special codes:
            [ "be-x-old", "bh", "als", "zh-classical", "zh-min-nan", "nb", "roa-rup", "bat-smg", "fiu-vro", "zh-yue" ]

    Returns:
        bool: True if the language is missing (both directly and after mapping), False otherwise
    """
    language_to_domain_mapping = get_language_to_domain_mapping()
    return (
        language not in available_languages
        and language_to_domain_mapping.get(language, language) not in available_languages
    )
