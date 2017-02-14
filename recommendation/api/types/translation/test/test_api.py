import flask
import pytest
import json
import urllib.parse

from recommendation.api.types.translation import translation
from recommendation.api.types.translation import filters
from recommendation.api.types.translation import recommendation

GOOD_RESPONSE = [
    {'title': 'A', 'pageviews': 9, 'wikidata_id': '123', 'rank': 9.0},
    {'title': 'B', 'pageviews': 8, 'wikidata_id': '122', 'rank': 8.0},
    {'title': 'C', 'pageviews': 7, 'wikidata_id': '121', 'rank': 7.0},
    {'title': 'D', 'pageviews': 6, 'wikidata_id': '120', 'rank': 6.0},
    {'title': 'E', 'pageviews': 5, 'wikidata_id': '119', 'rank': 5.0},
    {'title': 'F', 'pageviews': 4, 'wikidata_id': '118', 'rank': 4.0},
    {'title': 'G', 'pageviews': 3, 'wikidata_id': '117', 'rank': 3.0},
    {'title': 'H', 'pageviews': 2, 'wikidata_id': '116', 'rank': 2.0}
]


@pytest.fixture(params=[
    '/types/translation/v1/articles',
    '/api/'
])
def get_url(request):
    legacy_to_v1 = {'s': 'source',
                    't': 'target',
                    'n': 'count',
                    'article': 'seed',
                    'pageviews': 'include_pageviews'}
    return lambda input_dict: request.param + '?' + urllib.parse.urlencode(
        {legacy_to_v1.get(k, k): v for k, v in input_dict.items()} if 'v1' in request.param else input_dict)


@pytest.fixture
def recommend_response(monkeypatch):
    monkeypatch.setattr(translation, 'recommend', lambda *args, **kwargs: GOOD_RESPONSE)


@pytest.fixture
def client():
    app_instance = flask.Flask(__name__)
    app_instance.register_blueprint(translation.api.blueprint)
    app_instance.register_blueprint(translation.legacy.blueprint)
    app_instance.testing = True
    return app_instance.test_client()


@pytest.mark.parametrize('params', [
    dict(s='xx', t='yy'),
    dict(s='xx', t='yy', n=13),
    dict(s='xx', t='yy', article='separated|list|of|titles'),
    dict(s='xx', t='yy', article='Some Article'),
    dict(s='xx', t='yy', article=''),
    dict(s='xx', t='yy', pageviews='false'),
    dict(s='xx', t='yy', search='morelike'),
    dict(s='xx', t='yy', search='wiki'),
])
@pytest.mark.usefixtures('recommend_response')
def test_good_arg_parsing(client, get_url, params):
    result = client.get(get_url(params))
    assert 200 == result.status_code
    assert GOOD_RESPONSE == json.loads(result.data.decode('utf-8'))


@pytest.mark.parametrize('value,expected', [
    ('false', False),
    ('true', True),
    ('False', False),
    ('True', True),
    (1, True),
    (0, False)
])
def test_boolean_arg_parsing(client, get_url, value, expected):
    with client as c:
        url = get_url(dict(s='xx', t='yy', pageviews=value))
        c.get(url)
        if 'v1' in url:
            args = translation.get_v1_params().parse_args()
        else:
            args = translation.get_legacy_params().parse_args()

    assert expected is args['include_pageviews']


@pytest.mark.parametrize('params', [
    dict(s='xx'),
    dict(t='xx'),
    {},
    dict(s='xx', t='xx'),
    dict(s='xx', t='yy', n=-1),
    dict(s='xx', t='yy', n=25),
    dict(s='xx', t='yy', n='not a number'),
    dict(s='xx', t='yy', article='||||||||||||'),
    dict(s='xx', t='yy', pageviews='not a boolean'),
    dict(s='xx', t='yy', search='not a valid search'),
])
@pytest.mark.usefixtures('recommend_response')
def test_bad_args(client, get_url, params):
    result = client.get(get_url(params))
    assert 'errors' in json.loads(result.data.decode('utf-8'))


@pytest.mark.parametrize('params', [
    dict(s='xx', t='yy'),
])
def test_default_params(client, get_url, params):
    with client as c:
        url = get_url(params)
        c.get(url)
        if 'v1' in url:
            args = translation.get_v1_params().parse_args()
        else:
            args = translation.get_legacy_params().parse_args()
    assert 12 == args['count']
    assert None is args['seed']
    assert True is args['include_pageviews']
    assert 'morelike' == args['search']


def test_recommend_uses_mostpopular_if_no_seed_is_specified(monkeypatch):
    def mock_finder(*_):
        return []

    monkeypatch.setattr(translation, 'finder_map', {'mostpopular': mock_finder})
    result = translation.recommend(source='xx', target='yy', search='customsearch', seed=None, count=12,
                                   include_pageviews=True)
    assert [] == result


def test_generated_recommend_response_is_marshalled(client, get_url, monkeypatch):
    def mock_finder(*_):
        articles = []
        for item in GOOD_RESPONSE:
            article = recommendation.Recommendation(item['title'])
            article.pageviews = item['pageviews']
            article.wikidata_id = item['wikidata_id']
            article.rank = item['rank']
            articles.append(article)
        return articles

    monkeypatch.setattr(translation, 'finder_map', {'mostpopular': mock_finder})
    monkeypatch.setattr(filters, 'apply_filters', lambda source, target, recs: recs)
    result = client.get(get_url(dict(s='xx', t='yy', pageviews=False)))
    assert GOOD_RESPONSE == json.loads(result.data.decode('utf-8'))


@pytest.mark.usefixtures('recommend_response')
def test_cors_is_present(client, get_url):
    result = client.get(get_url(dict(s='xx', t='yy')))
    assert '*' == result.headers.get('Access-Control-Allow-Origin')
