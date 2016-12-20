from pkg_resources import resource_filename

import pytest

import recommendation
from recommendation.test.conftest import config_locations as overridden_config_locations  # NOQA


@pytest.fixture  # NOQA
def config_locations(overridden_config_locations):
    overridden_config_locations.append(resource_filename(recommendation.__name__,
                                                         'api/types/related_articles/test/test_related_articles.ini'))
    return overridden_config_locations


from recommendation.test.conftest import change_config_and_setup_responses  # NOQA
