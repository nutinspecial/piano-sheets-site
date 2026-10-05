"""
generate_envelopes.py
─────────────────────
Writes a loudness envelope for every playlist track so the home page can make
its strings and gold leaf move with the real recording, without needing CORS
access to the audio on R2.

Each envelope is one line of base-36 digits (0-z), one digit per 1/20 s,
scaled so the loudest moment of that track is "z". Output goes to
public/envelopes/<filename-stem>.txt.

Reads the local staged copies in r2-upload/ (see generate_tracks_manifest.py).
Tracks without a local copy are skipped; the page simply leaves those still.

Usage:  python generate_envelopes.py           (skips envelopes that exist)
        python generate_envelopes.py --force   (rebuilds all)
"""

import json
import subprocess
import sys
from array import array
from pathlib import Path

ROOT      = Path(__file__).parent
TRACKS    = ROOT / "src" / "data" / "tracks.json"
SOURCE    = ROOT / "r2-upload"
OUT       = ROOT / "public" / "envelopes"
RATE      = 2000          # decode sample rate (Hz); plenty for a loudness curve
STEP      = RATE // 20    # samples per envelope frame (20 frames per second)
DIGITS    = "0123456789abcdefghijklmnopqrstuvwxyz"


def envelope(path: Path) -> str:
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE),
         "-f", "s16le", "-"],
        check=True, capture_output=True,
    ).stdout
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])

    frames = []
    for i in range(0, len(samples), STEP):
        chunk = samples[i : i + STEP]
        if not chunk:
            break
        frames.append((sum(s * s for s in chunk) / len(chunk)) ** 0.5)

    peak = max(frames) or 1.0
    return "".join(DIGITS[min(35, round(f / peak * 35))] for f in frames)


def main() -> None:
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    tracks = json.loads(TRACKS.read_text(encoding="utf-8"))

    made = skipped = missing = 0
    for t in tracks:
        src = SOURCE / t["filename"]
        dst = OUT / (Path(t["filename"]).stem + ".txt")
        if dst.exists() and not force:
            skipped += 1
            continue
        if not src.exists():
            missing += 1
            continue
        dst.write_text(envelope(src), encoding="ascii")
        made += 1

    print(f"{made} written, {skipped} already there, {missing} with no local copy")


if __name__ == "__main__":
    main()
