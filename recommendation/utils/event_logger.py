from datetime import datetime
import requests
import logging
import json
import time

from recommendation.utils import configuration
from recommendation.api.external_data import fetcher

log = logging.getLogger(__name__)


def log_api_request(source, target, seed=None, search=None, host='',
                    user_agent=None, **kwargs):
    event = dict(timestamp=int(time.time()),
                 sourceLanguage=source,
                 targetLanguage=target)
    if seed:
        event['seed'] = seed
    if search:
        event['searchAlgorithm'] = search

    schema = 'TranslationRecommendationAPIRequests'
    payload = {
        'schema': schema,
        '$schema': f"/analytics/legacy/${schema.lower()}/1.0.0",
        'revision': 16261139,
        'event': event,
        'webHost': host,
        'client_dt': datetime.now().isoformat(),
        'meta': {
            'stream': 'eventlogging_' + schema,
            'domain': host
        }
    }

    url = configuration.get_config_value('endpoints', 'event_logger')
    headers = fetcher.set_headers_with_host_header(configuration, 'event_logger')
    log.info('Logging event: %s', json.dumps(payload))

    if user_agent is not None:
        headers['User-Agent'] = user_agent
    try:
        requests.post(url, data=payload, headers=headers)
    except requests.exceptions.RequestException:
        pass
