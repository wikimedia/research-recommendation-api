import logging
import logging.config
import time
from functools import lru_cache

import yaml

import recommendation
from recommendation.utils.configuration import configuration


@lru_cache(maxsize=None)
def initialize_logging():
    with open("logging.yaml", "rt") as f:
        config = yaml.safe_load(f.read())
    # Configure the logging module with the config file
    logging.config.dictConfig(config)
    logger = logging.getLogger(recommendation.__name__)
    logger.setLevel(configuration.LOG_LEVEL)
    return logger


def timeit(method):
    """Decorator for measuring function run times"""

    def timed(*args, **kw):
        t1 = time.time()
        result = method(*args, **kw)
        t2 = time.time()
        log.debug("%r run time: %2.2f s", method.__name__, t2 - t1)
        return result

    return timed


log = initialize_logging()
