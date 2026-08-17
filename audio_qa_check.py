"""
QA pass over r2-upload/*.{mp3,wav} — the exact files staged for/uploaded to R2.

For each file, runs a single ffmpeg pass combining:
  - silencedetect (finds leading/trailing silence that should have been trimmed)
  - volumedetect   (finds near-silent/broken exports and outlier loudness)

Also flags filenames that look like test/junk exports rather than real titles.

Does NOT verify song identity/content correctness — that needs a human ear.
Writes a CSV report (audio_qa_report.csv, gitignored) and prints a
flagged-only summary to stdout.

Requires ffmpeg/ffprobe on PATH.

Usage:
    python generate_tracks_manifest.py   # if source folders changed
    python audio_qa_check.py
    python trim_silence.py               # trims files still flagged with >=5s silence
    # then re-upload any changed files with: wrangler r2 object put ... --remote
"""

import csv
import re
import subprocess
from pathlib import Path

SRC_DIR = Path(__file__).parent / "r2-upload"
OUT_CSV = Path(__file__).parent / "audio_qa_report.csv"

SILENCE_NOISE_DB = "-35dB"
SILENCE_MIN_DUR = "0.3"

LEADING_SILENCE_FLAG_SEC = 4.0   # most tracks have ~0.5-3s natural pre-roll; flag real outliers only
TRAILING_SILENCE_FLAG_SEC = 1.5  # untrimmed tail worth flagging
QUIET_MEAN_DB_FLAG = -40         # whole-file mean_volume below this = suspiciously quiet/broken
SHORT_DURATION_FLAG_SEC = 25     # likely a broken/test export, not a real cover

SUSPICIOUS_NAME_RE = re.compile(
    r"^(test|untitled|untitl\d*ed|track|track-\d+|video-\d.*|voice-.*|compilation)$",
    re.IGNORECASE,
)

SILENCE_START_RE = re.compile(r"silence_start:\s*([\-\d.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*([\-\d.]+)\s*\|\s*silence_duration:\s*([\-\d.]+)")
MEAN_VOL_RE = re.compile(r"mean_volume:\s*([\-\d.]+)\s*dB")
MAX_VOL_RE = re.compile(r"max_volume:\s*([\-\d.]+)\s*dB")
DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):([\d.]+)")


def analyze(path: Path) -> dict:
    cmd = [
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-af", f"silencedetect=noise={SILENCE_NOISE_DB}:d={SILENCE_MIN_DUR},volumedetect",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = proc.stderr

    dur_m = DURATION_RE.search(log)
    duration = 0.0
    if dur_m:
        h, m, s = dur_m.groups()
        duration = int(h) * 3600 + int(m) * 60 + float(s)

    starts = [float(x) for x in SILENCE_START_RE.findall(log)]
    # (silence_end_time, silence_duration) — ffmpeg emits a matching end even
    # when the silence runs to EOF, so start/end pairs are positional.
    ends = [(float(a), float(b)) for a, b in SILENCE_END_RE.findall(log)]
    pairs = list(zip(starts, [e for e, _ in ends]))

    leading_silence = 0.0
    if pairs and pairs[0][0] < 0.05:
        leading_silence = ends[0][1]

    trailing_silence = 0.0
    if pairs and duration > 0 and pairs[-1][1] >= duration - 0.05:
        # skip if this is the same block already counted as leading (very short file)
        if not (pairs[-1][0] < 0.05):
            trailing_silence = ends[-1][1]

    mean_m = MEAN_VOL_RE.search(log)
    max_m = MAX_VOL_RE.search(log)
    mean_vol = float(mean_m.group(1)) if mean_m else None
    max_vol = float(max_m.group(1)) if max_m else None

    return {
        "duration": round(duration, 2),
        "leading_silence": round(leading_silence, 2),
        "trailing_silence": round(trailing_silence, 2),
        "mean_volume_db": mean_vol,
        "max_volume_db": max_vol,
    }


def main():
    files = sorted(
        p for p in SRC_DIR.iterdir()
        if p.suffix.lower() in {".mp3", ".wav"}
    )
    print(f"Analyzing {len(files)} files...")

    rows = []
    for i, f in enumerate(files, 1):
        stats = analyze(f)
        stem = f.stem
        name_suspicious = bool(SUSPICIOUS_NAME_RE.match(stem))

        flags = []
        if name_suspicious:
            flags.append("suspicious-name")
        if stats["leading_silence"] >= LEADING_SILENCE_FLAG_SEC:
            flags.append(f"leading-silence({stats['leading_silence']}s)")
        if stats["trailing_silence"] >= TRAILING_SILENCE_FLAG_SEC:
            flags.append(f"trailing-silence({stats['trailing_silence']}s)")
        if stats["mean_volume_db"] is not None and stats["mean_volume_db"] <= QUIET_MEAN_DB_FLAG:
            flags.append(f"very-quiet({stats['mean_volume_db']}dB)")
        if stats["duration"] <= SHORT_DURATION_FLAG_SEC:
            flags.append(f"very-short({stats['duration']}s)")

        row = {"filename": f.name, **stats, "flags": ";".join(flags)}
        rows.append(row)

        if i % 25 == 0 or i == len(files):
            print(f"  [{i}/{len(files)}]")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    flagged = [r for r in rows if r["flags"]]
    print(f"\nWrote full report to {OUT_CSV}")
    print(f"{len(flagged)}/{len(rows)} files flagged for review:\n")
    for r in flagged:
        print(f"  {r['filename']:<45} {r['flags']}")


if __name__ == "__main__":
    main()
