# Phase 1 Plan: Wikivoyage Integration

Wikivoyage is the first data source. It needs no API key, it has the richest content, and it exercises the full architecture from adapter to parser, cache and MCP tools. OpenTripMap comes next and plugs into the same layers (see [destination-data-plan.md](destination-data-plan.md)).

**Goal:** a Destination Research Agent can ask "tell me about Kyoto" and get an overview, travel-advice sections and structured listings, with attribution, served from a cache when possible.

## 1. Observed API behaviour (tested Nov 2026)

These come from live requests and shape the design:

| Observation | Impact |
|---|---|
| `list=geosearch` and `prop=extracts` work as documented | Use them for nearby guides and summaries |
| A request without a timeout **hung, then returned an empty body** | Every request needs a timeout and a retry on an empty or invalid JSON body |
| Large cities (Kyoto) keep listings in **district pages** (`Kyoto/Higashiyama` has 59 listings; the city page has only 5) | Listings must be collected from the district pages too |
| Districts are defined in a **`{{Regionlist}}`** template on the city page (`region1name=[[Kyoto/Central\|Central]]`, `region1description=...`) | Read districts from this template, not from search |
| `list=prefixsearch&pssearch=Kyoto/` is **fuzzy** and also returns `Kotor`, `Katowice`… | If prefix search is used, filter titles that start with `Kyoto/` |
| Sections are nested (levels 2–5): `Get in › By plane › Through Kansai International Airport › By train` | Keep the section tree, not a flat list |
| Metadata lives in templates: `{{geo}}`, `{{IsPartOf}}`, `{{guidecity}}`, `{{pagebanner}}` | Parse them for coordinates, parent region, article quality and banner image |
| Listing format: `{{see \| name= \| alt= \| url= \| address= \| lat= \| long= \| directions= \| hours= \| price= \| wikidata= \| content= }}` | Fixed field set, maps directly to a model |

## 2. Scope

**In scope**
- Resolve a destination name to a Wikivoyage article, handling redirects and ambiguous names
- Article metadata: coordinates, parent region, quality status, banner, districts
- Plain-text travel-advice sections
- Structured listings from the city page and its district pages
- Redis caching, rate limiting, retries
- An MCP server exposing this to agents
- Tests against recorded responses

**Out of scope for this phase:** OpenTripMap, merging sources, agents, UI, languages other than English.

## 3. Project setup

```
wayfinder/
  pyproject.toml
  .env.example                    # WIKIVOYAGE_CONTACT, REDIS_URL
  src/wayfinder/
    config.py
    providers/
      http.py                     # shared async client, retry, rate limit
      wikivoyage/
        client.py                 # raw API calls → JSON / wikitext
        parser.py                 # wikitext → models
        templates.py              # listing / geo / regionlist / status helpers
        adapter.py                # public interface used by services
    domain/
      models.py
    cache/
      redis_cache.py
    mcp_servers/
      wikivoyage_server.py
  scripts/
    capture_fixtures.py           # saves real responses for tests
  tests/
    fixtures/wikivoyage/
    test_templates.py
    test_parser.py
    test_adapter.py
```

Stack: Python 3.12, `uv`, `httpx`, `pydantic`, `mwparserfromhell`, `redis`, `mcp` (FastMCP), `pytest`, `pytest-asyncio`, `respx`.

## 4. Data model

```python
class Attribution(BaseModel):
    provider: Literal["wikivoyage"] = "wikivoyage"
    title: str
    url: str                       # https://en.wikivoyage.org/wiki/Kyoto
    revision_id: int               # exact revision used, for attribution
    license: str = "CC BY-SA 4.0"

class District(BaseModel):
    name: str                      # "Central"
    title: str                     # "Kyoto/Central"
    description: str

class Article(BaseModel):
    title: str
    lat: float | None              # {{geo}}
    lon: float | None
    parent: str | None             # {{IsPartOf}}
    kind: str | None               # city / region / country / park ...
    status: str | None             # outline / usable / guide / star
    banner: str | None             # {{pagebanner}}
    summary: str                   # intro, plain text
    districts: list[District]
    source: Attribution

class Section(BaseModel):
    title: str                     # "By plane"
    path: list[str]                # ["Get in", "By plane"]
    level: int
    text: str                      # plain text, listings removed
    source: Attribution

class Listing(BaseModel):
    type: Literal["see", "do", "buy", "eat", "drink", "sleep", "go", "other"]
    name: str
    alt: str | None
    lat: float | None
    lon: float | None
    address: str | None
    directions: str | None
    phone: str | None
    hours: str | None
    price: str | None
    url: str | None
    wikidata: str | None           # used later to join with OpenTripMap
    description: str | None        # from `content`
    district: str | None           # "Higashiyama" if from a district page
    section_path: list[str]        # where it appeared, e.g. ["Eat", "Budget"]
    source: Attribution
```

## 5. Build steps

### Step 1: HTTP client (`providers/http.py`)
- `httpx.AsyncClient`, **30 s timeout**, HTTP/2 off, gzip on.
- Header: `User-Agent: WayFinder/0.1 (<repo-url>; <contact-email>)`, read from config. Refuse to start without it.
- **Retry** (max 3, exponential backoff + jitter) on: timeout, 429, 5xx, empty body, invalid JSON, and an API `error.code == "maxlag"`. Honour `Retry-After`.
- **Serial access:** `asyncio.Semaphore(1)` per provider, plus a minimum gap between requests (start with 200 ms).
- Always send `format=json&formatversion=2&maxlag=5`.
- Log each call: endpoint, title, status, duration, retries.

**Done when:** a unit test shows an empty body and a 429 are retried, then succeed.

### Step 2: Capture fixtures (`scripts/capture_fixtures.py`)
Save raw responses for a set of test articles, chosen to cover the edge cases:

| Case | Example to try |
|---|---|
| Large city with districts | `Kyoto` + its 5 district pages |
| Small city without districts | a small town article |
| Redirect | a former city name that redirects |
| Ambiguous name | `Springfield` or `Paris` |
| Region / country (not a city) | `Kansai`, `Japan` |
| Non-Latin names in listings | any Japanese / Thai city listing |

Save `parse` (wikitext + sections + revid), `extracts` and `geosearch` responses as JSON in `tests/fixtures/wikivoyage/`. All later tests run offline against these files.

**Done when:** fixtures are committed and the script can be re-run to refresh them.

### Step 3: Raw client (`wikivoyage/client.py`)
Thin methods that only fetch:

| Method | API call |
|---|---|
| `search(query)` | `list=search&srsearch=` |
| `resolve(title)` | `action=query&titles=&redirects=1&prop=info\|pageprops` → canonical title, page id, disambiguation flag |
| `get_page(title)` | `action=parse&page=&prop=wikitext\|sections\|revid` → **one request per article** |
| `get_summary(title)` | `prop=extracts&exintro=1&explaintext=1&redirects=1` |
| `nearby(lat, lon, radius≤10000)` | `list=geosearch&gscoord=lat\|lon&gsradius=` |

Fetch the full wikitext once and split sections locally. That's 1 request per article instead of 1 per section.

How disambiguation pages are marked (page property or template) should be confirmed against the fixtures before relying on it.

### Step 4: Template helpers (`wikivoyage/templates.py`)
Using `mwparserfromhell`, match template names case-insensitively:
- `parse_geo` — `{{geo|35.01|135.76}}` → `(lat, lon)`
- `parse_is_part_of` — `{{IsPartOf|Kansai}}` → `"Kansai"`
- `parse_status` — `{{guidecity}}`, `{{usablecity}}`, `{{starregion}}`… → `(kind, status)`
- `parse_banner` — `{{pagebanner|File.jpg}}`
- `parse_regionlist` — `regionNname` / `regionNdescription` → `list[District]`. Extract the link target (`Kyoto/Central`) and the label (`Central`).
- `parse_listing` — `see`/`do`/`buy`/`eat`/`drink`/`sleep`/`go` + generic `listing` with `type=`. Convert `lat`/`long` to float. Treat empty strings as `None`. Strip wiki markup from `content`.

**Done when:** each helper has tests from the fixtures, including malformed input (missing `name`, non-numeric `lat`).

### Step 5: Article parser (`wikivoyage/parser.py`)
`parse_article(wikitext, sections, revid) → (Article, list[Section], list[Listing])`
1. Read metadata templates (Step 4).
2. Split wikitext by headings into a **section tree**, keeping `path` and `level`.
3. In each section: pull out listings (tagged with `section_path`), then convert the remaining text to plain text (`strip_code`, collapse whitespace).
4. Drop sections with no content and boilerplate (`See also`, empty `Go next`).

**Done when:** Kyoto parses into the expected section paths, and Kyoto/Higashiyama yields 59 listings (31 see, 9 eat, 10 sleep, 6 do, 2 buy, 1 drink).

### Step 6: Adapter (`wikivoyage/adapter.py`)
The public interface the rest of the system uses:

| Method | Behaviour |
|---|---|
| `find_destination(query)` | search → resolve → if ambiguous, return candidates; else `Article` |
| `get_article(title)` | cached `get_page` + `parse_article` |
| `get_sections(title, names=None)` | sections filtered by top-level name (`Get in`, `Stay safe`…) |
| `get_listings(title, types=None, include_districts=True)` | city listings + **each district's listings** (fetched serially, cached), tagged with `district` |
| `nearby(lat, lon)` | geosearch, returns titles + distance |

### Step 7: Cache (`cache/redis_cache.py`)
| Key | Value | TTL |
|---|---|---|
| `wv:page:{title}` | raw parse response (wikitext + revid) | 7 days |
| `wv:parsed:{title}:{revid}` | parsed Article + Sections + Listings | 30 days (the revision never changes) |
| `wv:resolve:{query}` | canonical title / candidates | 7 days |
| `wv:geo:{lat:.3f}:{lon:.3f}:{r}` | geosearch result | 7 days |

Cache the raw response **and** the parsed result. When the parser changes, bump a `PARSER_VERSION` in the key and re-parse without refetching.

**Done when:** a second `get_listings("Kyoto")` makes 0 HTTP calls.

### Step 8: MCP server (`mcp_servers/wikivoyage_server.py`)
| Tool | Returns |
|---|---|
| `search_destinations(query)` | up to 5 candidates: title, parent, kind |
| `get_destination_overview(title)` | `Article` (summary, coordinates, districts, status) |
| `get_travel_guide(title, sections)` | `Section`s, e.g. `["Get in", "Get around", "Stay safe"]` |
| `get_listings(title, types, district?, limit=20)` | `Listing`s, ranked: has coordinates, has description, then page order |
| `get_nearby_guides(lat, lon)` | nearby article titles + distance |

Rules:
- Keep outputs compact: limit about 20, truncate text over about 1,500 characters, and say when results were cut.
- Every response includes `source` (URL, revision, licence).
- Errors are short and structured: `{"error": "rate_limited", "retry_after": 30}`.

**Done when:** all tools work in MCP Inspector against live data for Kyoto.

## 6. Test plan

| Layer | Tests |
|---|---|
| HTTP client | retries on empty body / 429 / timeout; User-Agent present; requests serialised |
| Templates | each helper against fixtures + malformed input |
| Parser | section paths for Kyoto; listing counts for Kyoto/Higashiyama; plain text has no `{{` / `[[` left |
| Adapter | redirect resolved; ambiguous name returns candidates; districts included; cache hit makes no HTTP call (`respx`) |
| MCP | tool schemas valid; output size within limits; `source` present |

One optional live smoke test (`pytest -m live`) hits the real API for Kyoto. It's excluded from the default run.

## 7. Milestones

| # | Milestone | Steps |
|---|---|---|
| M1 | Fetch reliably | 1, 2, 3 |
| M2 | Parse Kyoto correctly | 4, 5 |
| M3 | Usable adapter with cache | 6, 7 |
| M4 | Agents can call it | 8 |

## 8. After this phase
- ~~Add the **OpenTripMap adapter**~~ Dropped (Nov 2026): no account. A second source, if needed, would be Overpass + Wikidata, using the same structure (`client` → `adapter`).
- Use the `wikidata` IDs in listings to join with that second source.
- Move ranking and merging into `DestinationService` as in [destination-data-plan.md](destination-data-plan.md).

## 9. Before starting
- [ ] Choose the contact email/URL for the User-Agent.
- [ ] Decide on Redis locally (Docker `redis:7`) or an in-memory cache for the first steps.
- [ ] Confirm the licence approach: show Wikivoyage text with attribution, and keep it separate from AI-generated text.
