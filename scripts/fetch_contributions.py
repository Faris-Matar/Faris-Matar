#!/usr/bin/env python3
"""Scrape the public GitHub contribution calendar and derive stats.

No token, no GraphQL. GitHub serves the calendar as public HTML at
https://github.com/users/<username>/contributions -- we fetch that with
requests and parse the day cells with BeautifulSoup.

Writes data/contributions.json with the raw per-day counts plus derived
stats (current streak, longest streak, best single day, monthly totals).

Usage: python scripts/fetch_contributions.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")  # hush the LibreSSL/urllib3 notice on stock macOS

import requests
from bs4 import BeautifulSoup

USERNAME = "Faris-Matar"
URL = f"https://github.com/users/{USERNAME}/contributions"
OUT = Path(__file__).resolve().parent.parent / "data" / "contributions.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html",
}

_COUNT_RE = re.compile(r"^([\d,]+)\s+contribution", re.I)


def fetch_html() -> str:
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_days(html: str) -> list[dict]:
    """Return a chronological list of {date, count} for every day in the calendar."""
    soup = BeautifulSoup(html, "html.parser")

    tips: dict[str, str] = {
        t.get("for", ""): t.get_text(strip=True) for t in soup.select("tool-tip")
    }

    days: list[dict] = []
    for cell in soup.select("td.ContributionCalendar-day"):
        date = cell.get("data-date")
        if not date:
            continue

        count = None
        tip = tips.get(cell.get("id", ""))
        if tip:
            if tip.lower().startswith("no contribution"):
                count = 0
            else:
                m = _COUNT_RE.match(tip)
                if m:
                    count = int(m.group(1).replace(",", ""))
        if count is None:  # no tooltip -> fall back to the coarse level bucket
            level = int(cell.get("data-level", "0") or "0")
            count = 0 if level == 0 else level

        days.append({"date": date, "count": count})

    if not days:
        raise RuntimeError(
            "No contribution day cells found -- GitHub markup may have changed."
        )

    days.sort(key=lambda d: d["date"])
    return days


def headline_total(html: str) -> int | None:
    soup = BeautifulSoup(html, "html.parser")
    h2 = soup.find("h2")
    if not h2:
        return None
    m = re.search(r"([\d,]+)\s+contribution", h2.get_text(" ", strip=True), re.I)
    return int(m.group(1).replace(",", "")) if m else None


def _runs(days: list[dict]) -> list[tuple[str, str, int]]:
    """All maximal runs of consecutive active days as (start, end, length)."""
    runs: list[tuple[str, str, int]] = []
    start = None
    prev = None
    for d in days:
        if d["count"] > 0:
            if start is None:
                start = d["date"]
            prev = d["date"]
        else:
            if start is not None:
                runs.append((start, prev, _daydiff(start, prev) + 1))
            start = None
    if start is not None:
        runs.append((start, prev, _daydiff(start, prev) + 1))
    return runs


def _daydiff(a: str, b: str) -> int:
    da = dt.date.fromisoformat(a)
    db = dt.date.fromisoformat(b)
    return (db - da).days


def derive_stats(days: list[dict], headline: int | None) -> dict:
    total = sum(d["count"] for d in days)

    runs = _runs(days)
    longest = max(runs, key=lambda r: r[2], default=("", "", 0))

    # Current streak: consecutive active days ending on the last calendar day
    # (or the day before it, so an as-yet-empty "today" doesn't break it).
    today = days[-1]["date"]
    cur_len, cur_start, cur_end = 0, None, None
    for d in reversed(days):
        if d["count"] > 0:
            cur_len += 1
            cur_start = d["date"]
            if cur_end is None:
                cur_end = d["date"]
        elif d["date"] == today:
            continue  # allow an empty final day
        else:
            break

    best = max(days, key=lambda d: d["count"])

    monthly: dict[str, int] = {}
    for d in days:
        monthly[d["date"][:7]] = monthly.get(d["date"][:7], 0) + d["count"]

    return {
        "total": total,
        "total_headline": headline if headline is not None else total,
        "active_days": sum(1 for d in days if d["count"] > 0),
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {
            "length": longest[2],
            "start": longest[0] or None,
            "end": longest[1] or None,
        },
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly_totals": monthly,
    }


def main() -> int:
    try:
        html = fetch_html()
    except requests.RequestException as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    days = parse_days(html)
    headline = headline_total(html)
    stats = derive_stats(days, headline)

    payload = {
        "username": USERNAME,
        "generated_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "range": {"from": days[0]["date"], "to": days[-1]["date"]},
        "days": days,
        "stats": stats,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")

    s = stats
    print(f"wrote {OUT.relative_to(Path.cwd())}")
    print(f"  {len(days)} days  |  {s['total']} contributions  |  headline {s['total_headline']}")
    print(f"  current streak {s['current_streak']['length']}d  |  longest {s['longest_streak']['length']}d")
    print(f"  best day {s['best_day']['date']} ({s['best_day']['count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
