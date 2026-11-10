"""Wikivoyage article -> Article, Sections and Listings.

    parsed = parse_article(await client.get_page("Kyoto/Higashiyama"))
    parsed.article      # metadata, summary, districts
    parsed.sections     # plain-text sections with their heading path
    parsed.listings     # structured see/do/eat/... entries

Pure function over a fetched page: no network, easy to test against fixtures.
"""

from __future__ import annotations

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

PARSER_VERSION = 1  # bump when output changes, so cached parses are invalidated (M3)

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


def parse_article(page: PageContent, *, lang: str = "en") -> ParsedArticle:
    source = Attribution(title=page.title, url=article_url(page.title, lang), revision_id=page.revid)
    code = parse(page.wikitext)
    district = page.title.rsplit("/", 1)[1] if "/" in page.title else None

    summary = ""
    sections: list[Section] = []
    listings: list[Listing] = []
    open_headings: list[tuple[int, str]] = []  # (level, title) of the headings we are inside

    for chunk in code.get_sections(flat=True, include_lead=True):
        headings = chunk.filter_headings(recursive=False)
        is_lead = not headings or chunk.index(headings[0]) != 0
        if is_lead:
            path: list[str] = []
            body = chunk
        else:
            heading = headings[0]
            title = to_text(heading.title)
            while open_headings and open_headings[-1][0] >= heading.level:
                open_headings.pop()
            open_headings.append((heading.level, title))
            path = [t for _, t in open_headings]
            body = parse(str(chunk)[len(str(heading)):])

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
            sections.append(Section(title=path[-1], path=path, level=heading.level, text=text, source=source))

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
