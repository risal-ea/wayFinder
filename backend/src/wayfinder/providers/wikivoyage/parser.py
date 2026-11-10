"""Wikivoyage article -> Article, Sections and Listings.

    parsed = parse_article(await client.get_page("Kyoto/Higashiyama"))
    parsed.article      # metadata, summary, districts
    parsed.sections     # plain-text sections with their heading path
    parsed.listings     # structured see/do/eat/... entries

Pure function over a fetched page: no network, easy to test against fixtures.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from pydantic import BaseModel

from wayfinder.domain.models import Article, Attribution, Listing, ListingType, Section
from wayfinder.providers.wikivoyage.client import article_url
from wayfinder.providers.wikivoyage.models import PageContent
from wayfinder.providers.wikivoyage.templates import (
    find_listings,
    parse_banner,
    parse_geo,
    parse_is_part_of,
    parse_listing,
    parse_regionlist,
    parse_status,
)
from wayfinder.providers.wikivoyage.text import parse, to_text

PARSER_VERSION = 2  # bump when output changes, so cached parses are invalidated (M3)

# Boilerplate sections that hold only links to other articles.
SKIPPED_SECTIONS = frozenset({"see also", "references", "external links"})

# Type for generic {{listing}} templates, from the top-level section they sit in.
SECTION_LISTING_TYPES: dict[str, ListingType] = {
    "see": "see",
    "do": "do",
    "buy": "buy",
    "eat": "eat",
    "drink": "drink",
    "sleep": "sleep",
    "get in": "go",
    "get around": "go",
}


class ParsedArticle(BaseModel):
    article: Article
    sections: list[Section]
    listings: list[Listing]


class _Chunk(NamedTuple):
    level: int        # 0 for the lead
    title: str        # "" for the lead
    body: str         # wikitext after the heading line


_HEADING_LINE = re.compile(r"^(={2,6})[ \t]*(.+?)[ \t]*\1[ \t]*$", re.MULTILINE)


def split_sections(page: PageContent) -> list[_Chunk]:
    """Cut the wikitext at its headings: lead first, then one chunk per heading.

    Uses the heading positions MediaWiki reported (tocdata), so malformed markup
    in one section (e.g. Japan's `'''''futon'' bedding'''`) cannot hide the
    headings after it. Falls back to matching heading lines if tocdata is absent.
    """
    text = page.wikitext
    marks = [(s.char_offset, s.level, s.title) for s in page.sections if s.char_offset is not None]
    if not marks:
        marks = [(m.start(), len(m.group(1)), to_text(m.group(2))) for m in _HEADING_LINE.finditer(text)]
    marks.sort()

    chunks = [_Chunk(0, "", text[: marks[0][0]] if marks else text)]
    for i, (start, level, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        heading_end = text.find("\n", start, end)
        chunks.append(_Chunk(level, title, text[heading_end + 1 : end] if heading_end >= 0 else ""))
    return chunks


def parse_article(page: PageContent, *, lang: str = "en") -> ParsedArticle:
    source = Attribution(title=page.title, url=article_url(page.title, lang), revision_id=page.revid)
    code = parse(page.wikitext)
    district = page.title.rsplit("/", 1)[1] if "/" in page.title else None

    summary = ""
    sections: list[Section] = []
    listings: list[Listing] = []
    open_headings: list[tuple[int, str]] = []  # (level, title) of the headings we are inside

    for chunk in split_sections(page):
        is_lead = chunk.level == 0
        if is_lead:
            path: list[str] = []
        else:
            while open_headings and open_headings[-1][0] >= chunk.level:
                open_headings.pop()
            open_headings.append((chunk.level, chunk.title))
            path = [t for _, t in open_headings]
        body = parse(chunk.body)

        default_type = SECTION_LISTING_TYPES.get(path[0].lower(), "other") if path else "other"
        for template in find_listings(body):
            listing = parse_listing(
                template, section_path=path, source=source, district=district, default_type=default_type
            )
            if listing:
                listings.append(listing)

        text = to_text(body)
        if is_lead:
            summary = text
        elif text and path[0].lower() not in SKIPPED_SECTIONS:
            sections.append(Section(title=chunk.title, path=path, level=chunk.level, text=text, source=source))

    lat_lon = parse_geo(code)
    kind, status = parse_status(code)
    article = Article(
        title=page.title,
        lat=lat_lon[0] if lat_lon else None,
        lon=lat_lon[1] if lat_lon else None,
        parent=parse_is_part_of(code),
        kind=kind,
        status=status,
        banner=parse_banner(code),
        summary=summary,
        districts=parse_regionlist(code),
        source=source,
    )
    return ParsedArticle(article=article, sections=sections, listings=listings)
