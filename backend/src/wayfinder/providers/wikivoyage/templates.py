"""Read structured data out of Wikivoyage templates.

Page metadata ({{geo}}, {{IsPartOf}}, status, {{pagebanner}}), the {{Regionlist}}
of districts, and listing templates ({{see}}, {{eat}}, ..., generic {{listing}}).
Template names are matched case-insensitively. Malformed values become None
instead of raising: wikitext is hand-written and varies between articles.
"""

from __future__ import annotations

import logging
import re

from mwparserfromhell.nodes import Tag, Template, Wikilink
from mwparserfromhell.wikicode import Wikicode

from wayfinder.domain.models import Attribution, District, Listing, ListingType
from wayfinder.providers.wikivoyage.text import named, parse, positional, template_name, to_text

logger = logging.getLogger("wayfinder.wikivoyage.templates")

LISTING_TEMPLATES = frozenset({"see", "do", "buy", "eat", "drink", "sleep", "go", "listing"})
LISTING_TYPES = frozenset({"see", "do", "buy", "eat", "drink", "sleep", "go"})
STATUS_LEVELS = ("outline", "usable", "guide", "star")
_STATUS = re.compile(rf"^({'|'.join(STATUS_LEVELS)})([a-z]+)$")
_WIKIDATA_ID = re.compile(r"^Q\d+$")


def page_templates(code: Wikicode | str, *names: str) -> list[Template]:
    """Top-level templates with one of `names` (not those nested inside other templates)."""
    wanted = set(names)
    return [t for t in parse(code).filter_templates(recursive=False) if template_name(t) in wanted]


# Page metadata

def parse_geo(code: Wikicode | str) -> tuple[float, float] | None:
    """{{geo|35.01|135.76|zoom=12}} -> (35.01, 135.76)."""
    for template in page_templates(code, "geo"):
        args = positional(template)
        if len(args) >= 2:
            lat, lon = _coordinate(str(args[0]), 90), _coordinate(str(args[1]), 180)
            if lat is not None and lon is not None:
                return lat, lon
    return None


def parse_is_part_of(code: Wikicode | str) -> str | None:
    """{{IsPartOf|Kansai}} -> "Kansai"."""
    for template in page_templates(code, "ispartof"):
        args = positional(template)
        if args and (parent := to_text(args[0]).replace("_", " ")):
            return parent
    return None


def parse_status(code: Wikicode | str) -> tuple[str | None, str | None]:
    """{{guidecity}} -> ("city", "guide"); {{usabledistrict}} -> ("district", "usable")."""
    for template in parse(code).filter_templates(recursive=False):
        match = _STATUS.match(template_name(template).replace(" ", ""))
        if match:
            return match.group(2), match.group(1)
    return None, None


def parse_banner(code: Wikicode | str) -> str | None:
    """{{pagebanner|Kyoto banner.jpg|caption=...}} -> "Kyoto banner.jpg"."""
    for template in page_templates(code, "pagebanner"):
        args = positional(template)
        if args and (banner := str(args[0]).strip()):
            return banner
    return None


def parse_regionlist(code: Wikicode | str) -> list[District]:
    """All entries of every {{Regionlist}} on the page, in order.

    `region2name=[[Kyoto/Arashiyama|Arashiyama]] (Western Kyoto)` gives
    name "Arashiyama", title "Kyoto/Arashiyama". Entries without a link
    (no article yet) keep their text as the name and have title None.
    """
    districts: list[District] = []
    for template in page_templates(code, "regionlist"):
        index = 1
        while template.has(f"region{index}name"):
            name_code = template.get(f"region{index}name").value
            description = named(template, f"region{index}description")
            district = _district(name_code, to_text(description))
            if district:
                districts.append(district)
            index += 1
    return districts


def _district(name_code: Wikicode, description: str) -> District | None:
    links = [link for link in name_code.filter_wikilinks() if not str(link.title).lower().startswith(("file:", "image:"))]
    if links:
        link: Wikilink = links[0]
        title = str(link.title).strip().split("#", 1)[0].replace("_", " ")
        name = to_text(link.text) if link.text is not None else title
        return District(name=name, title=title, description=description)
    text = to_text(name_code)
    return District(name=text, title=None, description=description) if text else None


# Listings

def is_listing(template: Template) -> bool:
    return template_name(template) in LISTING_TEMPLATES


def find_listings(code: Wikicode) -> list[Template]:
    """Listing templates in page order, including those inside tables and HTML tags
    (e.g. Beijing's embassy table) but not inside other templates' parameters."""
    found: list[Template] = []
    for node in code.nodes:
        if isinstance(node, Template):
            if is_listing(node):
                found.append(node)
        elif isinstance(node, Tag) and node.contents is not None:
            found.extend(find_listings(node.contents))
    return found


def parse_listing(
    template: Template,
    *,
    section_path: list[str],
    source: Attribution,
    district: str | None = None,
    default_type: ListingType = "other",
) -> Listing | None:
    """One listing template -> Listing, or None if it has no usable name.

    Generic {{listing}} templates usually have no `type=`; they take the type of
    the section they appear in (`default_type`).
    """
    kind = template_name(template)
    if kind == "listing":
        declared = _text(template, "type").lower()
        listing_type: ListingType = declared if declared in LISTING_TYPES else default_type  # type: ignore[assignment]
    else:
        listing_type = kind  # type: ignore[assignment]

    name = _text(template, "name").rstrip(" ,;:")
    if not name:
        logger.debug("skipping %s listing without a name in %s %s", kind, source.title, section_path)
        return None

    lat = _coordinate(_raw(template, "lat"), 90)
    lon = _coordinate(_raw(template, "long", "lon"), 180)
    if lat is None or lon is None:
        lat = lon = None

    wikidata = _raw(template, "wikidata").upper()
    url = _raw(template, "url")

    return Listing(
        type=listing_type,
        name=name,
        alt=_text(template, "alt") or None,
        lat=lat,
        lon=lon,
        address=_text(template, "address") or None,
        directions=_text(template, "directions") or None,
        phone=_text(template, "phone") or None,
        email=_raw(template, "email") or None,
        hours=_text(template, "hours") or None,
        check_in=_text(template, "checkin") or None,
        check_out=_text(template, "checkout") or None,
        price=_text(template, "price") or None,
        url=url if url.startswith(("http://", "https://")) else None,
        image=_raw(template, "image") or None,
        wikidata=wikidata if _WIKIDATA_ID.match(wikidata) else None,
        description=_text(template, "content", "description") or None,
        last_edit=_raw(template, "lastedit") or None,
        district=district,
        section_path=section_path,
        source=source,
    )


def _text(template: Template, *keys: str) -> str:
    return to_text(named(template, *keys))


def _raw(template: Template, *keys: str) -> str:
    value = named(template, *keys)
    return str(value).strip() if value is not None else ""


def _coordinate(value: str, limit: float) -> float | None:
    try:
        number = float(value.strip())
    except ValueError:
        return None
    return number if -limit <= number <= limit else None
