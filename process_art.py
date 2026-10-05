"""
process_art.py
──────────────
Turns the region paintings in art-inbox/ into what the home page scene needs:

  <out>/<region>.webp         the painting, 2560 px wide (desktop)
  <out>/<region>-m.webp       a 1080x1920 portrait crop around the focal point (phones)
  <out>/<region>-depth.webp   a soft depth map: white = near, black = far

The paintings use atmospheric perspective (bright sky far away, dark
silhouettes up close), so brightness is a good stand-in for depth. A heavy blur
keeps the parallax smooth so shapes never tear apart.

Usage:
  python process_art.py                      # art-inbox/*.png|jpg|webp -> public/art
  python process_art.py --src DIR --out DIR  # e.g. stand-ins for local testing
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

REGIONS = ["mondstadt", "liyue", "inazuma", "sumeru-forest", "sumeru-desert",
           "fontaine", "natlan", "nod-krai", "snezhnaya"]

# Where the main subject sits, as a fraction of the width, for the phone crop.
FOCUS_X = {"mondstadt": 0.75, "liyue": 0.66, "inazuma": 0.72, "sumeru-forest": 0.55, "sumeru-desert": 0.7,
           "fontaine": 0.72, "natlan": 0.62, "nod-krai": 0.4, "snezhnaya": 0.68}


def depth_map(img: Image.Image) -> Image.Image:
    small = img.convert("L").resize((512, round(512 * img.height / img.width)))
    lum = np.asarray(small, dtype=np.float32) / 255.0
    near = 1.0 - lum                                   # dark = near...
    rows = np.linspace(0.0, 1.0, near.shape[0])[:, None]
    land = np.clip((rows - 0.12) / 0.55, 0.0, 1.0) ** 1.3
    near = 0.5 * rows + 0.5 * near * land              # ...but the sky stays far, however dark
    near = (near - near.min()) / max(1e-6, near.max() - near.min())
    out = Image.fromarray((near * 255).astype(np.uint8))
    out = out.filter(ImageFilter.GaussianBlur(10))
    return ImageOps.autocontrast(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="art-inbox")
    ap.add_argument("--out", default="public/art")
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    done = []
    for region in REGIONS:
        found = [p for ext in ("png", "jpg", "jpeg", "webp") for p in src.glob(f"{region}.{ext}")]
        if not found:
            continue
        img = Image.open(found[0]).convert("RGB")
        wide = img.resize((2560, round(2560 * img.height / img.width)), Image.LANCZOS)
        wide.save(out / f"{region}.webp", quality=84, method=6)

        # Phone crop: full height, 9:16 slice centred on the focal point
        h = img.height
        w = round(h * 9 / 16)
        cx = round(img.width * FOCUS_X.get(region, 0.55))
        left = max(0, min(img.width - w, cx - w // 2))
        img.crop((left, 0, left + w, h)).resize((1080, 1920), Image.LANCZOS).save(
            out / f"{region}-m.webp", quality=82, method=6)

        depth_map(img).save(out / f"{region}-depth.webp", quality=90)
        done.append(region)

    print(f"processed {len(done)}: {', '.join(done) or 'none'} -> {out}")


if __name__ == "__main__":
    main()
