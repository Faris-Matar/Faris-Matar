#!/usr/bin/env python3
"""Photo -> grayscale prepped.png, ready for ASCII conversion.

Three steps, in this order, each fixing a specific problem:

  1. rembg strips the background, isolating the subject.
  2. OpenCV CLAHE (contrast-limited adaptive histogram equalization) boosts
     local contrast -- a flatly-lit face otherwise converts to a dark,
     unreadable blob.
  3. Composite onto pure white, so the background maps to the blank end of
     the ASCII density ramp (white -> space) instead of printing as glyphs.

Run once per photo. scripts/make_ascii_svg.py can then be re-run freely
without re-prepping.

Usage: python scripts/prep_photo.py source-photo.jpg

First run downloads the rembg U2-Net model (~170 MB) to ~/.u2net/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import remove

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "prepped.png"

MAX_SIDE = 1400        # downscale huge inputs before processing (rembg is slow)
CROP_MARGIN = 0.06     # padding around the subject bounding box, as a fraction
CLAHE_CLIP = 2.5
CLAHE_TILE = 8


def load_downscaled(src: Path) -> Image.Image:
    img = Image.open(src).convert("RGB")
    w, h = img.size
    scale = MAX_SIDE / max(w, h)
    if scale < 1:
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    return img


def crop_to_subject(rgb: np.ndarray, alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.where(alpha > 24)
    if len(xs) == 0:
        return rgb, alpha
    h, w = alpha.shape
    mx = int((xs.max() - xs.min()) * CROP_MARGIN)
    my = int((ys.max() - ys.min()) * CROP_MARGIN)
    x0, x1 = max(0, xs.min() - mx), min(w, xs.max() + mx + 1)
    y0, y1 = max(0, ys.min() - my), min(h, ys.max() + my + 1)
    return rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python scripts/prep_photo.py <photo>", file=sys.stderr)
        return 2
    src = Path(argv[1])
    if not src.exists():
        print(f"not found: {src}", file=sys.stderr)
        return 1

    print(f"[1/3] rembg: removing background from {src.name} ...")
    cut = remove(load_downscaled(src))          # RGBA
    arr = np.array(cut.convert("RGBA"))
    rgb, alpha = arr[..., :3], arr[..., 3]
    rgb, alpha = crop_to_subject(rgb, alpha)

    print("[2/3] CLAHE: boosting local contrast ...")
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP,
                            tileGridSize=(CLAHE_TILE, CLAHE_TILE))
    eq = clahe.apply(gray)

    print("[3/3] compositing subject onto pure white ...")
    a = (alpha.astype(np.float32) / 255.0)
    out = eq.astype(np.float32) * a + 255.0 * (1.0 - a)
    out = np.clip(out, 0, 255).astype(np.uint8)

    Image.fromarray(out, mode="L").save(OUT)
    print(f"wrote {OUT.relative_to(Path.cwd())}  ({out.shape[1]}x{out.shape[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
