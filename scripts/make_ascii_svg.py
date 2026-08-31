#!/usr/bin/env python3
"""prepped.png -> self-typing monochrome ASCII-portrait SVG.

Downsamples prepped.png to a ~100-wide character grid and maps each cell's
brightness to a glyph on a fixed density ramp. Renders one light-gray
monochrome SVG: each row wipes in left-to-right behind a small block
cursor, staggered top-to-bottom, so the portrait types itself in row by
row. Plays once (CSS @keyframes, fill-mode both) and freezes -- no loop.

Set STATIC=1 to emit a frozen, animation-free frame for file previews
that don't run SVG animation.

Usage: python scripts/make_ascii_svg.py   ->   writes portrait-ascii.svg
"""
from __future__ import annotations

import html
import os
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "prepped.png"
OUT = ROOT / "portrait-ascii.svg"
STATIC = os.environ.get("STATIC") == "1"

RAMP = " .`:-=+*cs#%@"   # bright (sparse) -> dark (dense)
#        ^ leading space is deliberate, it clears the background to nothing

COLS = int(os.environ.get("COLS", "100"))
CELL_ASPECT = float(os.environ.get("CELL_ASPECT", "0.53"))  # char width / line height

FS = 13
CW = FS * 0.6                       # monospace advance width
CH = round(CW / CELL_ASPECT)        # line height
PAD = 18

BG = "#0d1117"
STROKE = "#30363d"
INK = "#9ba7b4"                     # the single monochrome fill

ROW_DUR = 0.5
ROW_STEP = 0.03
ROW_BASE = 0.1


def load_grid() -> list[str]:
    if not SRC.exists():
        raise SystemExit(
            f"{SRC.name} not found -- run: python scripts/prep_photo.py source-photo.jpg"
        )
    img = Image.open(SRC).convert("L")
    w, h = img.size
    rows = max(1, round(h / w * COLS * CELL_ASPECT))
    small = img.resize((COLS, rows), Image.LANCZOS)
    px = np.asarray(small, dtype=np.float32)

    last = len(RAMP) - 1
    idx = np.rint((255.0 - px) / 255.0 * last).astype(int)
    idx = np.clip(idx, 0, last)

    lines = ["".join(RAMP[i] for i in row) for row in idx]
    # trim fully-blank rows from the top and bottom
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def build(lines: list[str]) -> str:
    n = len(lines)
    grid_w = COLS * CW
    width = round(grid_w + 2 * PAD)
    height = round(n * CH + 2 * PAD)
    row_w = round(grid_w, 1)

    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="ASCII-art portrait">'
    )
    p.append('<title>ASCII-art portrait</title>')

    if not STATIC:
        p.append(
            '<style>'
            'text{white-space:pre}'
            f'.row{{clip-path:inset(0 0 0 0);'
            f'animation:type {ROW_DUR}s ease-out var(--d) both}}'
            '@keyframes type{from{clip-path:inset(0 100% 0 0)}'
            'to{clip-path:inset(0 -2px 0 0)}}'
            f'.cur{{animation:cur {ROW_DUR}s ease-out var(--d) both}}'
            '@keyframes cur{'
            'from{transform:translateX(0);opacity:1}'
            '92%{opacity:1}'
            f'to{{transform:translateX({row_w}px);opacity:0}}}}'
            '@media(prefers-reduced-motion:reduce){'
            '.row,.cur{animation:none}.cur{opacity:0}}'
            '</style>'
        )

    p.append(
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{BG}" stroke="{STROKE}"/>'
    )

    p.append(
        f'<g font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
        f'font-size="{FS}" fill="{INK}" '
        f'transform="translate({PAD},{PAD + FS})">'
    )

    for i, line in enumerate(lines):
        y = round(i * CH, 1)
        text = (
            f'<text x="0" y="{y}" textLength="{row_w}" lengthAdjust="spacingAndGlyphs" '
            f'xml:space="preserve">{esc(line)}</text>'
        )
        if STATIC:
            p.append(f'<g>{text}</g>')
            continue
        delay = ROW_BASE + i * ROW_STEP
        cursor = (
            f'<rect class="cur" style="--d:{delay:.2f}s" x="0" y="{y - FS + 2}" '
            f'width="{CW:.1f}" height="{FS}" fill="{INK}"/>'
        )
        p.append(f'<g class="row" style="--d:{delay:.2f}s">{text}{cursor}</g>')

    p.append('</g>')
    p.append('</svg>')
    return "\n".join(p)


def main() -> int:
    lines = load_grid()
    OUT.write_text(build(lines) + "\n")
    mode = "static" if STATIC else "animated"
    print(f"wrote {OUT.relative_to(Path.cwd())}  "
          f"({mode}, {COLS}x{len(lines)} grid, {OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
