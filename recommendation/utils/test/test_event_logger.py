import responses
import re

from recommendation.utils import configuration
from recommendation.utils import event_logger


def test_correct_endpoint_is_requested():
    responses.add(responses.GET, re.compile("."), body="", status=200)
    event_logger.log_api_request("a", "b")
    assert 1 == len(responses.calls)
    assert (
        configuration.get_config_value("endpoints", "event_logger")
        in responses.calls[0].request.url
    )


def test_user_agent_override():
    responses.add(responses.GET, re.compile("."), body="", status=200)
    expected_user_agent = "overridden"
    event_logger.log_api_request("a", "b", user_agent=expected_user_agent)
    assert expected_user_agent == responses.calls[0].request.headers["User-Agent"]
    event_logger.log_api_request("a", "b")
    assert expected_user_agent != responses.calls[1].request.headers["User-Agent"]
