import requests
import logging

from recommendation.utils import configuration

log = logging.getLogger(__name__)

_language_pairs = None

# Copied from https://phabricator.wikimedia.org/diffusion/ECTX/browse/master/extension.json
_language_to_domain_mapping = {
    "be-tarask": "be-x-old",
    "bho": "bh",
    "crh-latn": "crh",
    "gsw": "als",
    "lzh": "zh-classical",
    "nan": "zh-min-nan",
    "nb": "no",
    "rup": "roa-rup",
    "sgs": "bat-smg",
    "vro": "fiu-vro",
    "yue": "zh-yue"
}


def is_valid_language_pair(source, target):
    if source == target:
        return False

    pairs = get_language_pairs()
    if pairs is None:
        # If we can't fetch a list of language pairs and it is the case that they are invalid,
        #  then the api will break downstream. is_valid_language_pair() is meant to short-circuit
        #  that failure, but is not essential
        return True

    source_valid = source in pairs['source'] or source in get_language_to_domain_mapping().values()
    target_valid = target in pairs['target'] or target in get_language_to_domain_mapping().values()

    if not source_valid or not target_valid:
        return False
    return True


def initialize_language_pairs():
    global _language_pairs
    if _language_pairs is None:
        language_pairs_endpoint = configuration.get_config_value('endpoints', 'language_pairs')
        try:
            result = requests.get(language_pairs_endpoint)
            result.raise_for_status()
            pairs = result.json()
            if {'source', 'target'} ^ set(pairs.keys()):
                raise ValueError()
            if not all(isinstance(v, list) for v in pairs.values()):
                raise ValueError()
            _language_pairs = pairs
        except requests.exceptions.RequestException as e:
            log.warning('Unable to load data from {}. {}'.format(language_pairs_endpoint, e))
        except (AttributeError, ValueError):
            log.warning('language pairs were invalid')


def get_language_pairs():
    initialize_language_pairs()
    return _language_pairs


def get_language_to_domain_mapping():
    return _language_to_domain_mapping
