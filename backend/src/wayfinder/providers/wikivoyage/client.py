"""Raw Wikivoyage (MediaWiki Action API) client.

Thin methods that fetch and return typed API results; no wikitext parsing.
Each call is split into a params builder, the request, and a response parser,
so `scripts/capture_fixtures.py` can save the exact raw responses the tests use.

Behaviour of the live API that this relies on (checked Nov 2026):
- errors arrive as HTTP 200 with `{"error": {"code": ..., "info": ...}}`
- replication lag arrives as error code `maxlag` plus a `Retry-After` header
- disambiguation pages have a `disambiguation` page property
- requests without a descriptive User-Agent get HTTP 403
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from wayfinder.config import Settings, get_settings
from wayfinder.providers.errors import ProviderError
from wayfinder.providers.http import ProviderHTTPClient, Sleep
from wayfinder.providers.wikivoyage.models import (
    NearbyPage,
    PageContent,
    ResolvedPage,
    SearchResult,
    SectionInfo,
    Summary,
)

logger = logging.getLogger("wayfinder.wikivoyage")

PROVIDER = "wikivoyage"
API_PATH = "api.php"
DEFAULT_PARAMS = {"format": "json", "formatversion": "2", "maxlag": "5"}
MAX_GEOSEARCH_RADIUS_M = 10_000


class WikivoyageApiError(ProviderError):
    def __init__(self, code: str, info: str) -> None:
        super().__init__(PROVIDER, f"{code}: {info}")
        self.code = code
        self.info = info


class PageNotFound(WikivoyageApiError):
    def __init__(self, title: str) -> None:
        super().__init__("missingtitle", f"no Wikivoyage article named {title!r}")
        self.title = title


def is_maxlag(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("error", {}).get("code") == "maxlag"


class WikivoyageClient:
    def __init__(
        self,
        user_agent: str,
        *,
        lang: str = "en",
        timeout: float = 30.0,
        min_interval: float = 0.2,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.lang = lang
        self._http = ProviderHTTPClient(
            provider=PROVIDER,
            # httpx appends "/" to base_url, so the script name must be the request path.
            base_url=f"https://{lang}.wikivoyage.org/w/",
            user_agent=user_agent,
            timeout=timeout,
            max_concurrency=1,  # Wikimedia etiquette: one request at a time
            min_interval=min_interval,
            max_retries=max_retries,
            default_params=DEFAULT_PARAMS,
            should_retry_payload=is_maxlag,
            transport=transport,
            sleep=sleep,
        )

    @classmethod
    def from_settings(cls, settings: Settings | None = None, **kwargs: Any) -> WikivoyageClient:
        settings = settings or get_settings()
        return cls(
            settings.user_agent,
            lang=settings.wikivoyage_lang,
            timeout=settings.http_timeout,
            min_interval=settings.wikivoyage_min_interval,
            **kwargs,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> WikivoyageClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    def page_url(self, title: str) -> str:
        return f"https://{self.lang}.wikivoyage.org/wiki/{quote(title.replace(' ', '_'), safe='/:()')}"

    async def call(self, params: dict[str, str]) -> dict[str, Any]:
        """Run one API request and return the raw JSON. Raises on API errors."""
        payload = await self._http.get_json(API_PATH, params=params)
        if not isinstance(payload, dict):
            raise WikivoyageApiError("badresponse", f"expected a JSON object, got {type(payload).__name__}")
        if "error" in payload:
            error = payload["error"]
            raise WikivoyageApiError(error.get("code", "unknown"), error.get("info", ""))
        if "warnings" in payload:
            logger.warning("API warnings for %s: %s", params, payload["warnings"])
        return payload

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        return parse_search(await self.call(search_params(query, limit)))

    async def resolve(self, title: str) -> ResolvedPage:
        """Canonical title for `title`, following redirects. Does not raise if missing."""
        return parse_resolve(title, await self.call(resolve_params(title)))

    async def get_page(self, title: str) -> PageContent:
        """Full wikitext, section list and revision in one request."""
        try:
            payload = await self.call(page_params(title))
        except WikivoyageApiError as exc:
            if exc.code == "missingtitle":
                raise PageNotFound(title) from exc
            raise
        return parse_page(payload)

    async def get_summary(self, title: str) -> Summary:
        return parse_summary(title, await self.call(summary_params(title)))

    async def nearby(self, lat: float, lon: float, radius_m: int = MAX_GEOSEARCH_RADIUS_M, limit: int = 10) -> list[NearbyPage]:
        """Articles near a point, closest first."""
        return parse_nearby(await self.call(nearby_params(lat, lon, radius_m, limit)))


# Params builders. Values are strings so fixtures can match requests exactly.

def search_params(query: str, limit: int = 10) -> dict[str, str]:
    return {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": "0",
        "srlimit": str(_clamp(limit, 1, 50)),
        "srprop": "snippet",
    }


def resolve_params(title: str) -> dict[str, str]:
    return {
        "action": "query",
        "titles": title,
        "redirects": "1",
        "prop": "info|pageprops",
        "ppprop": "disambiguation|wikibase_item",
    }


def page_params(title: str) -> dict[str, str]:
    return {
        "action": "parse",
        "page": title,
        "prop": "wikitext|tocdata|revid",  # tocdata replaces the deprecated prop=sections
        "redirects": "1",
    }


def summary_params(title: str) -> dict[str, str]:
    return {
        "action": "query",
        "titles": title,
        "redirects": "1",
        "prop": "extracts",
        "exintro": "1",
        "explaintext": "1",
    }


def nearby_params(lat: float, lon: float, radius_m: int = MAX_GEOSEARCH_RADIUS_M, limit: int = 10) -> dict[str, str]:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"invalid coordinates: {lat}, {lon}")
    return {
        "action": "query",
        "list": "geosearch",
        "gscoord": f"{lat}|{lon}",
        "gsradius": str(_clamp(radius_m, 10, MAX_GEOSEARCH_RADIUS_M)),
        "gslimit": str(_clamp(limit, 1, 100)),
        "gsnamespace": "0",
    }


# Response parsers.

_TAG = re.compile(r"<[^>]+>")


def parse_search(payload: dict[str, Any]) -> list[SearchResult]:
    return [
        SearchResult(
            title=hit["title"],
            pageid=hit["pageid"],
            snippet=html.unescape(_TAG.sub("", hit.get("snippet", ""))).strip(),
        )
        for hit in payload.get("query", {}).get("search", [])
    ]


def parse_resolve(asked: str, payload: dict[str, Any]) -> ResolvedPage:
    query = payload.get("query", {})
    pages = query.get("pages", [])
    if not pages:
        return ResolvedPage(query=asked, title=asked, exists=False)
    page = pages[0]
    redirects = query.get("redirects", [])
    props = page.get("pageprops", {})
    exists = not page.get("missing") and not page.get("invalid")
    return ResolvedPage(
        query=asked,
        title=page["title"],
        exists=exists,
        pageid=page.get("pageid"),
        redirected_from=redirects[0]["from"] if redirects else None,
        is_disambiguation="disambiguation" in props,
        wikidata=props.get("wikibase_item"),
        last_revid=page.get("lastrevid"),
    )


def parse_page(payload: dict[str, Any]) -> PageContent:
    parse = payload["parse"]
    redirects = parse.get("redirects", [])
    return PageContent(
        title=parse["title"],
        pageid=parse["pageid"],
        revid=parse["revid"],
        wikitext=parse.get("wikitext", ""),
        sections=[_section(s) for s in parse.get("tocdata", {}).get("sections", [])],
        redirected_from=redirects[0]["from"] if redirects else None,
    )


def _section(raw: dict[str, Any]) -> SectionInfo:
    index = str(raw.get("index", ""))
    return SectionInfo(
        # Transcluded sections have indexes like "T-1"; keep them sortable but distinct.
        index=int(index) if index.isdigit() else -1,
        level=int(raw["hLevel"]),
        title=html.unescape(_TAG.sub("", raw["line"])),
        number=raw.get("number", ""),
        anchor=raw.get("anchor", ""),
        char_offset=raw.get("codepointOffset"),
    )


def parse_summary(asked: str, payload: dict[str, Any]) -> Summary:
    pages = payload.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or pages[0].get("invalid"):
        raise PageNotFound(asked)
    page = pages[0]
    return Summary(title=page["title"], pageid=page["pageid"], extract=page.get("extract", "").strip())


def parse_nearby(payload: dict[str, Any]) -> list[NearbyPage]:
    results = [
        NearbyPage(
            title=hit["title"],
            pageid=hit["pageid"],
            lat=hit["lat"],
            lon=hit["lon"],
            distance_m=hit["dist"],
        )
        for hit in payload.get("query", {}).get("geosearch", [])
    ]
    return sorted(results, key=lambda p: p.distance_m)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
