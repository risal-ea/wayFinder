"""Save real Wikivoyage API responses for the offline tests.

    uv run python scripts/capture_fixtures.py

Requests go out one at a time through the normal client (same User-Agent,
pacing and retries). Re-run to refresh; tests only assert on facts that should
stay stable between revisions.

Writes tests/fixtures/wikivoyage/<name>.json plus manifest.json, which maps each
file to the exact request params so tests can serve it back with respx.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from pathlib import Path

from wayfinder.providers.wikivoyage.client import (
    WikivoyageApiError,
    WikivoyageClient,
    nearby_params,
    page_params,
    resolve_params,
    search_params,
    summary_params,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "wikivoyage"

KYOTO_DISTRICTS = ["Kyoto/Arashiyama", "Kyoto/Central", "Kyoto/Higashiyama", "Kyoto/North", "Kyoto/South"]

# (fixture kind, params). Cases follow docs/wikivoyage-plan.md, Step 2.
CASES: list[tuple[str, dict[str, str]]] = [
    # Large city with districts
    ("search", search_params("Kyoto", 5)),
    ("resolve", resolve_params("Kyoto")),
    ("summary", summary_params("Kyoto")),
    ("page", page_params("Kyoto")),
    *[("page", page_params(d)) for d in KYOTO_DISTRICTS],
    ("nearby", nearby_params(35.0116, 135.7681)),
    # Small city without districts
    ("resolve", resolve_params("Uji")),
    ("page", page_params("Uji")),
    # Redirect
    ("resolve", resolve_params("Peking")),
    ("page", page_params("Peking")),
    # Ambiguous name
    ("search", search_params("Springfield", 5)),
    ("resolve", resolve_params("Springfield")),
    # Region and country, not a city
    ("page", page_params("Kansai")),
    ("page", page_params("Japan")),
    # Missing article
    ("resolve", resolve_params("Nonexistentplacexyz")),
    ("summary", summary_params("Nonexistentplacexyz")),
    ("page", page_params("Nonexistentplacexyz")),
]


def fixture_name(kind: str, params: dict[str, str]) -> str:
    subject = params.get("page") or params.get("titles") or params.get("srsearch") or params.get("gscoord", "")
    return f"{kind}__{re.sub(r'[^A-Za-z0-9]+', '_', subject).strip('_')}.json"


async def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # our client logs each call already
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    async with WikivoyageClient.from_settings() as client:
        for kind, params in CASES:
            name = fixture_name(kind, params)
            try:
                payload = await client.call(params)
            except WikivoyageApiError as exc:
                # Keep API errors (e.g. missingtitle) as fixtures too.
                payload = {"error": {"code": exc.code, "info": exc.info}}
            (OUT_DIR / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            manifest.append({"file": name, "params": params})

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Saved {len(manifest)} fixtures to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
