import logging
import time

from recommendation.utils import configuration
import recommendation

log = logging.getLogger(__name__)


def initialize_logging():
    logging.basicConfig(
        format=configuration.get_config_value("logging", "format"),
        level=logging.WARNING,
    )
    log = logging.getLogger(recommendation.__name__)
    log.setLevel(
        logging.getLevelName(configuration.get_config_value("logging", "level"))
    )


def timeit(method):
    """Decorator for measuring function run times"""

    def timed(*args, **kw):
        t1 = time.time()
        result = method(*args, **kw)
        t2 = time.time()
        log.debug("%r run time: %2.2f s", method.__name__, t2 - t1)
        return result

    return timed
