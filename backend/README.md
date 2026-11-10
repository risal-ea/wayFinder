# WayFinder backend

Phase 1 of [docs/wikivoyage-plan.md](../docs/wikivoyage-plan.md): milestones M1 (fetch reliably) and M2 (parse articles). Caching and the MCP server come next.

## Setup

```bash
cd backend
uv sync
cp .env.example .env   # set WIKIVOYAGE_CONTACT to your email (see docs/api-setup.md)
```

## Use

```python
from wayfinder.providers.wikivoyage import WikivoyageClient

async with WikivoyageClient.from_settings() as wv:
    await wv.search("Kyoto")                 # list[SearchResult]
    await wv.resolve("Peking")               # ResolvedPage: title="Beijing", redirected_from="Peking"
    await wv.get_page("Kyoto")               # PageContent: wikitext, sections, revid (one request)
    await wv.get_summary("Kyoto")            # Summary: plain-text intro
    await wv.nearby(35.0116, 135.7681)       # list[NearbyPage], closest first
```

Errors are typed: `PageNotFound`, `WikivoyageApiError`, `ProviderRateLimited` (with `retry_after`), `ProviderUnavailable`, `ProviderRequestError`.

Turn a fetched page into structured data (no network involved):

```python
from wayfinder.providers.wikivoyage.parser import parse_article

parsed = parse_article(await wv.get_page("Kyoto/Higashiyama"))
parsed.article    # Article: coordinates, parent, kind/status, summary, districts
parsed.sections   # list[Section]: plain text with heading path, e.g. ["Get in", "By train"]
parsed.listings   # list[Listing]: 59 see/do/eat/... entries with coordinates, hours, price
```

## HTTP API (for Postman / browser)

```bash
uv run uvicorn wayfinder.api.app:app --reload      # http://localhost:8000, docs at /docs
```

| Endpoint | Example |
|---|---|
| `GET /search` | `/search?q=Kyoto` |
| `GET /resolve` | `/resolve?title=Peking` |
| `GET /summary` | `/summary?title=Kyoto` |
| `GET /article` | `/article?title=Kyoto` |
| `GET /sections` | `/sections?title=Kyoto&section=Get in&section=Get around` |
| `GET /listings` | `/listings?title=Kyoto/Higashiyama&type=eat&type=drink&limit=20` |
| `GET /nearby` | `/nearby?lat=35.0116&lon=135.7681` |

Errors: 404 `not_found`, 422 invalid input, 429 `rate_limited` (with `Retry-After`), 502/503 when Wikivoyage fails. Import `postman/WayFinder.postman_collection.json` for ready-made requests.

## Layout

| Path | What |
|---|---|
| `src/wayfinder/config.py` | Settings from `.env`; builds the Wikimedia User-Agent |
| `src/wayfinder/providers/http.py` | Shared client: timeout, retries, `Retry-After`, serial access, request spacing, log redaction |
| `src/wayfinder/providers/wikivoyage/client.py` | Params builders, API calls, response parsers |
| `src/wayfinder/providers/wikivoyage/text.py` | Wikitext → plain text (links, formatting, inline templates) |
| `src/wayfinder/providers/wikivoyage/templates.py` | `{{geo}}`, `{{IsPartOf}}`, status, banner, `{{Regionlist}}`, listing templates |
| `src/wayfinder/providers/wikivoyage/parser.py` | `parse_article()`: page → Article + Sections + Listings |
| `src/wayfinder/domain/models.py` | Article, Section, Listing, District, Attribution |
| `src/wayfinder/api/app.py` | FastAPI app exposing the client and parser over HTTP |
| `scripts/capture_fixtures.py` | Saves real API responses to `tests/fixtures/wikivoyage/` |
| `postman/WayFinder.postman_collection.json` | The same Wikivoyage calls, for Postman |

## Tests

```bash
uv run pytest              # offline, uses recorded fixtures
uv run pytest -m live      # one smoke test against the real API
uv run python scripts/capture_fixtures.py   # refresh fixtures
```
