"""HTTP API over the Wikivoyage client and parser.

    uv run uvicorn wayfinder.api.app:app --reload
    open http://localhost:8000/docs

A development API for trying the data layer from Postman or a browser. Titles go
in query params because they can contain "/" (e.g. "Kyoto/Higashiyama").
Each call fetches live (no cache until M3), one Wikivoyage request at a time.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from wayfinder import __version__
from wayfinder.domain.models import Article, Listing, ListingType, Section
from wayfinder.providers.errors import (
    ProviderRateLimited,
    ProviderRequestError,
    ProviderUnavailable,
)
from wayfinder.providers.wikivoyage import (
    NearbyPage,
    PageNotFound,
    ResolvedPage,
    SearchResult,
    Summary,
    WikivoyageApiError,
    WikivoyageClient,
)
from wayfinder.providers.wikivoyage.parser import ParsedArticle, parse_article

Title = Annotated[str, Query(min_length=1, description='Article title, e.g. "Kyoto" or "Kyoto/Higashiyama"')]


class SectionsResponse(BaseModel):
    title: str
    available: list[str]  # top-level headings on the page, for the `section` filter
    count: int
    sections: list[Section]


class ListingsResponse(BaseModel):
    title: str
    total: int        # listings on the page matching the type filter
    returned: int     # after `limit`
    listings: list[Listing]


def create_app(client_factory: Callable[[], WikivoyageClient] = WikivoyageClient.from_settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.wikivoyage = client_factory()
        yield
        await app.state.wikivoyage.aclose()

    app = FastAPI(title="WayFinder API", version=__version__, lifespan=lifespan)
    _add_error_handlers(app)

    def wv(request: Request) -> WikivoyageClient:
        return request.app.state.wikivoyage

    async def parsed(request: Request, title: str) -> ParsedArticle:
        client = wv(request)
        return parse_article(await client.get_page(title), lang=client.lang)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/search", tags=["wikivoyage"], summary="Find articles by name")
    async def search(
        request: Request, q: Annotated[str, Query(min_length=1)], limit: Annotated[int, Query(ge=1, le=50)] = 10
    ) -> list[SearchResult]:
        return await wv(request).search(q, limit)

    @app.get("/resolve", tags=["wikivoyage"], summary="Canonical title, redirect and disambiguation check")
    async def resolve(request: Request, title: Title) -> ResolvedPage:
        return await wv(request).resolve(title)

    @app.get("/summary", tags=["wikivoyage"], summary="Plain-text intro")
    async def summary(request: Request, title: Title) -> Summary:
        return await wv(request).get_summary(title)

    @app.get("/article", tags=["wikivoyage"], summary="Parsed article metadata, summary and districts")
    async def article(request: Request, title: Title) -> Article:
        return (await parsed(request, title)).article

    @app.get("/sections", tags=["wikivoyage"], summary="Plain-text sections, optionally filtered by top-level heading")
    async def sections(
        request: Request,
        title: Title,
        section: Annotated[list[str] | None, Query(description='Top-level heading, repeatable: "Get in", "Stay safe"')] = None,
    ) -> SectionsResponse:
        result = await parsed(request, title)
        wanted = {s.strip().lower() for s in section or []}
        items = [s for s in result.sections if not wanted or s.path[0].lower() in wanted]
        available = list(dict.fromkeys(s.path[0] for s in result.sections))
        return SectionsResponse(title=result.article.title, available=available, count=len(items), sections=items)

    @app.get("/listings", tags=["wikivoyage"], summary="Structured listings on one page")
    async def listings(
        request: Request,
        title: Title,
        type: Annotated[list[ListingType] | None, Query(description="see, do, buy, eat, drink, sleep, go, other")] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
    ) -> ListingsResponse:
        result = await parsed(request, title)
        items = [item for item in result.listings if not type or item.type in type]
        return ListingsResponse(
            title=result.article.title, total=len(items), returned=min(len(items), limit), listings=items[:limit]
        )

    @app.get("/nearby", tags=["wikivoyage"], summary="Articles near a point, closest first")
    async def nearby(
        request: Request,
        lat: Annotated[float, Query(ge=-90, le=90)],
        lon: Annotated[float, Query(ge=-180, le=180)],
        radius: Annotated[int, Query(ge=10, le=10_000, description="metres")] = 10_000,
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
    ) -> list[NearbyPage]:
        return await wv(request).nearby(lat, lon, radius, limit)

    return app


def _add_error_handlers(app: FastAPI) -> None:
    """Provider errors -> short JSON errors with a fitting status code."""

    def error(status: int, code: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
        return JSONResponse({"error": code, "message": message}, status_code=status, headers=headers)

    @app.exception_handler(PageNotFound)
    async def not_found(_: Request, exc: PageNotFound) -> JSONResponse:
        return error(404, "not_found", f"No Wikivoyage article named {exc.title!r}")

    @app.exception_handler(ProviderRateLimited)
    async def rate_limited(_: Request, exc: ProviderRateLimited) -> JSONResponse:
        seconds = str(int(exc.retry_after) + 1)
        return error(429, "rate_limited", str(exc), {"Retry-After": seconds})

    @app.exception_handler(ProviderUnavailable)
    async def unavailable(_: Request, exc: ProviderUnavailable) -> JSONResponse:
        return error(503, "upstream_unavailable", str(exc))

    @app.exception_handler(ProviderRequestError)
    async def rejected(_: Request, exc: ProviderRequestError) -> JSONResponse:
        return error(502, "upstream_rejected", str(exc))

    @app.exception_handler(WikivoyageApiError)
    async def api_error(_: Request, exc: WikivoyageApiError) -> JSONResponse:
        return error(502, exc.code, exc.info)

    @app.exception_handler(ValueError)
    async def bad_input(_: Request, exc: ValueError) -> JSONResponse:
        return error(400, "bad_request", str(exc))


app = create_app()
