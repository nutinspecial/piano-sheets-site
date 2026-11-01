"""
sync_audio_names.py
───────────────────
Keeps the recordings in ~/Downloads/Youtube/Audio named after their site titles.

Matches by sound, not by name: each file is compared with every track in
src/data/tracks.json of a similar length. Only a score of 0.97 or more renames
a file. tracks.json is the source of truth. Several files for one title: the
closest match gets the plain name, the rest get " (take 2)", " (take 3)".
A file with no match is left alone.

  python sync_audio_names.py                  # scan, writes audio_sync_plan.csv
  python sync_audio_names.py --apply          # rename from that plan, writes an undo log
  python sync_audio_names.py --undo <log.csv>

Run it after a site title changes, or after new exports land in the folder.
"""

import argparse
import csv
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
FOLDER = Path.home() / "Downloads" / "Youtube" / "Audio"
TRACKS = ROOT / "src" / "data" / "tracks.json"
PLAN = ROOT / "audio_sync_plan.csv"
CACHE = ROOT / ".match-cache" / "site-tracks"
CERTAIN = 0.97
WINDOW = 30            # seconds of length difference worth comparing
LONGEST = 600          # compilations and loops are skipped
SHORTEST = 20
AUDIO = (".mp3", ".wav", ".m4a")


def load(path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         stdin=subprocess.DEVNULL, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(float) / 32768


def features(a: np.ndarray, hop=8000, width=8192) -> np.ndarray:
    frames = []
    for i in range(0, len(a) - width, hop):
        s = np.log1p(np.abs(np.fft.rfft(a[i:i + width] * np.hanning(width)))[20:1200] * 10)
        frames.append(s / (np.linalg.norm(s) + 1e-9))
    return np.array(frames)


def flat(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def safe(title: str) -> str:
    return re.sub(r'[<>:"/\|?*]', "-", title.replace(" / ", " - ")).strip()


def scan() -> None:
    tracks = json.loads(TRACKS.read_text(encoding="utf-8"))
    CACHE.mkdir(parents=True, exist_ok=True)
    site = []
    for t in tracks:
        p = CACHE / t["filename"]
        if not p.exists():
            subprocess.run(["curl", "-s", "-o", str(p), t["url"]], stdin=subprocess.DEVNULL)
        f = features(load(p))
        if f.size:
            site.append((t, f))
    rows = []
    for path in sorted(p for p in FOLDER.iterdir() if p.suffix.lower() in AUDIO):
        f = features(load(path))
        secs = len(f)
        if not SHORTEST <= secs <= LONGEST:
            rows.append([path.name, secs, "skip", "", ""])
            continue
        scored = [(float(np.median((f @ g.T).max(axis=1))), t) for t, g in site if abs(len(g) - secs) <= WINDOW]
        score, best = max(scored, key=lambda x: x[0], default=(0, None))
        if score < CERTAIN:
            rows.append([path.name, secs, "nomatch", best["title"] if best else "", round(score, 3)])
        else:
            same = flat(path.stem) == flat(safe(best["title"]))
            rows.append([path.name, secs, "same" if same else "rename", best["title"], round(score, 3)])
    with PLAN.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    print(Counter(r[2] for r in rows))
    print(f"Plan written to {PLAN.name}. Check it, then run with --apply.")


def apply() -> None:
    rows = list(csv.reader(PLAN.open(encoding="utf-8")))
    keep = {flat(Path(r[0]).stem) for r in rows if r[2] != "rename"}     # names already in use
    todo = sorted((r for r in rows if r[2] == "rename"),
                  key=lambda r: (r[3], -float(r[4]), not r[0].lower().endswith(".wav")))
    used: Counter = Counter()
    log = FOLDER / f"rename_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with log.open("w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh)
        out.writerow(["old", "new"])
        for old, _, _, title, _ in todo:
            src = FOLDER / old
            if not src.exists():
                print(f"  missing, skipped: {old}")
                continue
            stem, n = safe(title), used[safe(title)]
            n += 1
            while True:
                name = stem if n == 1 else f"{stem} (take {n})"
                if flat(name) not in keep and not (FOLDER / f"{name}{src.suffix.lower()}").exists():
                    break
                n += 1
            used[stem] = n
            keep.add(flat(name))
            dst = FOLDER / f"{name}{src.suffix.lower()}"
            os.rename(src, dst)
            out.writerow([old, dst.name])
            print(f"  {old} -> {dst.name}")
    print(f"Undo log: {log}")


def undo(path: str) -> None:
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if (FOLDER / r["new"]).exists() and not (FOLDER / r["old"]).exists():
            os.rename(FOLDER / r["new"], FOLDER / r["old"])
    print("Undone.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--undo")
    a = ap.parse_args()
    undo(a.undo) if a.undo else apply() if a.apply else scan()
