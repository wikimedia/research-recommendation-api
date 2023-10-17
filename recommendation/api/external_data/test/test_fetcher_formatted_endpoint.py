import pytest

from recommendation.api.external_data import fetcher
from recommendation.utils import configuration

def test_get_formatted_endpoint_without_endpoint_host_headers_section():
    if not configuration.section_exists('endpoint_host_headers'):
        endpoint = fetcher.get_formatted_endpoint(configuration, 'wikipedia', source='en')
        assert endpoint == 'https://en.wikipedia.org/w/api.php'