#!/usr/bin/env python3
"""Hand-authored neofetch-style info card as a self-contained animated SVG.

A title bar, a `user@host` header, a rule, then colour-coded key/value
rows, then the classic neofetch palette blocks. Each logical line fades
and slides in on a short top-to-bottom stagger (CSS @keyframes, not SMIL,
so it plays inside GitHub's <img> embed).

Set STATIC=1 to emit a frozen, animation-free frame -- handy for macOS
Quick Look / file previews that don't run SVG animation.

Usage: python scripts/make_info_card.py   ->   writes info-card.svg
"""
from __future__ import annotations

import html
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "info-card.svg"
STATIC = os.environ.get("STATIC") == "1"

# ---------------------------------------------------------------- content ----
USER = "faris-matar"
HOST = "github"

ROWS: list[tuple[str, list[str]]] = [
    ("Now", ["Job hunting, AI/ML Engineer roles, London"]),
    ("Prev", ["BEng EEE, First Class Honours, Coventry University"]),
    ("Stack", ["Python, React, Claude Code, embedded systems"]),
    ("Highlights", ["Course Director's Prize (top of cohort) · Multi-agent",
                    "GenAI validator · Real-time eye-tracking control system"]),
]

# ------------------------------------------------------------------ style ----
MONO = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', monospace")

BG = "#0d1117"
STROKE = "#30363d"
BAR = "#161b22"
KEY = "#3fb950"        # neofetch colours its keys in the accent
VAL = "#c9d1d9"
ACCENT = "#3fb950"
DIM = "#6e7681"
AT = "#8b949e"

# neofetch's signature palette blocks: a normal row then a bright row
ANSI = ["#f85149", "#3fb950", "#d29922", "#58a6ff",
        "#bc8cff", "#39c5cf", "#b1bac4", "#6e7681"]
ANSI_BRIGHT = ["#ff7b72", "#56d364", "#e3b341", "#79c0ff",
               "#d2a8ff", "#56d4dd", "#f0f6fc", "#8b949e"]

# ---------------------------------------------------------------- geometry ---
W = 650
PAD = 26
BAR_H = 32
FS = 14                # body font-size
LH = 25                # body line-height
KEY_X = PAD
VAL_X = PAD + 104
HEAD_Y = BAR_H + 34
RULE_Y = HEAD_Y + 9
ROWS_Y = RULE_Y + 26
GROUP_GAP = 7          # extra space between key groups
SWATCH = 15
SWATCH_GAP = 6


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def build() -> str:
    p: list[str] = []

    # measured line boxes, top to bottom, each an animation unit
    lines: list[str] = []

    def line(inner: str) -> None:
        lines.append(inner)

    # header + rule
    line(
        f'<text x="{PAD}" y="{HEAD_Y}" font-family="{MONO}" font-size="{FS}" '
        f'font-weight="700">'
        f'<tspan fill="{ACCENT}">{USER}</tspan>'
        f'<tspan fill="{AT}" font-weight="400">@</tspan>'
        f'<tspan fill="{ACCENT}">{HOST}</tspan></text>'
    )
    # neofetch draws the rule exactly as wide as the "user@host" header
    rule_w = int(len(f"{USER}@{HOST}") * FS * 0.6)
    line(
        f'<line x1="{PAD}" y1="{RULE_Y}" x2="{PAD + rule_w}" y2="{RULE_Y}" '
        f'stroke="{DIM}"/>'
    )

    # key / value rows
    y = ROWS_Y
    for key, vals in ROWS:
        for i, val in enumerate(vals):
            key_tspan = (
                f'<tspan x="{KEY_X}" fill="{KEY}" font-weight="700">{esc(key)}</tspan>'
                if i == 0 else ""
            )
            line(
                f'<text y="{y}" font-family="{MONO}" font-size="{FS}">'
                f'{key_tspan}'
                f'<tspan x="{VAL_X}" fill="{VAL}">{esc(val)}</tspan></text>'
            )
            y += LH
        y += GROUP_GAP

    # palette blocks (neofetch signature): normal row + bright row
    y += 10
    for palette in (ANSI, ANSI_BRIGHT):
        blocks = [
            f'<rect x="{PAD + i * (SWATCH + SWATCH_GAP)}" y="{y - SWATCH + 2}" '
            f'width="{SWATCH}" height="{SWATCH}" rx="3" fill="{c}"/>'
            for i, c in enumerate(palette)
        ]
        line("".join(blocks))
        y += SWATCH + 5
    bottom = y - SWATCH + 2 + PAD

    height = int(bottom)

    # ---- assemble ----
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" role="img" '
        f'aria-label="{USER}@{HOST} info card">'
    )
    p.append(f'<title>{USER}@{HOST}</title>')

    if not STATIC:
        # fill-mode:both -> a clean cascade that matches the portrait's type-in
        # (they sit side by side and read as one reveal). Non-animating file
        # previews should use STATIC=1.
        p.append(
            '<style>'
            '.ln{animation-name:lnIn;animation-duration:.42s;'
            'animation-timing-function:ease-out;animation-fill-mode:both;'
            'animation-delay:var(--d,0s)}'
            '@keyframes lnIn{'
            'from{opacity:0;transform:translateX(-9px)}'
            'to{opacity:1;transform:translateX(0)}}'
            '@media(prefers-reduced-motion:reduce){.ln{animation:none}}'
            '</style>'
        )

    p.append(
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{height - 1}" rx="10" '
        f'fill="{BG}" stroke="{STROKE}"/>'
    )
    # title bar
    p.append(
        f'<path d="M0 10 Q0 0 10 0 H{W - 10} Q{W} 0 {W} 10 V{BAR_H} H0 Z" '
        f'fill="{BAR}"/>'
    )
    p.append(f'<line x1="0" y1="{BAR_H}" x2="{W}" y2="{BAR_H}" stroke="{STROKE}"/>')
    for i, c in enumerate(("#f85149", "#d29922", "#3fb950")):
        p.append(f'<circle cx="{PAD - 6 + i * 20}" cy="{BAR_H // 2}" r="6" fill="{c}"/>')
    p.append(
        f'<text x="{W // 2}" y="{BAR_H // 2 + 4}" text-anchor="middle" '
        f'font-family="{MONO}" font-size="11" fill="{DIM}">neofetch</text>'
    )

    # emit each line as an animation unit
    for idx, inner in enumerate(lines):
        if STATIC:
            p.append(f'<g>{inner}</g>')
        else:
            delay = 0.12 + idx * 0.06
            p.append(f'<g class="ln" style="--d:{delay:.2f}s">{inner}</g>')

    p.append('</svg>')
    return "\n".join(p)


def main() -> int:
    OUT.write_text(build() + "\n")
    mode = "static" if STATIC else "animated"
    print(f"wrote {OUT.relative_to(Path.cwd())}  ({mode}, {OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
