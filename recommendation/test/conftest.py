import pytest
import responses
from pkg_resources import resource_filename

from recommendation.utils import configuration
from recommendation.utils import logger
import recommendation


@pytest.fixture
def config_locations():
    locations = configuration._config_locations[:1]
    locations.append(resource_filename(recommendation.__name__, 'test/test_recommendation.ini'))
    return locations


@pytest.fixture(scope='function', autouse=True)
def change_config_and_setup_responses(request, config_locations):
    """
    This changes the config file that is loaded to test_recommendation.ini
     as well as (in a hack-y way) activating `responses` without having
     to apply a decorator to every test function
    """
    configuration._config = None
    old_config_locations = configuration._config_locations
    configuration._config_locations = config_locations

    logger.initialize_logging()

    responses._default_mock.__enter__()

    def fin():
        responses._default_mock.__exit__(None, None, None)
        configuration._config_locations = old_config_locations

    request.addfinalizer(fin)
