import configparser
from pkg_resources import resource_filename

import recommendation

_config = None
_config_locations = [
    resource_filename(recommendation.__name__, 'data/recommendation.ini'),
    '/etc/recommendation/recommendation.ini'
]


def get_config_value(section, key, **kwargs):
    return _get_configuration().get(section, key, **kwargs)


def get_config_int(section, key):
    return _get_configuration().getint(section, key)


def get_config_float(section, key):
    return _get_configuration().getfloat(section, key)


def get_config_dict(section):
    return dict(_get_configuration()[section])


def get_config_bool(section, key):
    return _get_configuration().getboolean(section, key)


def _get_configuration():
    global _config
    if _config is None:
        initialize_config()
    return _config


def initialize_config():
    config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    config.read(_config_locations)
    global _config
    _config = config
