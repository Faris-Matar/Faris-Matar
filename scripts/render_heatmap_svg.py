#!/usr/bin/env python3
"""Render data/contributions.json as an animated contribution heatmap SVG.

The familiar 53-week x 7-day grid of rounded, coloured boxes. The grid
reveals once on load with a diagonal, cell-after-cell slide-down (CSS
@keyframes, animation-fill-mode: both) -- it plays a single time and then
holds still. No looping glow. A Less->More legend and a stats footer line
sit below the grid.

CSS @keyframes (not SMIL) because GitHub embeds the SVG via <img>, and
CSS animation is the only motion that reliably plays in that context
across Chrome / Firefox / Safari.

Usage: python scripts/render_heatmap_svg.py   ->   writes contrib-heatmap.svg
"""
from __future__ import annotations

import datetime as dt
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "contrib-heatmap.svg"

PALETTE = ["#161b22", "#0e4429", "#006d32",
           "#26a641", "#39d353", "#69f0a0"]
#          none -> brightest (level 5 is a deliberately neon top end)

# --- geometry -------------------------------------------------------------
CELL = 11          # box side
GAP = 3            # gap between boxes
PITCH = CELL + GAP
PAD = 16           # inner padding of the card
LABEL_COL = 30     # width reserved for Mon/Wed/Fri labels
MONTH_ROW = 18     # height reserved for month labels
GRID_GAP = 16      # grid -> legend/footer gap
FOOT_ROW = 18

MONO = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', monospace")

FG = "#c9d1d9"
MUTED = "#8b949e"
DIM = "#6e7681"
CARD_BG = "#0d1117"
CARD_STROKE = "#30363d"

WEEKDAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def level_for(count: int, mx: int) -> int:
    if count <= 0:
        return 0
    if mx <= 1:
        return 1
    return min(5, 1 + math.floor(5 * (count - 1) / (mx - 1)))


def build_weeks(days: list[dict]) -> list[list[dict | None]]:
    first = dt.date.fromisoformat(days[0]["date"])
    pad = first.isoweekday() % 7          # Sunday -> 0, matches GitHub columns
    cells: list[dict | None] = [None] * pad + list(days)
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


def month_labels(weeks: list[list[dict | None]]) -> list[tuple[int, str]]:
    """One label per month, at the first column that lands in it -- mirrors
    GitHub: a stub first column (starting late in a month) gets no label, and
    labels never crowd within 3 columns of each other."""
    out: list[tuple[int, str]] = []
    prev_month = None
    prev_wi = -10
    for wi, week in enumerate(weeks):
        first_day = next((c for c in week if c), None)
        if not first_day:
            continue
        d = dt.date.fromisoformat(first_day["date"])
        if d.month == prev_month:
            continue
        prev_month = d.month
        if wi == 0 and d.day > 7:
            continue
        if wi - prev_wi < 3:
            continue
        out.append((wi, MONTHS[d.month - 1]))
        prev_wi = wi
    return out


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def render(payload: dict) -> str:
    days = payload["days"]
    stats = payload["stats"]
    mx = max((d["count"] for d in days), default=0)
    weeks = build_weeks(days)
    n_weeks = len(weeks)

    grid_w = n_weeks * PITCH - GAP
    grid_h = 7 * PITCH - GAP
    grid_x = PAD + LABEL_COL
    grid_y = PAD + MONTH_ROW

    width = grid_x + grid_w + PAD
    height = grid_y + grid_h + GRID_GAP + FOOT_ROW + PAD

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(payload["username"])} GitHub contribution heatmap">'
    )
    parts.append(
        f'<title>{esc(stats["total_headline"])} contributions in the last year</title>'
    )
    # fill-mode:forwards + a positive per-cell delay (never 0): a renderer that
    # freezes SVGs at t=0 -- e.g. some file previews -- shows every cell at its
    # natural opacity instead of a blank grid, while real browsers still play
    # the diagonal sweep. The "from" state only dims to 0.15 (not 0) so the
    # pre-delay frame reads as a shimmer, not a flash.
    parts.append(
        '<style>'
        '.cell{animation-name:cellIn;animation-duration:.36s;'
        'animation-timing-function:ease-out;animation-fill-mode:forwards;'
        'animation-delay:var(--d,0s)}'
        '@keyframes cellIn{'
        'from{opacity:.15;transform:translateY(-4px)}'
        'to{opacity:1;transform:translateY(0)}}'
        '@media(prefers-reduced-motion:reduce){.cell{animation:none}}'
        '</style>'
    )
    parts.append(
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{CARD_BG}" stroke="{CARD_STROKE}"/>'
    )

    # month labels
    for wi, name in month_labels(weeks):
        x = grid_x + wi * PITCH
        parts.append(
            f'<text x="{x}" y="{grid_y - 6}" font-family="{MONO}" font-size="10" '
            f'fill="{MUTED}">{name}</text>'
        )

    # weekday labels
    for row, label in WEEKDAY_LABELS.items():
        y = grid_y + row * PITCH + CELL - 1
        parts.append(
            f'<text x="{PAD}" y="{y}" font-family="{MONO}" font-size="9" '
            f'fill="{MUTED}">{label}</text>'
        )

    # day cells -- diagonal slide-down reveal, plays once then freezes
    base = 0.15
    step = 0.011
    parts.append(f'<g transform="translate({grid_x},{grid_y})">')
    for wi, week in enumerate(weeks):
        for di in range(7):
            if di >= len(week) or week[di] is None:
                continue
            cell = week[di]
            lvl = level_for(cell["count"], mx)
            x = wi * PITCH
            y = di * PITCH
            delay = f"{base + (wi + di) * step:.2f}s"
            parts.append(
                f'<rect class="cell" style="--d:{delay}" x="{x}" y="{y}" '
                f'width="{CELL}" height="{CELL}" rx="2" fill="{PALETTE[lvl]}"/>'
            )
    parts.append('</g>')

    # footer row: stats line (left) + Less..More legend (right)
    foot_y = grid_y + grid_h + GRID_GAP + 10
    ls = stats["longest_streak"]["length"]
    cs = stats["current_streak"]["length"]
    footer = (
        f'{stats["total_headline"]} contributions in the last year'
        f'  ·  {stats["active_days"]} active days'
        f'  ·  longest streak {ls} day{"s" if ls != 1 else ""}'
    )
    if cs:
        footer += f'  ·  current {cs} day{"s" if cs != 1 else ""}'
    parts.append(
        f'<text x="{grid_x}" y="{foot_y}" font-family="{MONO}" font-size="10" '
        f'fill="{DIM}">{esc(footer)}</text>'
    )

    legend_box = 10
    legend_gap = 3
    legend_w = 4 * legend_gap + 6 * legend_box + 66
    lx = grid_x + grid_w - legend_w
    parts.append(
        f'<text x="{lx}" y="{foot_y}" font-family="{MONO}" font-size="10" '
        f'fill="{DIM}">Less</text>'
    )
    sx = lx + 30
    for i, color in enumerate(PALETTE):
        parts.append(
            f'<rect x="{sx + i * (legend_box + legend_gap)}" y="{foot_y - legend_box + 1}" '
            f'width="{legend_box}" height="{legend_box}" rx="2" fill="{color}"/>'
        )
    parts.append(
        f'<text x="{sx + 6 * (legend_box + legend_gap) + 4}" y="{foot_y}" '
        f'font-family="{MONO}" font-size="10" fill="{DIM}">More</text>'
    )

    parts.append('</svg>')
    return "\n".join(parts)


def main() -> int:
    payload = json.loads(DATA.read_text())
    OUT.write_text(render(payload) + "\n")
    size = OUT.stat().st_size
    print(f"wrote {OUT.relative_to(Path.cwd())}  ({size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
