"""
standardize_audio_names.py
──────────────────────────
Renames the recordings in ~/Downloads/Youtube/Audio to their official titles.

How a file is matched (most certain first):
  playlist   The file's original playlist id (rebuilt exactly the way
             generate_tracks_manifest.py made it) points at a curated, region-
             tagged entry in src/data/tracks.json, and the lengths agree. Renamed.
  tidy       Same, but the entry was never curated ("Uncategorized"), so the name
             is only tidied ("adeptus piano edited" -> "Adeptus Piano"). Renamed.
  suggested  No playlist entry, but the name closely resembles an official title
             from the channel. Only renamed with --include-suggested.
  leave      Quarantined, ambiguous, or unknown. Never touched.

New names are "<Official Title>.<ext>"; a second take of the same title gets
" (take 2)". Characters Windows forbids are replaced.

Usage:
  python standardize_audio_names.py                 # preview only, writes rename_plan.csv
  python standardize_audio_names.py --apply         # rename; writes an undo log in the folder
  python standardize_audio_names.py --undo <log.csv>

Note: generate_tracks_manifest.py builds ids from these file names, so do not
re-run it after renaming (it would treat every file as new). Publish new
recordings with publish_track.py instead.
"""

import argparse
import csv
import difflib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from generate_tracks_manifest import SOURCES, AUDIO_EXTS, clean_title, slugify, unique_id  # noqa: E402

FOLDER = Path.home() / "Downloads" / "Youtube" / "Audio"
TRACKS = json.loads((ROOT / "src" / "data" / "tracks.json").read_text(encoding="utf-8"))
QUARANTINE = json.loads((ROOT / "src" / "data" / "tracks-quarantine.json").read_text(encoding="utf-8"))
VIDEOS = json.loads((ROOT / "src" / "data" / "videos.json").read_text(encoding="utf-8"))


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def original_ids() -> dict[Path, str]:
    """Rebuild every file's playlist id in the manifest's own iteration order."""
    seen: dict[str, int] = {}
    ids = {}
    for source_dir, _ in SOURCES:
        if not source_dir.exists():
            continue
        for path in sorted(source_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
                ids[path] = unique_id(slugify(clean_title(path.stem)), seen)
    return ids


def official_names() -> list[str]:
    names = {t["title"] for t in TRACKS if t["category"] != "Uncategorized"}
    for v in VIDEOS:
        t = v["title"].replace("‘", "'").replace("’", "'")
        m = re.search(r"'(.+?)'(?![\w])", t)
        if m:
            names.add(m[1].strip())
    return sorted(names)


def safe(name: str) -> str:
    name = re.sub(r"\s*/\s*", " - ", name)
    name = re.sub(r'[<>:"\\|?*]', "", name)
    return re.sub(r"\s{2,}", " ", name).strip(" .")


def plan() -> list[dict]:
    by_id = {t["id"]: t for t in TRACKS}
    quarantined = {t["id"] for t in QUARANTINE}
    names = official_names()
    lower = {n.lower(): n for n in names}
    ids = original_ids()
    rows = []
    for path in sorted(p for p in FOLDER.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS):
        tid = ids.get(path, "")
        row = {"old": path.name, "new": "", "match": "leave", "why": ""}
        if tid in by_id:
            t = by_id[tid]
            gap = abs(duration(path) - t["duration"])
            if gap <= 25:                                # trims removed at most ~22 s of silence
                curated = t["category"] != "Uncategorized"
                row.update(new=safe(t["title"]) + path.suffix.lower(), match="playlist" if curated else "tidy",
                           why=(f"official title from the playlist ({t['category']})" if curated
                                else "uncurated playlist entry: filename tidied, not an official title"))
            else:
                row["why"] = f"playlist id {tid} but length differs by {gap:.0f}s"
        elif tid in quarantined:
            row["why"] = "in quarantine (no official title yet)"
        else:
            guess = difflib.get_close_matches(clean_title(path.stem).lower(), list(lower), n=1, cutoff=0.72)
            if guess:
                row.update(new=safe(lower[guess[0]]) + path.suffix.lower(), match="suggested",
                           why=f'name resembles "{lower[guess[0]]}"')
            else:
                row["why"] = "no confident match"
        rows.append(row)

    # Already correct, or a second take of the same title
    taken: dict[str, int] = {}
    for r in rows:
        if not r["new"]:
            continue
        if r["new"] == r["old"]:
            r["match"], r["why"] = "ok", "already official"
        key = r["new"].lower()
        taken[key] = taken.get(key, 0) + 1
        if taken[key] > 1:
            stem, ext = r["new"].rsplit(".", 1)
            r["new"] = f"{stem} (take {taken[key]}).{ext}"
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--include-suggested", action="store_true")
    ap.add_argument("--undo")
    a = ap.parse_args()

    if a.undo:
        with open(a.undo, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                src, dst = FOLDER / r["new"], FOLDER / r["old"]
                if src.exists() and not dst.exists():
                    src.rename(dst)
        print("undone")
        return

    rows = plan()
    with open(ROOT / "rename_plan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["old", "new", "match", "why"]); w.writeheader(); w.writerows(rows)
    counts = {k: sum(r["match"] == k for r in rows) for k in ("playlist", "tidy", "suggested", "ok", "leave")}
    print(f"{len(rows)} files: {counts['playlist']} official, {counts['tidy']} tidied, {counts['suggested']} suggested "
          f"(review only), {counts['ok']} already right, {counts['leave']} left alone  (details: rename_plan.csv)")

    if not a.apply:
        return
    todo = [r for r in rows if r["match"] in ("playlist", "tidy") or (a.include_suggested and r["match"] == "suggested")]
    log = FOLDER / f"rename_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
    done = []
    for r in todo:
        src, dst = FOLDER / r["old"], FOLDER / r["new"]
        if dst.exists():
            r["why"] += " (skipped: target exists)"
            continue
        src.rename(dst)
        done.append(r)
    with open(log, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["old", "new", "match", "why"]); w.writeheader(); w.writerows(done)
    print(f"renamed {len(done)}; undo with: python standardize_audio_names.py --undo \"{log}\"")


if __name__ == "__main__":
    main()
