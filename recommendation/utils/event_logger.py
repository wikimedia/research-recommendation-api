import json
import logging
import time
from datetime import datetime

import httpx

from recommendation.external_data import fetcher
from recommendation.utils.configuration import configuration

log = logging.getLogger(__name__)

httpx_sync_client = httpx.Client()


def log_api_request(source, target, seed=None, search=None, host="", user_agent=None, **kwargs):
    event = {"timestamp": int(time.time()), "sourceLanguage": source, "targetLanguage": target}
    if seed:
        event["seed"] = seed
    if search:
        event["searchAlgorithm"] = search

    schema = "TranslationRecommendationAPIRequests"
    payload = {
        "schema": schema,
        "$schema": f"/analytics/legacy/${schema.lower()}/1.0.0",
        "revision": 16261139,
        "event": event,
        "webHost": host,
        "client_dt": datetime.now().isoformat(),
        "meta": {"stream": "eventlogging_" + schema, "domain": host},
    }

    url = str(configuration.EVENT_LOGGER_API)
    headers = fetcher.set_headers_with_host_header(configuration.EVENT_LOGGER_API_HEADER)
    log.info("Logging event: %s", json.dumps(payload))

    if user_agent is not None:
        headers["User-Agent"] = user_agent
    try:
        httpx_sync_client.post(url, data=payload, headers=headers)
    except httpx.RequestError:
        pass
