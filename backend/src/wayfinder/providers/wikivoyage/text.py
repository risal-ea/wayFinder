"""Wikitext -> plain text.

Links keep their visible text, formatting is removed, and templates are dropped
unless they carry text that belongs in the sentence (see `INLINE_TEMPLATES`).
Listing templates are dropped here too; `templates.parse_listing` reads them.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import mwparserfromhell
from mwparserfromhell.nodes import (
    Comment,
    ExternalLink,
    Heading,
    HTMLEntity,
    Node,
    Tag,
    Template,
    Text,
    Wikilink,
)
from mwparserfromhell.wikicode import Wikicode

# <ref>, <gallery>, maps etc. hold no readable prose.
_DROPPED_TAGS = frozenset({
    "ref", "references", "gallery", "math", "score", "syntaxhighlight", "templatestyles",
    "mapframe", "maplink", "indicator", "timeline", "graph",
})
_LINE_TAGS = frozenset({"p", "div", "li", "dd", "dt", "tr", "table", "blockquote", "center"})
_CELL_TAGS = frozenset({"td", "th"})
_NON_CONTENT_LINK = re.compile(r"^:?\s*(file|image|media|category)\s*:", re.IGNORECASE)
_INTERLANGUAGE_LINK = re.compile(r"^[a-z]{2,3}(-[a-z]+)?:", re.IGNORECASE)
_MAGIC_WORD = re.compile(r"__[A-Z]+__")


def parse(wikitext: str | Wikicode) -> Wikicode:
    return wikitext if isinstance(wikitext, Wikicode) else mwparserfromhell.parse(str(wikitext))


def template_name(template: Template) -> str:
    """Normalised name: "Dead_link" -> "dead link", "Template:IsPartOf" -> "ispartof"."""
    name = str(template.name).strip().replace("_", " ").lower()
    return name.removeprefix("template:").strip()


def positional(template: Template) -> list[Wikicode]:
    return [p.value for p in template.params if not p.showkey]


def named(template: Template, *keys: str) -> Wikicode | None:
    """First of `keys` present on the template."""
    for key in keys:
        if template.has(key):
            return template.get(key).value
    return None


def to_text(wikitext: str | Wikicode | None) -> str:
    """Plain, tidied text for a piece of wikitext."""
    if wikitext is None:
        return ""
    return _tidy(_render(parse(wikitext)))


def _render(code: Wikicode) -> str:
    return "".join(_render_node(node) for node in code.nodes)


def _render_node(node: Node) -> str:
    if isinstance(node, Text):
        return str(node.value)
    if isinstance(node, HTMLEntity):
        return node.normalize()
    if isinstance(node, Wikilink):
        return _render_wikilink(node)
    if isinstance(node, ExternalLink):
        if node.title is not None:
            return _render(node.title)
        return "" if node.brackets else str(node.url)
    if isinstance(node, Template):
        renderer = INLINE_TEMPLATES.get(template_name(node))
        return renderer(node) if renderer else ""
    if isinstance(node, Tag):
        return _render_tag(node)
    if isinstance(node, Heading):
        return "\n" + _render(node.title).strip() + "\n"
    if isinstance(node, Comment):
        return ""
    return ""  # Argument ({{{x}}}) and anything unexpected


def _render_wikilink(link: Wikilink) -> str:
    target = str(link.title).strip()
    if _NON_CONTENT_LINK.match(target):
        return ""
    if link.text is not None:
        return _render(link.text)
    if _INTERLANGUAGE_LINK.match(target):
        return ""
    return target.lstrip(":").split("#", 1)[0]


def _render_tag(tag: Tag) -> str:
    name = str(tag.tag).strip().lower()
    if name in _DROPPED_TAGS:
        return ""
    if name == "br" or name == "hr":
        return "\n"
    contents = _render(tag.contents) if tag.contents is not None else ""
    if tag.wiki_markup:  # "*"/"#" list items and ":"/";" indents are markers at the start of a line
        if name == "li":
            return "- " + contents
        if name in {"dd", "dt"}:
            return contents
    if name in _CELL_TAGS:
        return " " + contents.strip() + " "
    if name in _LINE_TAGS:
        return "\n" + contents + "\n"
    return contents


# Templates whose output is part of the sentence. Everything else renders to "".

def _first(template: Template) -> str:
    args = positional(template)
    return _render(args[0]).strip() if args else ""


def _last(template: Template) -> str:
    args = positional(template)
    return _render(args[-1]).strip() if args else ""


def _iata(template: Template) -> str:
    code = _first(template)
    return f"(IATA: {code})" if code else ""


def _km(template: Template) -> str:
    value = _first(template)
    return f"{value} km" if value else ""


def _marker(template: Template) -> str:
    name = named(template, "name")
    return _render(name).strip() if name is not None else ""


_RANGE_WORDS = frozenset({"to", "-", "and", "or", "by", "x", "×", "–"})


def _convert(template: Template) -> str:
    """{{convert|1.445|to|1.824|m2|...}} -> "1.445 to 1.824 m2" (value(s) + first unit)."""
    words: list[str] = []
    for arg in positional(template):
        word = _render(arg).strip()
        if not word:
            continue
        words.append(word)
        if not _is_number(word) and word.lower() not in _RANGE_WORDS:
            break  # first unit reached
    return " ".join(words)


def _is_number(word: str) -> bool:
    try:
        float(word.replace(",", ""))
    except ValueError:
        return False
    return True


INLINE_TEMPLATES: dict[str, Callable[[Template], str]] = {
    "lang": _last,          # {{Lang|ja|義理チョコ}}
    "nowrap": _first,
    "nobr": _first,
    "phone": _first,
    "iata": _iata,          # {{IATA|NRT}}
    "km": _km,              # {{km|256}}
    "convert": _convert,
    "marker": _marker,      # {{marker|type=city|name=[[Tokyo]]|...}}
}


def _tidy(text: str) -> str:
    text = _MAGIC_WORD.sub("", text)
    lines = []
    for raw in text.split("\n"):
        line = re.sub(r"[ \t ​]+", " ", raw).strip()
        markers = re.match(r"^([*#:;]+)\s*", line)
        if markers:
            rest = line[markers.end():].strip()
            line = f"- {rest}" if rest and ("*" in markers.group(1) or "#" in markers.group(1)) else rest
        line = re.sub(r"\(\s*[,;]?\s*\)", "", line)        # "()" left by dropped templates
        line = re.sub(r"\s+([,.;:!?])", r"\1", line)        # "word ," -> "word,"
        line = re.sub(r" {2,}", " ", line).strip()
        depth = 0
        while line.startswith("- ") or line == "-":
            depth, line = depth + 1, line[2:]
        if depth and line:
            line = "  " * (depth - 1) + "- " + line  # "**" nesting -> indented sub-bullet
        if line == "|":
            line = ""
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
