import json
from flask import Blueprint, render_template, request, send_from_directory

from recommendation.utils import configuration
from recommendation.utils import language_pairs

gapfinder = Blueprint('gapfinder', __name__, template_folder='templates', static_folder='static',
                      static_url_path='/static/gapfinder')


@gapfinder.route('/')
def home():
    s = request.args.get('s')
    t = request.args.get('t')
    seed = request.args.get('seed')
    search = request.args.get('search')
    rank_method = request.args.get('rank_method')
    pairs = language_pairs.get_language_pairs()
    return render_template(
        'index.html',
        language_pairs=json.dumps(pairs),
        language_to_domain_mapping=json.dumps(language_pairs.get_language_to_domain_mapping()),
        s=s,
        t=t,
        seed=seed,
        search=search,
        rank_method=rank_method,
        event_logger_url=configuration.get_config_value('endpoints', 'event_logger'),
        default_search=configuration.get_config_value('gapfinder', 'default_search')
    )


@gapfinder.route('/static/resource/<path:filename>')
def resource(filename):
    return send_from_directory(configuration.get_config_value('gapfinder', 'resource_path'), filename=filename)
