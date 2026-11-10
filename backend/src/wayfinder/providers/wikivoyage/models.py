"""Typed results of the raw Wikivoyage API calls.

These mirror what the API returns. They are not the domain models: turning
wikitext into articles, sections and listings is the parser's job (Step 5).
"""

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    pageid: int
    snippet: str  # plain text, search-match markup removed


class ResolvedPage(BaseModel):
    query: str                      # what was asked for
    title: str                      # canonical title after normalisation and redirects
    exists: bool
    pageid: int | None = None
    redirected_from: str | None = None
    is_disambiguation: bool = False
    wikidata: str | None = None     # e.g. "Q34600"
    last_revid: int | None = None


class SectionInfo(BaseModel):
    index: int                      # use with action=parse&section=N
    level: int                      # 2 = "==", 3 = "===", ...
    title: str                      # "By plane"
    number: str                     # "3.1"
    anchor: str
    char_offset: int | None         # where the heading starts in `wikitext` (Python str index);
                                    # None for sections that come from a transcluded template


class PageContent(BaseModel):
    title: str
    pageid: int
    revid: int                      # exact revision, needed for attribution and caching
    wikitext: str
    sections: list[SectionInfo]
    redirected_from: str | None = None


class Summary(BaseModel):
    title: str
    pageid: int
    extract: str                    # plain-text intro


class NearbyPage(BaseModel):
    title: str
    pageid: int
    lat: float
    lon: float
    distance_m: float
