from flask import Flask

from recommendation.api.types.translation import translation
from recommendation.api.types.related_articles import related_articles, candidate_finder
from recommendation.api import api
from recommendation.web import gapfinder
from recommendation.utils import logger
from recommendation.utils import configuration

logger.initialize_logging()

app = Flask(__name__)
app.register_blueprint(api.api.blueprint)

section = "enabled_services"

if configuration.get_config_bool(section, "gapfinder"):
    app.register_blueprint(gapfinder.gapfinder)

if configuration.get_config_bool(section, "translation"):
    app.register_blueprint(translation.api.blueprint)
    app.register_blueprint(translation.legacy.blueprint)

if configuration.get_config_bool(section, "related_articles"):
    optimized_path = configuration.get_config_value(
        "related_articles", "optimized_embedding_path"
    )
    candidate_finder.initialize_embedding()
    app.register_blueprint(related_articles.api.blueprint)

app.config["RESTPLUS_VALIDATE"] = True
app.config["RESTPLUS_MASK_SWAGGER"] = False
application = app

if __name__ == "__main__":
    application.run()
