import httpx
import pytest
import respx

from wayfinder.providers.errors import ProviderRequestError
from wayfinder.providers.wikivoyage import PageNotFound, WikivoyageClient
from wayfinder.providers.wikivoyage.client import nearby_params

from .conftest import TEST_UA, WIKIVOYAGE_API

KYOTO_DISTRICTS = {"Kyoto/Arashiyama", "Kyoto/Central", "Kyoto/Higashiyama", "Kyoto/North", "Kyoto/South"}


# Recorded responses (tests/fixtures/wikivoyage, refresh with scripts/capture_fixtures.py)

async def test_search_returns_plain_text_snippets(wv_client, recorded_api):
    results = await wv_client.search("Kyoto", limit=5)
    assert results[0].title == "Kyoto"
    assert all("<" not in r.snippet for r in results)


async def test_resolve_existing_page(wv_client, recorded_api):
    page = await wv_client.resolve("Kyoto")
    assert page.exists and page.title == "Kyoto"
    assert page.wikidata == "Q34600"
    assert not page.is_disambiguation and page.redirected_from is None


async def test_resolve_follows_redirect(wv_client, recorded_api):
    page = await wv_client.resolve("Peking")
    assert page.title == "Beijing"
    assert page.redirected_from == "Peking"


async def test_resolve_flags_disambiguation(wv_client, recorded_api):
    page = await wv_client.resolve("Springfield")
    assert page.exists and page.is_disambiguation


async def test_resolve_missing_page_does_not_raise(wv_client, recorded_api):
    page = await wv_client.resolve("Nonexistentplacexyz")
    assert not page.exists and page.pageid is None


async def test_get_page_returns_wikitext_sections_and_revision(wv_client, recorded_api):
    page = await wv_client.get_page("Kyoto")
    assert page.revid > 0
    assert "{{pagebanner" in page.wikitext
    top_level = [s.title for s in page.sections if s.level == 2]
    assert {"Districts", "Understand", "Get in", "Get around", "See"} <= set(top_level)
    assert "{{Regionlist" in page.wikitext or "{{regionlist" in page.wikitext.lower()


async def test_section_offsets_point_at_headings(wv_client, recorded_api):
    page = await wv_client.get_page("Kyoto/Higashiyama")
    located = [s for s in page.sections if s.char_offset is not None]
    assert located
    for section in located:
        heading = "=" * section.level
        assert page.wikitext[section.char_offset:].startswith(heading), section.title


async def test_get_page_follows_redirect(wv_client, recorded_api):
    page = await wv_client.get_page("Peking")
    assert page.title == "Beijing" and page.redirected_from == "Peking"


async def test_get_page_missing_raises(wv_client, recorded_api):
    with pytest.raises(PageNotFound):
        await wv_client.get_page("Nonexistentplacexyz")


async def test_get_summary(wv_client, recorded_api):
    summary = await wv_client.get_summary("Kyoto")
    assert summary.title == "Kyoto" and "Kyōto" in summary.extract


async def test_get_summary_missing_raises(wv_client, recorded_api):
    with pytest.raises(PageNotFound):
        await wv_client.get_summary("Nonexistentplacexyz")


async def test_nearby_finds_districts_closest_first(wv_client, recorded_api):
    pages = await wv_client.nearby(35.0116, 135.7681)
    assert KYOTO_DISTRICTS <= {p.title for p in pages}
    distances = [p.distance_m for p in pages]
    assert distances == sorted(distances)


# Behaviour that recorded fixtures can't show

@respx.mock
async def test_maxlag_error_is_retried(wv_client, sleep):
    maxlag = httpx.Response(200, json={"error": {"code": "maxlag", "info": "lagged"}}, headers={"Retry-After": "5"})
    ok = httpx.Response(200, json={"query": {"search": []}})
    route = respx.get(WIKIVOYAGE_API).mock(side_effect=[maxlag, ok])
    assert await wv_client.search("Kyoto") == []
    assert route.call_count == 2
    assert sleep.longest == pytest.approx(5, abs=0.1)


@respx.mock
async def test_every_request_sends_defaults_and_user_agent(wv_client):
    route = respx.get(WIKIVOYAGE_API).mock(return_value=httpx.Response(200, json={"query": {"search": []}}))
    await wv_client.search("Kyoto")
    request = route.calls.last.request
    assert request.headers["User-Agent"] == TEST_UA
    params = request.url.params
    assert (params["format"], params["formatversion"], params["maxlag"]) == ("json", "2", "5")


@respx.mock
async def test_forbidden_user_agent_surfaces_clearly(wv_client):
    respx.get(WIKIVOYAGE_API).mock(return_value=httpx.Response(403, text="Please set a user-agent"))
    with pytest.raises(ProviderRequestError, match="403"):
        await wv_client.search("Kyoto")


def test_nearby_params_validate_and_clamp():
    assert nearby_params(35.0, 135.7, radius_m=50_000)["gsradius"] == "10000"
    with pytest.raises(ValueError):
        nearby_params(135.0, 35.0)


def test_page_url():
    client = WikivoyageClient(TEST_UA)
    assert client.page_url("Kyoto/Higashiyama") == "https://en.wikivoyage.org/wiki/Kyoto/Higashiyama"
    assert client.page_url("Mount Hiei") == "https://en.wikivoyage.org/wiki/Mount_Hiei"


# Live smoke test: uv run pytest -m live

@pytest.mark.live
async def test_live_kyoto():
    async with WikivoyageClient.from_settings() as client:
        page = await client.get_page("Kyoto")
        assert page.title == "Kyoto" and page.sections
