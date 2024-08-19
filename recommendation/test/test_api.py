import pytest
from httpx import ASGITransport, AsyncClient

from recommendation.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=f"http://test{app.root_path}") as client:
        yield client


@pytest.mark.anyio
async def test_read_openapi_docs(client: AsyncClient):
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_read_openapi_json(client: AsyncClient):
    response = await client.get("/openapi.json")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_language_pair_validation(client: AsyncClient):
    response = await client.get("/v1/translation?source=en&target=en&seed=Apple")
    assert response.status_code == 422
    assert response.json().get("detail")[0].get("msg") == "Value error, Source and target languages must be different"


@pytest.mark.anyio
async def test_language_validation(client: AsyncClient):
    response = await client.get("/v1/translation?source=x12&target=en&seed=Apple")
    assert response.status_code == 422
    assert response.json().get("detail")[0].get("msg") == "Value error, Invalid source language code"


@pytest.mark.anyio
async def test_recommendations_morelike(client: AsyncClient):
    response = await client.get("/v1/translation?source=en&target=es&seed=Apple&search_algorithm=morelike")
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert results[0].get("title")
    assert results[0].get("pageviews") == 0
    assert results[0].get("wikidata_id")
    assert results[0].get("rank") > 0
    assert results[0].get("langlinks_count") >= 0


@pytest.mark.anyio
async def test_recommendations_mostpopular(client: AsyncClient):
    response = await client.get("/v1/translation?source=en&target=es&seed=Moon&search_algorithm=morelike")
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert results[0].get("title")
    assert results[0].get("pageviews") == 0
    assert results[0].get("wikidata_id")
    assert results[0].get("rank") > 0
    assert results[0].get("langlinks_count") >= 0


@pytest.mark.anyio
async def test_recommendations_with_pageviews(client: AsyncClient):
    response = await client.get(
        "/v1/translation?source=en&target=es&seed=Apple&search_algorithm=morelike&include_pageviews=True"
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert results[0].get("title")
    assert results[0].get("pageviews") >= 0
    assert results[0].get("wikidata_id")
    assert results[0].get("rank") > 0
    assert results[0].get("langlinks_count") >= 0


@pytest.mark.anyio
async def test_section_recommendations(client: AsyncClient):
    response = await client.get(
        "/v1/translation/sections?source=en&target=es&seed=Apple&search_algorithm=morelike&count=12"
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 12
    assert results[0].get("source_title")
    assert results[0].get("target_title")
    assert results[0].get("source_sections")
    assert results[0].get("target_sections")
    assert results[0].get("present")
    assert results[0].get("missing")
