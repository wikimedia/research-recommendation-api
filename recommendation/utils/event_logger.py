import requests
import urllib.parse
import logging
import json
import time

from recommendation.utils import configuration

log = logging.getLogger(__name__)


def log_api_request(source, target, seed=None, search=None, user_agent=None, **kwargs):
    event = dict(timestamp=int(time.time()),
                 sourceLanguage=source,
                 targetLanguage=target)
    if seed:
        event['seed'] = seed
    if search:
        event['searchAlgorithm'] = search

    payload = dict(schema='TranslationRecommendationAPIRequests',
                   revision=16261139,
                   wiki='metawiki',
                   event=event)

    url = configuration.get_config_value('endpoints', 'event_logger')
    url += '?' + urllib.parse.quote_plus(json.dumps(payload))

    log.info('Logging event: %s', json.dumps(payload))

    headers = {}
    if user_agent is not None:
        headers['User-Agent'] = user_agent

    try:
        requests.get(url, headers=headers)
    except requests.exceptions.RequestException:
        pass
