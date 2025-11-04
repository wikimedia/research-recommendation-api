import pytest
from httpx import ASGITransport, AsyncClient

from recommendation.cache import get_sitematrix_cache
from recommendation.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def setup_test_language_codes():
    """Setup basic language codes for testing"""
    cache = get_sitematrix_cache()
    # Add basic language codes that should be valid for tests
    # Include special language codes that have domain mappings
    language_codes = [
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "ru",
        "zh",
        "ja",
        "ar",
        "be-tarask",
        "bho",
        "gsw",
        "lzh",
        "nan",
        "nb",
        "rup",
        "sgs",
        "vro",
        "yue",
    ]
    cache.set_language_codes(language_codes)
    return cache


@pytest.fixture(scope="session")
async def client(setup_test_language_codes):
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
    assert "wikidata_id" in results[0]  # Field should exist, even if None
    assert results[0].get("rank") > 0
    assert results[0].get("langlinks_count") >= 0
    assert results[0].get("size") > 0


@pytest.mark.anyio
async def test_recommendations_mostpopular(client: AsyncClient):
    response = await client.get("/v1/translation?source=en&target=es&search_algorithm=mostpopular")
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert results[0].get("title")
    assert results[0].get("pageviews") == 0
    assert "wikidata_id" in results[0]  # Field should exist, even if None
    assert results[0].get("rank") > 0
    assert results[0].get("langlinks_count") >= 0
    assert results[0].get("size") > 0


@pytest.mark.anyio
async def test_recommendations_country(client: AsyncClient):
    response = await client.get("/v1/translation?source=en&target=es&country=ita")
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert results[0].get("title")
    assert results[0].get("pageviews") == 0
    assert "wikidata_id" in results[0]  # Field should exist, even if None
    assert results[0].get("rank") > 0
    assert results[0].get("langlinks_count") >= 0
    assert results[0].get("size") > 0


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
    assert "wikidata_id" in results[0]  # Field should exist, even if None
    assert results[0].get("rank") > 0
    assert results[0].get("langlinks_count") >= 0
    assert results[0].get("size") > 0


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
    assert results[0].get("missing"), results[0].get("source_title")
