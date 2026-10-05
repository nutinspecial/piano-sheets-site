"""
apply_audio_renames.py
──────────────────────
Applies the decisions exported from match-review (Downloads/rename_decisions.json).

  python apply_audio_renames.py                  # preview
  python apply_audio_renames.py --apply          # rename, write an undo log
  python apply_audio_renames.py --apply --fix-playlist
                                                 # also correct titles in tracks.json
  python apply_audio_renames.py --undo <log.csv>

Renames ticked files in ~/Downloads/Youtube/Audio to "<Official Title>.<ext>",
numbering further takes "(take 2)". Lists every playlist entry whose title
disagrees with the confirmed one; --fix-playlist corrects those titles (the R2
file names are left as they are, so nothing on the site breaks).
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from standardize_audio_names import FOLDER, original_ids, safe  # noqa: E402
from version_rules import is_compilation, is_working_file, mp3_twins, pick_finished, to_recycle_bin  # noqa: E402

DECISIONS = Path.home() / "Downloads" / "rename_decisions.json"
TRACKS_PATH = ROOT / "src" / "data" / "tracks.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--fix-playlist", action="store_true")
    ap.add_argument("--decisions", default=str(DECISIONS))
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

    decisions = [d for d in json.loads(Path(a.decisions).read_text(encoding="utf-8")) if d.get("title")]
    # Shorter official names where the video title carries extra words
    TIDY = {"Pilot's Rest / Romaritime Recollection - Fontaine Happy Day Theme": "Romaritime Recollection",
            "A Happy Furina Que le vent soit doux": "Que le vent soit doux"}
    for d in decisions:
        d["title"] = TIDY.get(d["title"], d["title"])
        if "que le vent soit doux" in d["title"].lower():
            d["title"] = "Que le vent soit doux"
    # Same house rules as the review page, enforced whatever was ticked
    held = []
    twins = mp3_twins(FOLDER)
    twin_names = {p.name for p in twins}
    decisions = [d for d in decisions if d["file"] not in twin_names]
    for d in [d for d in decisions if is_working_file(d["file"], d["title"])]:
        held.append(f'{d["file"]} (working file)'); decisions.remove(d)
    matched = {x["file"]: x for x in json.loads((ROOT / "match_results.json").read_text(encoding="utf-8"))}
    for d in list(decisions):
        x = matched.get(d["file"])
        if x and x["candidates"] and is_compilation(x["secs"], x["candidates"][0]["dur"]):
            held.append(f'{d["file"]} (compilation or loop)'); decisions.remove(d)
    by_title: dict[str, list] = {}
    for d in decisions:
        by_title.setdefault(d["title"].lower(), []).append(d)
    for ds in by_title.values():
        if len(ds) > 1:
            keep = pick_finished([FOLDER / d["file"] for d in ds]).name
            for d in ds:
                if d["file"] != keep:
                    held.append(f'{d["file"]} (older version; {keep} is the finished one)'); decisions.remove(d)
    ids = {p.name: i for p, i in original_ids().items() if p.parent == FOLDER}
    tracks = json.loads(TRACKS_PATH.read_text(encoding="utf-8"))
    by_id = {t["id"]: t for t in tracks}

    # Plan names, numbering repeat takes of the same piece
    existing = {p.name.lower() for p in FOLDER.iterdir()}
    used: dict[str, int] = {}
    plan = []
    for d in sorted(decisions, key=lambda d: d["file"].lower()):
        ext = Path(d["file"]).suffix.lower()
        base = safe(d["title"])
        n = used.get(base.lower(), 0) + 1
        name = f"{base}{ext}" if n == 1 else f"{base} (take {n}){ext}"
        while name.lower() in existing and name.lower() != d["file"].lower():
            n += 1
            name = f"{base} (take {n}){ext}"
        used[base.lower()] = n
        existing.add(name.lower())
        plan.append({"old": d["file"], "new": name, "title": d["title"]})

    fixes = []
    for p in plan:
        t = by_id.get(ids.get(p["old"], ""))
        if t and t["title"] != p["title"]:
            fixes.append((t, p["title"]))

    changes = [p for p in plan if p["old"] != p["new"]]
    for h in held:
        print(f"  left as is: {h}")
    for t in twins:
        print(f"  to Recycle Bin (WAV of the same name kept): {t.name}")
    print(f"{len(changes)} files to rename; {len(fixes)} playlist titles disagree")
    for p in changes[:400]:
        print(f"  {p['old']}  ->  {p['new']}")
    for t, new in fixes:
        print(f"  playlist: \"{t['title']}\" -> \"{new}\"  ({t['filename']})")
    if not a.apply:
        print("(preview only; add --apply)")
        return

    log = FOLDER / f"rename_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
    done = []
    for p in changes:
        src, dst = FOLDER / p["old"], FOLDER / p["new"]
        if src.exists() and not dst.exists():
            src.rename(dst)
            done.append(p)
    for t in twins:
        if t.exists():
            to_recycle_bin(t)
    print(f"sent {len(twins)} MP3 copies to the Recycle Bin")
    with open(log, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["old", "new", "title"]); w.writeheader(); w.writerows(done)
    print(f"renamed {len(done)}; undo: python apply_audio_renames.py --undo \"{log}\"")

    if a.fix_playlist and fixes:
        for t, new in fixes:
            t["title"] = new
        TRACKS_PATH.write_text(json.dumps(tracks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"tracks.json: corrected {len(fixes)} titles")


if __name__ == "__main__":
    main()
