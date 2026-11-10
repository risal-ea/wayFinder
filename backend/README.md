# WayFinder backend

Phase 1, milestone M1 of [docs/wikivoyage-plan.md](../docs/wikivoyage-plan.md): fetching from Wikivoyage reliably. Parsing, caching and the MCP server come next.

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

## Layout

| Path | What |
|---|---|
| `src/wayfinder/config.py` | Settings from `.env`; builds the Wikimedia User-Agent |
| `src/wayfinder/providers/http.py` | Shared client: timeout, retries, `Retry-After`, serial access, request spacing, log redaction |
| `src/wayfinder/providers/wikivoyage/client.py` | Params builders, API calls, response parsers |
| `scripts/capture_fixtures.py` | Saves real API responses to `tests/fixtures/wikivoyage/` |
| `postman/WayFinder.postman_collection.json` | The same Wikivoyage calls, for Postman |

## Tests

```bash
uv run pytest              # offline, uses recorded fixtures
uv run pytest -m live      # one smoke test against the real API
uv run python scripts/capture_fixtures.py   # refresh fixtures
```
