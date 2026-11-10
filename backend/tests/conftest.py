import json
from pathlib import Path

import httpx
import pytest
import respx

from wayfinder.providers.wikivoyage.client import DEFAULT_PARAMS, WikivoyageClient, parse_page
from wayfinder.providers.wikivoyage.models import PageContent

FIXTURES = Path(__file__).parent / "fixtures" / "wikivoyage"
WIKIVOYAGE_API = "https://en.wikivoyage.org/w/api.php"
TEST_UA = "WayFinder/0.1 (https://github.com/risal-ea/wayFinder; tests) httpx"


def load_page(name: str) -> PageContent:
    """A recorded `get_page` result, e.g. load_page("Kyoto_Higashiyama")."""
    payload = json.loads((FIXTURES / f"page__{name}.json").read_text(encoding="utf-8"))
    return parse_page(payload)


class SleepRecorder:
    """Stands in for asyncio.sleep: records waits instead of sleeping."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)

    @property
    def longest(self) -> float:
        return max(self.calls, default=0.0)


@pytest.fixture
def sleep() -> SleepRecorder:
    return SleepRecorder()


@pytest.fixture
async def wv_client(sleep: SleepRecorder):
    client = WikivoyageClient(TEST_UA, sleep=sleep)
    yield client
    await client.aclose()


@pytest.fixture
def recorded_api():
    """Serve the captured fixtures for any request whose params match the manifest exactly."""
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))

    def respond(request: httpx.Request) -> httpx.Response:
        params = {k: v for k, v in request.url.params.items() if k not in DEFAULT_PARAMS}
        for entry in manifest:
            if entry["params"] == params:
                body = (FIXTURES / entry["file"]).read_bytes()
                return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})
        raise AssertionError(f"no recorded fixture for params {params}")

    with respx.mock(assert_all_called=False) as router:
        route = router.get(WIKIVOYAGE_API).mock(side_effect=respond)
        yield route
