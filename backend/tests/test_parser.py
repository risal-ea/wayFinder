"""parse_article against the recorded pages (tests/fixtures/wikivoyage).

Counts and names come from the recorded revisions; if fixtures are refreshed
and an article has been edited, update the expectations here.
"""

from collections import Counter

import pytest

from wayfinder.providers.wikivoyage.parser import parse_article

from .conftest import load_page

ALL_PAGES = [
    "Kyoto", "Kyoto_Arashiyama", "Kyoto_Central", "Kyoto_Higashiyama", "Kyoto_North",
    "Kyoto_South", "Uji", "Peking", "Kansai", "Japan",
]


@pytest.fixture(scope="module")
def parsed():
    return {name: parse_article(load_page(name)) for name in ALL_PAGES}


# Article metadata

def test_kyoto_article(parsed):
    article = parsed["Kyoto"].article
    assert (article.kind, article.status, article.parent) == ("city", "guide", "Kyoto (prefecture)")
    assert article.lat == pytest.approx(35.0117, abs=1e-3) and article.lon == pytest.approx(135.7683, abs=1e-3)
    assert article.banner and article.banner.endswith(".png") or article.banner.endswith(".jpg")
    assert article.summary.startswith("Kyōto (京都) was the capital of Japan")
    assert [(d.name, d.title) for d in article.districts] == [
        ("Central", "Kyoto/Central"),
        ("Arashiyama", "Kyoto/Arashiyama"),
        ("Higashiyama", "Kyoto/Higashiyama"),
        ("North", "Kyoto/North"),
        ("South", "Kyoto/South"),
    ]
    assert all(d.description for d in article.districts)


@pytest.mark.parametrize(
    ("page", "kind", "status", "parent"),
    [
        ("Kyoto_Higashiyama", "district", "usable", "Kyoto"),
        ("Uji", "city", "guide", "Kyoto (prefecture)"),
        ("Peking", "city", "usable", "North China"),
        ("Kansai", "region", "usable", "Japan"),
        ("Japan", "country", "usable", "East Asia"),
    ],
)
def test_article_kinds(parsed, page, kind, status, parent):
    article = parsed[page].article
    assert (article.kind, article.status, article.parent) == (kind, status, parent)
    assert article.lat is not None and article.summary


def test_redirected_page_uses_canonical_title(parsed):
    beijing = parsed["Peking"]
    assert beijing.article.title == "Beijing"
    assert beijing.article.source.url == "https://en.wikivoyage.org/wiki/Beijing"


def test_country_regions_and_partially_linked_districts(parsed):
    assert [d.name for d in parsed["Japan"].article.districts][:3] == ["Hokkaido", "Tohoku", "Kanto"]
    beijing = parsed["Peking"].article.districts
    assert any(d.title is None for d in beijing)  # e.g. Dongcheng has no article of its own
    assert any(d.title == "Beijing/Xicheng" for d in beijing)


# Sections

def test_kyoto_section_tree(parsed):
    paths = [s.path for s in parsed["Kyoto"].sections]
    assert ["Understand", "Orientation"] in paths
    assert ["Get in", "By plane", "Through Kansai International Airport", "By train"] in paths
    assert ["Get around", "By bus"] in paths
    for section in parsed["Kyoto"].sections:
        assert section.title == section.path[-1]
        assert section.level == len(section.path) + 1  # "==" is level 2


def test_skipped_and_empty_sections(parsed):
    for result in parsed.values():
        for section in result.sections:
            assert section.text
            assert section.path[0].lower() not in {"see also", "references", "external links"}


@pytest.mark.parametrize("page", ALL_PAGES)
def test_plain_text_has_no_markup(parsed, page):
    result = parsed[page]
    texts = [result.article.summary] + [s.text for s in result.sections]
    texts += [value for item in result.listings for value in (item.name, item.alt, item.description) if value]
    for text in texts:
        for markup in ("{{", "}}", "[[", "]]", "'''", "<ref", "&ndash;", "&nbsp;"):
            assert markup not in text, f"{markup!r} left in: {text[:120]!r}"


# Listings

def test_higashiyama_listings(parsed):
    listings = parsed["Kyoto_Higashiyama"].listings
    assert len(listings) == 59
    assert Counter(item.type for item in listings) == {"see": 31, "sleep": 10, "eat": 9, "do": 6, "buy": 2, "drink": 1}
    assert {item.district for item in listings} == {"Higashiyama"}

    temple = next(item for item in listings if item.name == "Kiyomizu Temple")
    assert temple.alt == "清水寺" and temple.wikidata == "Q221716"
    assert (temple.lat, temple.lon) == pytest.approx((34.994831, 135.785003))
    assert temple.hours.startswith("Daily: 06:00–18:00")
    assert temple.section_path == ["See"]
    assert temple.source.title == "Kyoto/Higashiyama" and temple.source.revision_id > 0


@pytest.mark.parametrize(
    ("page", "count"),
    [("Kyoto_Arashiyama", 36), ("Kyoto_Central", 89), ("Kyoto_North", 48), ("Kyoto_South", 24), ("Kyoto", 5), ("Uji", 19)],
)
def test_listing_counts(parsed, page, count):
    assert len(parsed[page].listings) == count


def test_city_page_listings_have_no_district(parsed):
    assert {item.district for item in parsed["Kyoto"].listings} == {None}


def test_generic_listings_take_section_type(parsed):
    beijing = parsed["Peking"].listings
    assert len(beijing) == 100  # 82 of them inside the embassy table in "Cope"
    by_section = Counter((item.section_path[0], item.type) for item in beijing)
    assert by_section[("Cope", "other")] == 82
    assert by_section[("Get in", "go")] == 8
    airport = next(item for item in beijing if item.name == "Beijing Capital International Airport")
    assert airport.type == "go" and "(IATA: PEK)" in airport.alt


def test_listing_section_paths_are_nested(parsed):
    central = parsed["Kyoto_Central"].listings
    assert any(item.section_path[:2] == ["Sleep", "Budget"] and len(item.section_path) == 3 for item in central)


def test_regions_and_countries_have_no_listings(parsed):
    assert parsed["Japan"].listings == [] and parsed["Kansai"].listings == []
