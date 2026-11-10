"""Template helpers and wikitext -> text, on small hand-written snippets,
including the malformed input real articles sometimes contain."""

import pytest

from wayfinder.domain.models import Attribution
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

SOURCE = Attribution(title="Test", url="https://en.wikivoyage.org/wiki/Test", revision_id=1)


def listing(wikitext: str, **kwargs):
    templates = find_listings(parse(wikitext))
    assert len(templates) == 1
    return parse_listing(templates[0], section_path=["See"], source=SOURCE, **kwargs)


# to_text

@pytest.mark.parametrize(
    ("wikitext", "expected"),
    [
        ("Visit [[Kyoto]] and [[Kyoto/Central|the centre]].", "Visit Kyoto and the centre."),
        ("'''Bold''' and ''italic''", "Bold and italic"),
        ("See [https://example.com the site] or https://bare.example", "See the site or https://bare.example"),
        ("Fly to Narita {{IATA|NRT}}", "Fly to Narita (IATA: NRT)"),
        ("Gift chocolate ({{Lang|ja|義理チョコ}})", "Gift chocolate (義理チョコ)"),
        ("It is {{km|256}} away", "It is 256 km away"),
        ("Area {{convert|1.445|to|1.824|m2|m2|abbr=on}}", "Area 1.445 to 1.824 m2"),
        ("Go to {{marker|type=city|name=[[Tokyo]]|lat=35.6|long=139.6}}.", "Go to Tokyo."),
        ("Line 2 {{rint|beijing|2}} stops here", "Line 2 stops here"),
        ("Closed{{Dead link|date=March 2025}}.", "Closed."),
        ("Open 06:00&ndash;18:00", "Open 06:00–18:00"),
        ("Text<ref>a citation</ref> continues", "Text continues"),
        ("[[File:Kyoto.jpg|thumb|A caption]]Kyoto is old.", "Kyoto is old."),
        ("* first\n* second\n*\n# third", "- first\n- second\n\n- third"),
        ("* parent\n** child", "- parent\n  - child"),
        ("Station (){{rint|x|y}} here", "Station here"),
        ("Hidden <!-- editor note --> text", "Hidden text"),
        ("[[ja:京都市]]", ""),
    ],
)
def test_to_text(wikitext, expected):
    assert to_text(wikitext) == expected


def test_to_text_handles_none_and_empty():
    assert to_text(None) == "" and to_text("") == ""


# Page metadata

def test_geo():
    assert parse_geo("{{geo|35.011667|135.768333|zoom=12}}") == (35.011667, 135.768333)
    assert parse_geo("{{Geo|34.5|135.0}}") == (34.5, 135.0)
    assert parse_geo("{{geo|north|east}}") is None
    assert parse_geo("{{geo|95|135}}") is None  # out of range
    assert parse_geo("no geo here") is None


def test_is_part_of():
    assert parse_is_part_of("{{IsPartOf|Kansai}}") == "Kansai"
    assert parse_is_part_of("{{IsPartOf|Kyoto_(prefecture)}}") == "Kyoto (prefecture)"
    assert parse_is_part_of("{{IsPartOf}}") is None


@pytest.mark.parametrize(
    ("wikitext", "expected"),
    [
        ("{{guidecity}}", ("city", "guide")),
        ("{{usabledistrict}}", ("district", "usable")),
        ("{{starcountry}}", ("country", "star")),
        ("{{outlineregion}}", ("region", "outline")),
        ("{{seedistricts}}", (None, None)),
        ("", (None, None)),
    ],
)
def test_status(wikitext, expected):
    assert parse_status(wikitext) == expected


def test_banner():
    assert parse_banner("{{pagebanner|Gion banner.jpg|caption=Gion Festival}}") == "Gion banner.jpg"
    assert parse_banner("{{pagebanner}}") is None


def test_regionlist():
    districts = parse_regionlist("""{{Regionlist
| regionmap=Kyoto map.png
| region1name=[[Kyoto/Central|Central]]
| region1description=Site of [[Nijō Castle]].
| region2name=[[Kyoto/Arashiyama|Arashiyama]] (Western Kyoto)
| region2description=Hills and bamboo.
| region3name=Dongcheng District (东城区)
| region4name=[[Hokkaido]]
}}""")
    assert [(d.name, d.title) for d in districts] == [
        ("Central", "Kyoto/Central"),
        ("Arashiyama", "Kyoto/Arashiyama"),
        ("Dongcheng District (东城区)", None),
        ("Hokkaido", "Hokkaido"),
    ]
    assert districts[0].description == "Site of Nijō Castle."
    assert districts[2].description == ""


# Listings

def test_full_listing():
    item = listing("""* {{see
| name=Kiyomizu Temple | alt=清水寺 | url=http://www.kiyomizudera.or.jp/ | email=
| address=1-chome, Kiyomizu | lat=34.994831 | long=135.785003 | directions=bus 100
| phone=+81 75-551-123 | hours=Daily: 06:00&ndash;18:00 | price=¥400
| image=Kiyomizudera.jpg | wikidata=Q221716 | lastedit=2020-08-19
| content=A '''famous''' temple near [[Gion]].
}}""", district="Higashiyama")
    assert item.type == "see" and item.name == "Kiyomizu Temple" and item.alt == "清水寺"
    assert (item.lat, item.lon) == (34.994831, 135.785003)
    assert item.hours == "Daily: 06:00–18:00"
    assert item.description == "A famous temple near Gion."
    assert item.email is None  # empty field -> None
    assert (item.wikidata, item.last_edit, item.district) == ("Q221716", "2020-08-19", "Higashiyama")
    assert item.section_path == ["See"] and item.source == SOURCE


def test_listing_without_name_is_skipped():
    assert listing("{{eat | name= | lat=35.0 | long=135.0 | content=Nameless}}") is None
    assert listing("{{eat | content=No name field at all}}") is None


def test_bad_coordinates_become_none():
    item = listing("{{see | name=Somewhere | lat=north | long=135.7}}")
    assert (item.lat, item.lon) == (None, None)
    item = listing("{{see | name=Somewhere | lat=35.0 | long=}}")
    assert (item.lat, item.lon) == (None, None)  # never half a coordinate pair
    item = listing("{{see | name=Somewhere | lat=135.0 | long=35.0}}")
    assert item.lat is None  # latitude out of range


def test_invalid_url_and_wikidata_are_dropped():
    item = listing("{{do | name=X | url=www.no-scheme.example | wikidata=not-an-id}}")
    assert item.url is None and item.wikidata is None


def test_generic_listing_type():
    assert listing("{{listing | name=Uni | type=see}}").type == "see"
    assert listing("{{listing | name=Uni}}", default_type="eat").type == "eat"
    assert listing("{{listing | name=Uni | type=nonsense}}").type == "other"


def test_listing_name_with_link_and_template():
    item = listing("{{go | name=[[Beijing Capital International Airport]] | alt=首都机场 {{IATA|PEK}}}}")
    assert item.name == "Beijing Capital International Airport"
    assert item.alt == "首都机场 (IATA: PEK)"


def test_name_trailing_punctuation_is_trimmed():
    assert listing("{{see | name=Imperial Office, }}").name == "Imperial Office"


def test_find_listings_looks_inside_tables_but_not_templates():
    code = parse("""{|
| {{listing | name=Embassy A}}
|}
{{see | name=Temple | content=Near {{listing | name=Nested}} }}""")
    assert [str(t.get("name").value).strip() for t in find_listings(code)] == ["Embassy A", "Temple"]
