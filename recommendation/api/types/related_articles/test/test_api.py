import flask
import pytest
import json
import urllib.parse

from recommendation.api.types.related_articles import related_articles

GOOD_RESPONSE = [
    {'title': 'A', 'wikidata_id': '123', 'url': 'some/url/A', 'score': 0.1},
    {'title': 'B', 'wikidata_id': '122', 'url': 'some/url/B', 'score': 0.2},
    {'title': 'C', 'wikidata_id': '121', 'url': 'some/url/C', 'score': 0.3},
    {'title': 'D', 'wikidata_id': '120', 'url': 'some/url/D', 'score': 0.4},
    {'title': 'E', 'wikidata_id': '119', 'url': 'some/url/E', 'score': 0.5},
    {'title': 'F', 'wikidata_id': '118', 'url': 'some/url/F', 'score': 0.6},
    {'title': 'G', 'wikidata_id': '117', 'url': 'some/url/G', 'score': 0.7},
    {'title': 'H', 'wikidata_id': '116', 'url': 'some/url/H', 'score': 0.8},
]


@pytest.fixture(params=[
    '/types/related_articles/v1/articles'
])
def get_url(request):
    return lambda input_dict: request.param + '?' + urllib.parse.urlencode(input_dict)


@pytest.fixture
def recommend_response(monkeypatch):
    monkeypatch.setattr(related_articles, 'recommend', lambda *args, **kwargs: GOOD_RESPONSE)


@pytest.fixture
def client():
    app_instance = flask.Flask(__name__)
    app_instance.register_blueprint(related_articles.api.blueprint)
    app_instance.testing = True
    return app_instance.test_client()


@pytest.mark.parametrize('params', [
    dict(source='xx', count=13, seed='Some Article'),
    dict(source='xx', seed='separated|list|of|titles'),
    dict(source='xx', seed='Some Article'),
])
@pytest.mark.usefixtures('recommend_response')
def test_good_arg_parsing(client, get_url, params):
    result = client.get(get_url(params))
    assert 200 == result.status_code
    assert GOOD_RESPONSE == json.loads(result.data.decode('utf-8'))


@pytest.mark.parametrize('params', [
    dict(source='xx'),
    {},
    dict(source='xx', count=-1),
    dict(source='xx', count=25),
    dict(source='xx', count='not a number'),
    dict(source='xx', seed='||||||||||||'),
    dict(source='xx', seed='')
])
@pytest.mark.usefixtures('recommend_response')
def test_bad_args(client, get_url, params):
    result = client.get(get_url(params))
    assert 'errors' in json.loads(result.data.decode('utf-8'))


@pytest.mark.parametrize('params', [
    dict(source='xx', seed='Some Article'),
])
def test_default_params(client, get_url, params):
    with client as c:
        c.get(get_url(params))
        args = related_articles.v1_articles_params.parse_args()
    assert 12 == args['count']


@pytest.mark.usefixtures('recommend_response')
def test_generated_recommend_response_is_marshalled(client, get_url, monkeypatch):
    result = client.get(get_url(dict(source='xx', seed='Some Article')))
    assert GOOD_RESPONSE == json.loads(result.data.decode('utf-8'))


@pytest.mark.usefixtures('recommend_response')
def test_cors_is_present(client, get_url):
    result = client.get(get_url(dict(source='xx', seed='Some Article')))
    assert '*' == result.headers.get('Access-Control-Allow-Origin')
