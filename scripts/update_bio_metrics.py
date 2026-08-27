#!/usr/bin/env python3
"""Refresh the bio's Google Scholar metrics with conservative validation.

Google Scholar has no supported public metrics API. This script uses SerpApi's
structured Scholar Author endpoint, validates the identity and every parsed
value, and preserves the last known-good file on any failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROFILE_ID = "R2ntI8IAAAAJ"
PROFILE_NAME = "Kevin Maik Jablonka"
PROFILE_URL = f"https://scholar.google.com/citations?user={PROFILE_ID}&hl=en"
SERPAPI_URL = "https://serpapi.com/search.json"
USER_AGENT = "kjablonka-bio-metrics/1.0 (+https://kjablonka.com/bio)"


def parse_profile(payload: dict[str, object]) -> dict[str, int]:
    if payload.get("error"):
        raise ValueError(f"SerpApi reported an error: {payload['error']}")

    metadata = payload.get("search_metadata")
    if not isinstance(metadata, dict) or metadata.get("status") != "Success":
        raise ValueError("SerpApi response was not marked successful")

    author = payload.get("author")
    if not isinstance(author, dict) or author.get("name") != PROFILE_NAME:
        raise ValueError("Scholar profile identity did not match Kevin Maik Jablonka")

    cited_by = payload.get("cited_by")
    table = cited_by.get("table") if isinstance(cited_by, dict) else None
    if not isinstance(table, list) or len(table) < 3:
        raise ValueError("Scholar metric table was incomplete")

    expected = ("citations", "h_index", "i10_index")
    values: dict[str, int] = {}
    for row in table:
        if not isinstance(row, dict):
            continue
        for key in expected:
            metric = row.get(key)
            if metric is None:
                continue
            if not isinstance(metric, dict) or not isinstance(metric.get("all"), int):
                raise ValueError(f"Scholar {key} row did not contain an integer total")
            values[key] = metric["all"]

    missing = [key for key in expected if key not in values]
    if missing:
        raise ValueError(f"Scholar metric table omitted: {', '.join(missing)}")
    return values


def fetch_profile(api_key: str) -> dict[str, object]:
    query = urlencode(
        {
            "engine": "google_scholar_author",
            "author_id": PROFILE_ID,
            "hl": "en",
            "api_key": api_key,
        }
    )
    request = Request(f"{SERPAPI_URL}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"SerpApi returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        # Avoid including a request URL containing the API secret in error output.
        raise RuntimeError(f"SerpApi request failed ({type(error).__name__})") from error
    if not isinstance(payload, dict):
        raise ValueError("SerpApi response was not a JSON object")
    return payload


def load_existing(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate(metrics: dict[str, int], previous: dict[str, object] | None) -> None:
    if metrics["citations"] < 1000:
        raise ValueError("Citation count failed the minimum sanity check")
    if not 5 <= metrics["h_index"] <= 200:
        raise ValueError("h-index failed its sanity check")
    if not 5 <= metrics["i10_index"] <= 500:
        raise ValueError("i10-index failed its sanity check")

    if previous:
        old_citations = int(previous.get("citations", 0))
        old_h_index = int(previous.get("h_index", 0))
        old_i10_index = int(previous.get("i10_index", 0))
        if metrics["citations"] < old_citations:
            raise ValueError("Citation count decreased; refusing an automatic update")
        if old_citations and metrics["citations"] > old_citations * 1.5:
            raise ValueError("Citation count jumped by more than 50%; refusing an automatic update")
        if metrics["h_index"] < old_h_index or metrics["i10_index"] < old_i10_index:
            raise ValueError("Scholar indices decreased; refusing an automatic update")


def build_payload(metrics: dict[str, int], _previous: dict[str, object] | None) -> dict[str, object]:
    return {
        "profile": PROFILE_NAME,
        "profile_id": PROFILE_ID,
        **metrics,
        "as_of": datetime.now(UTC).date().isoformat(),
        "source": "Google Scholar",
        "source_url": PROFILE_URL,
    }


def write_if_changed(path: Path, payload: dict[str, object]) -> bool:
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == serialized:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)
    return True


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=repository_root / "bio-metrics.json",
        help="Path to the validated JSON output.",
    )
    parser.add_argument(
        "--json-file",
        type=Path,
        help="Parse a saved SerpApi response instead of making a network request.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print validated JSON without writing it.")
    args = parser.parse_args()

    try:
        api_key = os.environ.get("SERPAPI_KEY", "")
        if args.json_file:
            response_payload = json.loads(args.json_file.read_text(encoding="utf-8"))
        elif api_key:
            response_payload = fetch_profile(api_key)
        else:
            raise RuntimeError("SERPAPI_KEY is required for a live refresh")
        if not isinstance(response_payload, dict):
            raise ValueError("SerpApi response was not a JSON object")
        metrics = parse_profile(response_payload)
        previous = load_existing(args.output)
        validate(metrics, previous)
        payload = build_payload(metrics, previous)
        if args.dry_run:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        changed = write_if_changed(args.output, payload)
        print("Updated bio metrics." if changed else "Bio metrics are already current.")
        return 0
    except Exception as error:  # Keep the last validated file intact on every failure.
        print(f"Bio metric refresh failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
