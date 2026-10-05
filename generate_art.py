"""
generate_art.py
───────────────
Generates the home page region paintings through Pollinations (model
gpt-image-2) into art-inbox/, ready for process_art.py.

Needs a Pollinations secret key in the POLLINATIONS_TOKEN environment variable
(user-level is fine; it is read from the Windows user environment if the
current shell does not have it). The key is never printed.

Usage:
  python generate_art.py                 # every region that has no image yet
  python generate_art.py liyue fontaine  # just these (overwrites)
  python generate_art.py --seed 21 liyue # a different take
"""

import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "art-inbox"
MODEL = "gpt-image-2"

STYLE = (
    "Stylized fantasy landscape wallpaper, 16:9. Layered silhouette composition with strong "
    "atmospheric perspective: the sky is the brightest part and each layer of land gets darker "
    "toward the front, ending in near-black silhouettes along the bottom. Nearly monochrome "
    "{palette} palette with a few tiny warm window lights. {scene} Dramatic stylized curling "
    "clouds with crisp cel-shaded edges. Fine silhouette detail, painterly, elegant, quiet, "
    "cinematic. Keep the left third calm and uncluttered. No people, no characters, no text, "
    "no logo, no watermark."
)

REGIONS = {
    "mondstadt": ("teal and soft green night",
        "Rolling grassy hills with several old wooden windmills with large sails, the nearest one "
        "large and detailed on the right. A walled hilltop city with a tall cathedral spire in the "
        "far distance. Long grass bending in the wind, dandelion seeds floating through the air, "
        "clouds streaming in one direction as if blown by a strong breeze, a thin crescent moon. "
        "A calm lake in the lower third mirrors the hills and windmills."),
    "liyue": ("amber and gold sunset",
        "Towering limestone karst mountains rising from mist like stone pillars, layered far into "
        "the distance, golden sunset light behind them. At their feet a harbour town with curved "
        "tiled rooftops, pagodas, wooden junk boats and many small glowing paper lanterns. A low "
        "golden sun near the horizon. The calm sea in the lower third reflects the mountains and "
        "lantern lights."),
    "inazuma": ("deep violet with pale pink blossoms",
        "An enormous ancient cherry blossom tree in full bloom fills the right side, pale glowing "
        "pink blossoms against a starry violet sky, petals drifting. A Japanese castle town on "
        "rocky islands in the distance. Calm dark water in the lower third mirrors the blossoms "
        "and town lights. No lightning."),
    "sumeru-forest": ("lush green and gold evening",
        "A gigantic ancient tree with a city built into its trunk and branches, glowing windows "
        "among the leaves, surrounded by rainforest canopy and giant mushroom-shaped trees, warm "
        "golden-green evening light, fireflies. The horizon sits about 60 percent down the frame, "
        "with a calm strip of water along the bottom reflecting the light."),
    "sumeru-desert": ("sand gold and amber evening",
        "A vast desert of rolling sand dunes under a warm golden-green evening sky, ancient "
        "pyramid-like ruins and broken stone pillars in the distance, a few warm lights at a small "
        "oasis. The horizon sits about 60 percent down the frame, with a calm strip of oasis water "
        "along the bottom reflecting the light."),
    "fontaine": ("aqua blue and gold, underwater",
        "An underwater view of a sunken city of elegant golden Belle Epoque architecture. A "
        "curving ornate golden aqueduct carries a glowing bright blue stream of water from the "
        "foreground into the distance. Tall ruined towers and arches fade into a hazy sunlit blue "
        "distance. Broad shafts of warm golden sunlight pour down from the surface above. Schools "
        "of small glowing pale violet fish, orange and teal coral and tall swaying sea plants frame "
        "the right side. Dreamy, luminous and calm."),
    "natlan": ("ember red and orange",
        "A great volcano glowing at its peak under a deep ember-red sky, flat-topped mesas and "
        "tall rock spires around it, a village of warm lights at its foot, sparks and embers "
        "drifting upward, swirling smoke-like clouds. Dark water in the lower third reflects the "
        "glow."),
    "nod-krai": ("blue and violet moonlight",
        "A still lake in a northern pine forest under a huge bright full moon, mist drifting over "
        "the water, a small wooden village and a lighthouse with warm windows on the far shore, a "
        "faint aurora in the sky, tall dark pines framing both sides. The moon and its long silver "
        "path reflect on the lake."),
    "snezhnaya": ("deep midnight blue with pale ice-blue highlights, a snowy night",
        "A grand palace city with onion-domed towers on a snowy hill, snow falling softly, a "
        "frozen river and snow-covered fir trees in the foreground, warm lights in a few palace "
        "windows, soft frosty clouds. The frozen river in the lower third faintly reflects the "
        "palace."),
}


def token() -> str:
    tok = os.environ.get("POLLINATIONS_TOKEN", "")
    if not tok and os.name == "nt":
        tok = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Environment]::GetEnvironmentVariable('POLLINATIONS_TOKEN','User')"],
            capture_output=True, text=True).stdout.strip()
    if not tok:
        sys.exit("POLLINATIONS_TOKEN is not set")
    return tok


def generate(region: str, seed: int, tok: str) -> None:
    palette, scene = REGIONS[region]
    prompt = STYLE.format(palette=palette, scene=scene)
    url = (f"https://gen.pollinations.ai/image/{urllib.parse.quote(prompt)}"
           f"?model={MODEL}&width=1920&height=1080&nologo=true&seed={seed}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=400) as res:
        data = res.read()
        if not res.headers.get("Content-Type", "").startswith("image/"):
            raise RuntimeError(data[:300].decode("utf-8", "replace"))
    (OUT / f"{region}.jpg").write_bytes(data)


def main() -> None:
    args = sys.argv[1:]
    seed = 11
    if "--seed" in args:
        i = args.index("--seed"); seed = int(args[i + 1]); del args[i:i + 2]
    names = args or [r for r in REGIONS if not any(OUT.glob(f"{r}.*"))]
    tok = token()
    for r in names:
        t = time.time()
        try:
            generate(r, seed, tok)
            print(f"{r}: ok ({time.time() - t:.0f}s)")
        except Exception as e:                       # keep going; report at the end
            print(f"{r}: FAILED {e}")


if __name__ == "__main__":
    main()
