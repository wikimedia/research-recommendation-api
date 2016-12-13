import collections
import logging
import time

import flask_restplus
from flask_restplus import fields
from flask_restplus import reqparse
from flask_restplus import abort
from flask_restplus import inputs

from recommendation.utils import event_logger
from recommendation.utils import language_pairs
from recommendation.utils import configuration
from recommendation.api import helper
from recommendation.api.types.translation import filters
from recommendation.api.types.translation import candidate_finders
from recommendation.api.types.translation import pageviews

log = logging.getLogger(__name__)

legacy = helper.build_api('legacy', __name__, url_prefix='/api')

ArticleSpec = collections.namedtuple('Article', ['pageviews', 'title', 'wikidata_id'])

legacy_params = reqparse.RequestParser()

legacy_params.add_argument(
    's',
    type=str,
    dest='source',
    required=True)
legacy_params.add_argument(
    't',
    type=str,
    dest='target',
    required=True)
legacy_params.add_argument(
    'n',
    type=inputs.int_range(low=0, high=configuration.get_config_int('api', 'count_max')),
    dest='count',
    required=False,
    default=configuration.get_config_int('api', 'count_default'))
legacy_params.add_argument(
    'article',
    type=inputs.regex(r'^([^|]+(\|[^|]+)*)?$'),
    dest='seed',
    required=False)
legacy_params.add_argument(
    'pageviews',
    type=inputs.boolean,
    dest='include_pageviews',
    required=False,
    default=True)
legacy_params.add_argument(
    'search',
    type=str,
    required=False,
    default='morelike',
    choices=['morelike', 'wiki'])

legacy_model = legacy.model(ArticleSpec.__name__, ArticleSpec(
    pageviews=fields.Integer(description='pageviews', required=False),
    title=fields.String(description='title', required=True),
    wikidata_id=fields.String(description='wikidata_id', required=True)
)._asdict())

legacy_doc = dict(description='Gets recommendations of source articles that are missing in the target',
                  params=dict(s='Source wiki project language code',
                              t='Target wiki project language code',
                              n='Number of recommendations to fetch',
                              article='Seed article for personalized recommendations '
                                      'that can also be a list separated by "|"',
                              pageviews='Whether to include pageview counts',
                              search='Which search algorithm to use if a seed is specified')
                  )


@legacy.deprecated
@legacy.route('/')
class LegacyArticle(flask_restplus.Resource):
    @legacy.expect(legacy_params)
    @legacy.marshal_with(legacy_model, as_list=True)
    @legacy.doc(**legacy_doc)
    def get(self):
        args = legacy_params.parse_args()
        return process_request(args)


api = helper.build_api('translation', __name__, url_prefix='/types/translation')
v1 = helper.build_namespace(api, 'v1', description='')

v1_params = reqparse.RequestParser()

v1_params.add_argument(
    'source',
    type=str,
    required=True)
v1_params.add_argument(
    'target',
    type=str,
    required=True)
v1_params.add_argument(
    'count',
    type=inputs.int_range(low=0, high=configuration.get_config_int('api', 'count_max')),
    required=False,
    default=configuration.get_config_int('api', 'count_default'))
v1_params.add_argument(
    'seed',
    type=inputs.regex(r'^([^|]+(\|[^|]+)*)?$'),
    required=False)
v1_params.add_argument(
    'include_pageviews',
    type=inputs.boolean,
    required=False,
    default=True)
v1_params.add_argument(
    'search',
    type=str,
    required=False,
    default='morelike',
    choices=['morelike', 'wiki', 'related_articles'])

v1_model = legacy.clone(ArticleSpec.__name__, legacy_model)
v1_doc = dict(description='Gets recommendations of source articles that are missing in the target',
              params=dict(source='Source wiki project language code',
                          target='Target wiki project language code',
                          count='Number of recommendations to fetch',
                          seed='Seed article for personalized recommendations '
                               'that can also be a list separated by "|"',
                          include_pageviews='Whether to include pageview counts',
                          search='Which search algorithm to use if a seed is specified')
              )


@v1.route('/articles')
class Article(flask_restplus.Resource):
    @v1.expect(v1_params)
    @v1.marshal_with(v1_model, as_list=True)
    @v1.doc(**v1_doc)
    def get(self):
        args = v1_params.parse_args()
        return process_request(args)


article_model = v1.model(ArticleSpec.__name__, ArticleSpec(
    pageviews=fields.Integer(description='pageviews', required=False),
    title=fields.String(description='title', required=True),
    wikidata_id=fields.String(description='wikidata_id', required=True)
)._asdict())


def process_request(args):
    t1 = time.time()

    if not language_pairs.is_valid_language_pair(args['source'], args['target']):
        abort(400, errors='Invalid or duplicate source and/or target language')

    event_logger.log_api_request(**args)
    recs = recommend(**args)
    t2 = time.time()
    log.info('Request processed in %f seconds', t2 - t1)
    return recs


finder_map = {
    'morelike': candidate_finders.MorelikeCandidateFinder(),
    'wiki': candidate_finders.MorelikeCandidateFinder(),
    'mostpopular': candidate_finders.PageviewCandidateFinder(),
    'related_articles': candidate_finders.RelatedArticleFinder()
}


def recommend(source, target, search, seed, count, include_pageviews, max_candidates=500):
    """
    1. Use finder to select a set of candidate articles
    2. Filter out candidates that are not missing, are disambiguation pages, etc
    3. get pageview info for each passing candidate if desired
    """

    recs = []

    if seed:
        finder = finder_map[search]
        for seed in seed.split('|'):
            recs.extend(finder.get_candidates(source, seed, max_candidates))
    else:
        recs.extend(finder_map['mostpopular'].get_candidates(source, seed, max_candidates))

    recs = sorted(recs, key=lambda x: x.rank)

    recs = filters.apply_filters(source, target, recs, count)

    if recs and include_pageviews:
        recs = pageviews.set_pageview_data(source, recs)

    recs = sorted(recs, key=lambda x: x.rank)
    return [{'title': r.title, 'pageviews': r.pageviews, 'wikidata_id': r.wikidata_id} for r in recs]
