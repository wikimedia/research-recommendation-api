import collections
import logging
import time

import flask_restplus
from flask_restplus import fields
from flask_restplus import reqparse
from flask_restplus import inputs

from recommendation.api import helper
from recommendation.api.types.related_articles import candidate_finder
from recommendation.utils import configuration

log = logging.getLogger(__name__)

api = helper.build_api('related_articles', __name__, url_prefix='/types/related_articles')
v1 = helper.build_namespace(api, 'v1', description='')

ArticleSpec = collections.namedtuple('Article', ['title', 'wikidata_id', 'url', 'score'])

v1_params = reqparse.RequestParser()

v1_params.add_argument(
    'source',
    type=str,
    required=True)
v1_params.add_argument(
    'count',
    type=inputs.int_range(low=0, high=configuration.get_config_int('api', 'count_max')),
    required=False,
    default=configuration.get_config_int('api', 'count_default'))
v1_params.add_argument(
    'seed',
    type=inputs.regex(r'^[^|]+(\|[^|]+)*$'),
    required=True)

v1_model = v1.model(ArticleSpec.__name__, ArticleSpec(
    title=fields.String(description='title', required=True),
    wikidata_id=fields.String(description='wikidata_id', required=True),
    url=fields.String(description='url', required=True),
    score=fields.Float(description='score', required=True)
)._asdict())

v1_doc = dict(description='Gets recommendations of articles that are related to a given article',
              params=dict(source='Source wiki project language code',
                          count='Number of recommendations to fetch',
                          seed='Seed article that can also be a list separated by "|"'))


@v1.route('/articles')
class Article(flask_restplus.Resource):
    @v1.expect(v1_params)
    @v1.marshal_with(v1_model, as_list=True)
    @v1.doc(**v1_doc)
    def get(self):
        args = v1_params.parse_args()
        return process_request(args)


def process_request(args):
    t1 = time.time()

    # event_logger.log_api_request(**args)
    recs = recommend(**args)

    t2 = time.time()
    log.info('Request processed in %f seconds', t2 - t1)
    return recs


def recommend(source, seed, count):
    recs = []

    for seed in seed.split('|'):
        recs.extend(candidate_finder.get_candidates(source, seed, count))

    return [ArticleSpec(title=rec.title,
                        wikidata_id=rec.wikidata_id,
                        url=rec.url,
                        score=rec.score)._asdict() for rec in recs]
