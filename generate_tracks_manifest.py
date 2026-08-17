"""
Scans the local audio source folders, builds src/data/tracks.json for the
Playlist Builder, and copies each track into r2-upload/ (gitignored) under
its clean id.ext name, ready for `wrangler r2 object put`.

Does NOT touch the original files in the source folders.

Usage:
    python generate_tracks_manifest.py

Re-run after setting R2_BASE below to the real Cloudflare R2 public URL,
and any time new tracks are added to the source folders.
"""

import json
import re
import shutil
from pathlib import Path

from mutagen import File as MutagenFile

# ── Config ───────────────────────────────────────────────────────────────

# Set this once the R2 bucket exists and is public (see plan step 2).
R2_BASE = "https://pub-9ea7a49f5df1482d8170a302c30ae134.r2.dev"

HOME = Path.home()

# (source folder, category mode)
#   category mode "subfolder" -> category = immediate parent folder name
#   category mode "flat"      -> category = "Uncategorized"
SOURCES = [
    (HOME / "Downloads" / "Edited MP3s", "subfolder"),
    (HOME / "Downloads" / "Youtube" / "Audio", "flat"),
]

OUTPUT_JSON = Path(__file__).parent / "src" / "data" / "tracks.json"
UPLOAD_DIR = Path(__file__).parent / "r2-upload"

AUDIO_EXTS = {".mp3", ".wav"}

# ── Helpers ──────────────────────────────────────────────────────────────

NOISE_WORDS = re.compile(r"\b(edited|edit|wip|part|new|combined|collated)\b", re.IGNORECASE)


def clean_title(stem: str) -> str:
    title = NOISE_WORDS.sub("", stem)
    title = re.sub(r"[_\-]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" -.,")
    if not title:
        title = stem.strip()
    return " ".join(w if w.isupper() else w.capitalize() for w in title.split(" "))


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "track"


def unique_id(base: str, seen: dict) -> str:
    if base not in seen:
        seen[base] = 1
        return base
    seen[base] += 1
    return f"{base}-{seen[base]}"


def get_duration_seconds(path: Path) -> int:
    try:
        audio = MutagenFile(path)
        if audio is not None and audio.info is not None:
            return round(audio.info.length)
    except Exception:
        pass
    return 0


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    UPLOAD_DIR.mkdir(exist_ok=True)
    seen_ids: dict[str, int] = {}
    tracks = []
    skipped = []

    for source_dir, mode in SOURCES:
        if not source_dir.exists():
            print(f"  (skipping missing folder: {source_dir})")
            continue

        for path in sorted(source_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
                continue

            title = clean_title(path.stem)
            base_id = slugify(title)
            track_id = unique_id(base_id, seen_ids)

            category = path.parent.name if mode == "subfolder" else "Uncategorized"

            duration = get_duration_seconds(path)
            if duration == 0:
                skipped.append(str(path))

            ext = path.suffix.lower()
            dest_filename = f"{track_id}{ext}"
            shutil.copy2(path, UPLOAD_DIR / dest_filename)

            tracks.append({
                "id": track_id,
                "title": title,
                "category": category,
                "filename": dest_filename,
                "duration": duration,
                "url": f"{R2_BASE}/{dest_filename}",
            })

    tracks.sort(key=lambda t: (t["category"], t["title"]))

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(tracks, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {len(tracks)} tracks to {OUTPUT_JSON}")
    print(f"Copied audio files to {UPLOAD_DIR}")
    if skipped:
        print(f"\n{len(skipped)} file(s) had unreadable duration (kept, duration=0):")
        for s in skipped[:10]:
            print(f"  - {s}")
        if len(skipped) > 10:
            print(f"  ... and {len(skipped) - 10} more")
    if R2_BASE.startswith("https://REPLACE"):
        print("\nR2_BASE is still a placeholder — set it once the bucket is public, then re-run.")


if __name__ == "__main__":
    main()
