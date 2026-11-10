"""HTTP API tests, served from the recorded Wikivoyage fixtures (no network)."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from wayfinder.api.app import create_app
from wayfinder.providers.wikivoyage import WikivoyageClient

from .conftest import TEST_UA, WIKIVOYAGE_API


async def _no_sleep(_: float) -> None:
    return None


@pytest.fixture
def api(recorded_api):
    app = create_app(lambda: WikivoyageClient(TEST_UA, sleep=_no_sleep))
    with TestClient(app) as client:
        yield client


def test_health(api):
    assert api.get("/health").json()["status"] == "ok"


def test_search(api):
    results = api.get("/search", params={"q": "Kyoto", "limit": 5}).json()
    assert results[0]["title"] == "Kyoto"


def test_resolve_redirect_and_disambiguation(api):
    assert api.get("/resolve", params={"title": "Peking"}).json()["redirected_from"] == "Peking"
    assert api.get("/resolve", params={"title": "Springfield"}).json()["is_disambiguation"] is True


def test_summary(api):
    assert "Kyōto" in api.get("/summary", params={"title": "Kyoto"}).json()["extract"]


def test_article(api):
    article = api.get("/article", params={"title": "Kyoto"}).json()
    assert (article["kind"], article["status"]) == ("city", "guide")
    assert len(article["districts"]) == 5
    assert article["source"]["license"] == "CC BY-SA 4.0"


def test_sections_filtered_by_heading(api):
    body = api.get("/sections", params=[("title", "Kyoto"), ("section", "Get in"), ("section", "get around")]).json()
    assert body["count"] > 0
    assert {s["path"][0] for s in body["sections"]} == {"Get in", "Get around"}
    assert body["available"][:3] == ["Districts", "Understand", "Get in"]


def test_sections_filter_with_no_match_lists_available(api):
    body = api.get("/sections", params={"title": "Kyoto", "section": "Stay safe"}).json()
    assert body["count"] == 0 and "Get in" in body["available"]


def test_listings_with_slash_in_title_and_type_filter(api):
    body = api.get("/listings", params=[("title", "Kyoto/Higashiyama"), ("type", "eat"), ("type", "drink")]).json()
    assert body["title"] == "Kyoto/Higashiyama"
    assert body["total"] == 10 and body["returned"] == 10
    assert {item["type"] for item in body["listings"]} == {"eat", "drink"}


def test_listings_limit(api):
    body = api.get("/listings", params={"title": "Kyoto/Higashiyama", "limit": 3}).json()
    assert (body["total"], body["returned"], len(body["listings"])) == (59, 3, 3)


def test_nearby(api):
    pages = api.get("/nearby", params={"lat": 35.0116, "lon": 135.7681}).json()
    assert "Kyoto/Higashiyama" in {p["title"] for p in pages}


def test_missing_page_is_404(api):
    response = api.get("/article", params={"title": "Nonexistentplacexyz"})
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_invalid_input_is_422(api):
    assert api.get("/listings", params={"title": "Kyoto", "type": "museum"}).status_code == 422
    assert api.get("/nearby", params={"lat": 135, "lon": 35}).status_code == 422
    assert api.get("/search").status_code == 422


def test_upstream_rate_limit_is_passed_on():
    with respx.mock:
        respx.get(WIKIVOYAGE_API).mock(return_value=httpx.Response(429, headers={"Retry-After": "600"}))
        app = create_app(lambda: WikivoyageClient(TEST_UA, sleep=_no_sleep))
        with TestClient(app) as client:
            response = client.get("/search", params={"q": "Kyoto"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "601"
    assert response.json()["error"] == "rate_limited"
