import re
import json
import urllib

import flask
import pytest
import responses

from recommendation.api.types.related_articles import related_articles
from recommendation.api.types.related_articles import candidate_finder
from recommendation.api.types.translation import translation
from recommendation.api.types.translation import filters
from recommendation.utils import configuration
from recommendation.api.external_data import wikidata

RELATED_ARTICLE_RESPONSE = [
    {
        "score": 1.0,
        "title": "Leonardo_DiCaprio",
        "url": "https://en.wikipedia.org/wiki/Leonardo_DiCaprio",
        "wikidata_id": "Q38111"
    },
    {
        "score": 0.8978985948847182,
        "title": "Leonardo_DiCaprio_filmography",
        "url": "https://en.wikipedia.org/wiki/Leonardo_DiCaprio_filmography",
        "wikidata_id": "Q6525967"
    },
    {
        "score": 0.8953459243768583,
        "title": "George_DiCaprio",
        "url": "https://en.wikipedia.org/wiki/George_DiCaprio",
        "wikidata_id": "Q5538516"
    },
    {
        "score": 0.8854479979147444,
        "title": "List_of_awards_and_nominations_received_by_Leonardo_DiCaprio",
        "url": "https://en.wikipedia.org/wiki/List_of_awards_and_nominations_received_by_Leonardo_DiCaprio",
        "wikidata_id": "Q6606737"
    },
    {
        "score": 0.8299793726014886,
        "title": "Toni_Garrn",
        "url": "https://en.wikipedia.org/wiki/Toni_Garrn",
        "wikidata_id": "Q64960"
    },
    {
        "score": 0.8118964694860049,
        "title": "What's_Eating_Gilbert_Grape",
        "url": "https://en.wikipedia.org/wiki/What%27s_Eating_Gilbert_Grape",
        "wikidata_id": "Q660894"
    },
    {
        "score": 0.7672587413550775,
        "title": "Erin_Heatherton",
        "url": "https://en.wikipedia.org/wiki/Erin_Heatherton",
        "wikidata_id": "Q235959"
    },
    {
        "score": 0.7619007144779639,
        "title": "Kate_Winslet",
        "url": "https://en.wikipedia.org/wiki/Kate_Winslet",
        "wikidata_id": "Q202765"
    },
    {
        "score": 0.751873479285607,
        "title": "Bar_Refaeli",
        "url": "https://en.wikipedia.org/wiki/Bar_Refaeli",
        "wikidata_id": "Q298197"
    },
    {
        "score": 0.7383579128165948,
        "title": "Titanic_(1997_film)",
        "url": "https://en.wikipedia.org/wiki/Titanic_(1997_film)",
        "wikidata_id": "Q44578"
    },
    {
        "score": 0.7360210451142972,
        "title": "The_Revenant_(2015_film)",
        "url": "https://en.wikipedia.org/wiki/The_Revenant_(2015_film)",
        "wikidata_id": "Q18002795"
    },
    {
        "score": 0.7256523780415556,
        "title": "Kelly_Rohrbach",
        "url": "https://en.wikipedia.org/wiki/Kelly_Rohrbach",
        "wikidata_id": "Q21997695"
    }
]


@pytest.fixture
def app():
    app_instance = flask.Flask(__name__)
    app_instance.register_blueprint(related_articles.api.blueprint)
    app_instance.register_blueprint(translation.api.blueprint)
    app_instance.testing = True
    app_instance.app_context().push()
    return app_instance


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def set_related_articles_response():
    related_articles_endpoint = configuration.get_config_value('endpoints', 'related_articles')
    responses.add(responses.GET, re.compile(r'{}.'.format(related_articles_endpoint)),
                  body=json.dumps(RELATED_ARTICLE_RESPONSE), status=200, content_type='application/json')


@pytest.fixture
def remove_filters(monkeypatch):
    monkeypatch.setattr(filters, 'apply_filters', lambda source, target, candidates, campaign: candidates)


@pytest.fixture
def set_wikidata_results_to_use_fixed_response(monkeypatch):
    def get_titles_from_wikidata_items(source, items):
        return [wikidata.WikidataItem(id=item['wikidata_id'],
                                      url=item['url'],
                                      title=item['title'],
                                      sitelink_count=1)
                for item in RELATED_ARTICLE_RESPONSE if item['wikidata_id'] in items]

    def get_wikidata_items_from_titles(source, titles):
        return [wikidata.WikidataItem(id=item['wikidata_id'],
                                      url=item['url'],
                                      title=item['title'],
                                      sitelink_count=1)
                for item in RELATED_ARTICLE_RESPONSE if item['title'] in titles]

    monkeypatch.setattr(wikidata, 'get_titles_from_wikidata_items', get_titles_from_wikidata_items)
    monkeypatch.setattr(wikidata, 'get_wikidata_items_from_titles', get_wikidata_items_from_titles)
    monkeypatch.setattr(candidate_finder, 'resolve_seed', lambda source, seed: seed)


@pytest.fixture
def expected_recommendations():
    return [{'title': item['title'],
             'pageviews': None,
             'wikidata_id': item['wikidata_id'],
             'rank': item['score']} for item in RELATED_ARTICLE_RESPONSE]


@pytest.fixture
def query_url():
    url = '/types/translation/v1/articles'
    url += '?' + urllib.parse.urlencode(dict(source='en',
                                             target='de',
                                             seed=RELATED_ARTICLE_RESPONSE[0]['title'],
                                             search='related_articles',
                                             include_pageviews=False))
    return url


@pytest.mark.usefixtures('remove_filters', 'set_related_articles_response')
def test_results_are_kept_in_order(client, expected_recommendations, query_url):
    result = client.get(query_url)
    assert expected_recommendations == json.loads(result.data.decode('utf-8'))


@pytest.mark.usefixtures('remove_filters', 'set_related_articles_response')
def test_correct_endpoints_are_used(client, query_url):
    client.get(query_url)
    called_urls = [r.request.url for r in responses.calls]
    expected_urls = [configuration.get_config_value('endpoints', 'language_pairs'),
                     configuration.get_config_value('endpoints', 'event_logger'),
                     configuration.get_config_value('endpoints', 'related_articles')]
    for expected_url in expected_urls:
        assert any(expected_url in url for url in called_urls)
    assert 3 == len(responses.calls)


@pytest.mark.usefixtures('set_wikidata_results_to_use_fixed_response')
def test_related_articles_result(client):
    result = client.get('/types/related_articles/v1/articles?source=en&seed=Leonardo_DiCaprio')
    result = json.loads(result.data.decode('utf-8'))
    for expected, actual in zip(RELATED_ARTICLE_RESPONSE, result):
        for key in expected.keys():
            if key == 'score':
                assert pytest.approx(expected[key]) == actual[key]
            else:
                assert expected[key] == actual[key]


# math.isclose was added in 3.5
# https://www.python.org/dev/peps/pep-0485/#proposed-implementation
def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)
