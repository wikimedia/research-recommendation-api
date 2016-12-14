from flask import Flask

from recommendation.api.types.translation import translation
#from recommendation.api.types.related_articles import related_articles
from recommendation.api import api
from recommendation.web import gapfinder
from recommendation.utils import logger

logger.initialize_logging()

app = Flask(__name__)
app.register_blueprint(api.api.blueprint)
app.register_blueprint(translation.api.blueprint)
app.register_blueprint(translation.legacy.blueprint)
#app.register_blueprint(related_articles.api.blueprint)
app.register_blueprint(gapfinder.gapfinder)
app.config['RESTPLUS_VALIDATE'] = True
app.config['RESTPLUS_MASK_SWAGGER'] = False
application = app

if __name__ == '__main__':
    application.run(debug=True)
