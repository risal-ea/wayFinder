"""Domain models: what the rest of WayFinder (services, MCP tools, agents) works with.

Every record carries an `Attribution`, because Wikivoyage text is CC BY-SA and
must be credited with a link to the exact revision used.
"""

from typing import Literal

from pydantic import BaseModel

ListingType = Literal["see", "do", "buy", "eat", "drink", "sleep", "go", "other"]


class Attribution(BaseModel):
    provider: Literal["wikivoyage"] = "wikivoyage"
    title: str
    url: str                        # https://en.wikivoyage.org/wiki/Kyoto
    revision_id: int                # exact revision used
    license: str = "CC BY-SA 4.0"


class District(BaseModel):
    """An entry of the page's {{Regionlist}}: districts of a city, regions of a country."""

    name: str                       # "Arashiyama"
    title: str | None               # "Kyoto/Arashiyama"; None if the entry has no article
    description: str


class Article(BaseModel):
    title: str
    lat: float | None               # {{geo}}
    lon: float | None
    parent: str | None              # {{IsPartOf}}, e.g. "Kansai"
    kind: str | None                # city / district / region / country / ...
    status: str | None              # outline / usable / guide / star
    banner: str | None              # {{pagebanner}} file name
    summary: str                    # lead text before the first heading, plain text
    districts: list[District]
    source: Attribution


class Section(BaseModel):
    title: str                      # "By train"
    path: list[str]                 # ["Get in", "By train"]
    level: int                      # 2 for "==", 3 for "===", ...
    text: str                       # plain text, listings removed
    source: Attribution


class Listing(BaseModel):
    type: ListingType
    name: str
    alt: str | None = None          # alternative / local-script name
    lat: float | None = None
    lon: float | None = None
    address: str | None = None
    directions: str | None = None
    phone: str | None = None
    email: str | None = None
    hours: str | None = None
    check_in: str | None = None     # sleep listings
    check_out: str | None = None
    price: str | None = None
    url: str | None = None
    image: str | None = None        # Commons file name
    wikidata: str | None = None     # e.g. "Q221716", join key for other sources
    description: str | None = None  # from `content`
    last_edit: str | None = None    # when editors last checked the listing, e.g. "2020-08-19"
    district: str | None = None     # "Higashiyama" if it came from a district page
    section_path: list[str]         # where it appeared, e.g. ["Eat", "Budget"]
    source: Attribution
