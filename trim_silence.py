"""
Trims leading/trailing silence >=5s (down to a 0.3s natural buffer) from the
files flagged by audio_qa_check.py, in place in r2-upload/, and updates
src/data/tracks.json durations to match.

Reads audio_qa_report.csv (must be current — re-run audio_qa_check.py first
if r2-upload/ has changed) to decide which files and how much to cut.

After running, re-upload each changed file:
    wrangler r2 object put bigpianosmallpiano-audio/<file> --file=r2-upload/<file> --remote

Usage:
    python trim_silence.py
"""

import csv
import json
import subprocess
from pathlib import Path

REPORT_CSV = Path(__file__).parent / "audio_qa_report.csv"
R2_UPLOAD_DIR = Path(__file__).parent / "r2-upload"
TRACKS_JSON = Path(__file__).parent / "src" / "data" / "tracks.json"

TRIM_THRESHOLD_SEC = 5.0   # only trim ends with at least this much detected silence
KEEP_BUFFER_SEC = 0.3      # leave this much natural pre/post-roll


def trim_file(path: Path, start_trim: float, new_duration: float) -> None:
    tmp = path.with_suffix(".trimmed" + path.suffix)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if start_trim > 0:
        cmd += ["-ss", f"{start_trim:.3f}"]
    cmd += ["-i", str(path), "-t", f"{new_duration:.3f}", "-c", "copy", str(tmp)]
    subprocess.run(cmd, check=True)
    tmp.replace(path)


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def main():
    rows = list(csv.DictReader(REPORT_CSV.open(encoding="utf-8")))
    to_trim = []
    for r in rows:
        lead = float(r["leading_silence"])
        trail = float(r["trailing_silence"])
        if lead >= TRIM_THRESHOLD_SEC or trail >= TRIM_THRESHOLD_SEC:
            to_trim.append((r["filename"], lead, trail, float(r["duration"])))

    print(f"{len(to_trim)} files to trim")

    tracks = json.loads(TRACKS_JSON.read_text(encoding="utf-8"))
    by_filename = {t["filename"]: t for t in tracks}

    for filename, lead, trail, orig_duration in to_trim:
        path = R2_UPLOAD_DIR / filename
        if not path.exists():
            print(f"  SKIP (missing): {filename}")
            continue

        start_trim = max(0.0, lead - KEEP_BUFFER_SEC) if lead >= TRIM_THRESHOLD_SEC else 0.0
        end_cut = max(0.0, trail - KEEP_BUFFER_SEC) if trail >= TRIM_THRESHOLD_SEC else 0.0
        new_duration = orig_duration - start_trim - end_cut

        trim_file(path, start_trim, new_duration)
        actual_duration = round(probe_duration(path))

        if filename in by_filename:
            by_filename[filename]["duration"] = actual_duration

        print(f"  {filename:<45} {orig_duration:.1f}s -> {actual_duration}s "
              f"(cut {start_trim:.1f}s lead / {end_cut:.1f}s tail)")

    TRACKS_JSON.write_text(json.dumps(tracks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nUpdated durations in {TRACKS_JSON}")


if __name__ == "__main__":
    main()
