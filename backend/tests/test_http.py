import asyncio
import logging

import httpx
import pytest
import respx

from wayfinder.providers.errors import ProviderRateLimited, ProviderRequestError, ProviderUnavailable
from wayfinder.providers.http import ProviderHTTPClient, parse_retry_after

BASE = "https://api.example.test/"
URL = BASE + "data"


@pytest.fixture
async def client(sleep):
    c = ProviderHTTPClient(
        provider="example",
        base_url=BASE,
        user_agent="WayFinder/0.1 (tests)",
        min_interval=0.0,
        default_params={"format": "json"},
        should_retry_payload=lambda p: p.get("error") == "busy",
        sleep=sleep,
    )
    yield c
    await c.aclose()


OK = httpx.Response(200, json={"ok": True})


@respx.mock
async def test_sends_user_agent_and_default_params(client):
    route = respx.get(URL).mock(return_value=OK)
    assert await client.get_json("data", {"q": "kyoto"}) == {"ok": True}
    request = route.calls.last.request
    assert request.headers["User-Agent"] == "WayFinder/0.1 (tests)"
    assert dict(request.url.params) == {"format": "json", "q": "kyoto"}


def test_refuses_empty_user_agent():
    with pytest.raises(ValueError, match="User-Agent"):
        ProviderHTTPClient(provider="example", base_url=BASE, user_agent="  ")


@respx.mock
@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(200, content=b""),
        httpx.Response(200, content=b"<html>not json</html>"),
        httpx.Response(503),
        httpx.Response(200, json={"error": "busy"}),
        httpx.ReadTimeout("slow"),
        httpx.ConnectError("down"),
    ],
    ids=["empty-body", "invalid-json", "503", "payload-retry", "timeout", "connect-error"],
)
async def test_retries_transient_failures_then_succeeds(client, failure):
    route = respx.get(URL).mock(side_effect=[failure, OK])
    assert await client.get_json("data") == {"ok": True}
    assert route.call_count == 2


@respx.mock
async def test_429_honours_retry_after(client, sleep):
    respx.get(URL).mock(side_effect=[httpx.Response(429, headers={"Retry-After": "7"}), OK])
    assert await client.get_json("data") == {"ok": True}
    assert sleep.longest == pytest.approx(7, abs=0.1)


@respx.mock
async def test_429_without_retry_after_waits_at_least_5s(client, sleep):
    respx.get(URL).mock(side_effect=[httpx.Response(429), OK])
    await client.get_json("data")
    assert sleep.longest == pytest.approx(5, abs=0.1)


@respx.mock
async def test_payload_retry_uses_retry_after_header(client, sleep):
    busy = httpx.Response(200, json={"error": "busy"}, headers={"Retry-After": "3"})
    respx.get(URL).mock(side_effect=[busy, OK])
    await client.get_json("data")
    assert sleep.longest == pytest.approx(3, abs=0.1)


@respx.mock
async def test_gives_up_after_max_retries(client):
    route = respx.get(URL).mock(return_value=httpx.Response(502))
    with pytest.raises(ProviderUnavailable, match="HTTP 502"):
        await client.get_json("data")
    assert route.call_count == 4  # first try + 3 retries


@respx.mock
async def test_persistent_429_raises_rate_limited(client):
    respx.get(URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "2"}))
    with pytest.raises(ProviderRateLimited) as exc_info:
        await client.get_json("data")
    assert exc_info.value.retry_after == 2


@respx.mock
async def test_long_retry_after_is_raised_not_slept(client, sleep):
    route = respx.get(URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "600"}))
    with pytest.raises(ProviderRateLimited) as exc_info:
        await client.get_json("data")
    assert exc_info.value.retry_after == 600
    assert route.call_count == 1
    assert sleep.longest < 1


@respx.mock
async def test_client_errors_are_not_retried(client):
    route = respx.get(URL).mock(return_value=httpx.Response(403, text="Please set a user-agent"))
    with pytest.raises(ProviderRequestError) as exc_info:
        await client.get_json("data")
    assert exc_info.value.status == 403
    assert "user-agent" in str(exc_info.value)
    assert route.call_count == 1


@respx.mock
async def test_requests_are_serialised_and_spaced(sleep):
    in_flight = 0
    peak = 0

    async def slow(request):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return httpx.Response(200, json={"ok": True})

    respx.get(URL).mock(side_effect=slow)
    async with ProviderHTTPClient(
        provider="example", base_url=BASE, user_agent="ua", min_interval=0.5, sleep=sleep
    ) as client:
        await asyncio.gather(*(client.get_json("data") for _ in range(3)))

    assert peak == 1
    # The fake sleep doesn't advance the clock, so waits are measured from the first
    # request: the 2nd starts 0.5 s after it, the 3rd 1.0 s after it.
    assert sleep.calls == pytest.approx([0.5, 1.0], abs=0.1)


@respx.mock
async def test_secrets_are_redacted_in_logs(client, caplog):
    respx.get(URL).mock(return_value=OK)
    with caplog.at_level(logging.INFO, logger="wayfinder.http"):
        await client.get_json("data", {"apikey": "s3cret", "name": "Kyoto"})
    assert "s3cret" not in caplog.text
    assert "apikey=***" in caplog.text and "name=Kyoto" in caplog.text


def test_parse_retry_after():
    assert parse_retry_after(None) is None
    assert parse_retry_after("12") == 12
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0  # date in the past
    assert parse_retry_after("soon") is None
