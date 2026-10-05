"""
publish_track.py
────────────────
One command from a finished WAV to a track playing on the site.

  python publish_track.py "path/to/take.wav" --region Snezhnaya
  python publish_track.py "take.wav" --region Snezhnaya --title "I Loved You"
  python publish_track.py "take.wav" --region Snezhnaya --dry-run   # process only

Steps:
  1. Name      If --title is missing, suggests the official name from the YouTube
               upload in src/data/videos.json whose length is closest; asks to confirm.
  2. Trim      Silence at the start and end, down to 0.3 s.
  3. Level     Two-pass loudness normalisation to -16 LUFS, true peak -1.5 dB, so
               every track on the site plays at the same volume.
  4. Encode    MP3 192 kb/s, named <slug(title)>-<compactregion>.mp3 (site convention),
               plus a 20 s preview clip for hover previews.
  5. Envelope  public/envelopes/<stem>.txt for the music-reactive visuals.
  6. Upload    Both MP3s to the R2 bucket with wrangler (skipped with --dry-run).
  7. Playlist  Adds or updates the entry in src/data/tracks.json.

Commit and push afterwards to deploy (or pass --push).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TRACKS = ROOT / "src" / "data" / "tracks.json"
VIDEOS = ROOT / "src" / "data" / "videos.json"
STAGE = ROOT / "r2-upload"
ENVELOPES = ROOT / "public" / "envelopes"
BUCKET = "bigpianosmallpiano-audio"
R2_BASE = "https://pub-9ea7a49f5df1482d8170a302c30ae134.r2.dev"

sys.path.insert(0, str(ROOT))
from generate_envelopes import envelope  # noqa: E402


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.stdout.strip())


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("'", "").replace("’", "")).strip("-")


def official_title(seconds: float) -> str:
    """The quoted name of the YouTube upload closest in length."""
    def secs(iso):
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
        return int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0) if m else 0
    videos = json.loads(VIDEOS.read_text(encoding="utf-8"))
    ranked = sorted(videos, key=lambda v: abs(secs(v.get("duration")) - seconds))[:3]
    print("  Closest uploads by length:")
    for v in ranked:
        print(f"    {secs(v.get('duration')):>4}s  {v['title']}")
    top = ranked[0]["title"].replace("‘", "'").replace("’", "'")
    m = re.search(r"'(.+?)'(?![\w])", top)
    return (m[1] if m else top.split("|")[0]).strip()


def process(src: Path, out: Path, preview: Path) -> None:
    trim = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.3,"
            "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.3,areverse")
    # Pass 1: measure loudness after trimming
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af",
                            f"{trim},loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    start = probe.stderr.rindex("{")
    stats = json.loads(probe.stderr[start:probe.stderr.index("}", start) + 1])
    norm = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
            f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
            f"offset={stats['target_offset']}:linear=true")
    # Pass 2: trim, level, encode
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", f"{trim},{norm}",
         "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", str(out)])
    # Preview: 20 s from a quarter of the way in, with soft fades
    total = duration(out)
    start = max(0.0, min(total * 0.25, total - 20))
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", "20", "-i", str(out),
         "-af", "afade=t=in:d=1.5,afade=t=out:st=17.5:d=2.5", "-c:a", "libmp3lame", "-b:a", "128k", str(preview)])


def upload(path: Path) -> None:
    run(["npx", "wrangler", "r2", "object", "put", f"{BUCKET}/{path.name}", f"--file={path}",
         "--remote", "--content-type=audio/mpeg"], cwd=ROOT, shell=(sys.platform == "win32"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--region", required=True, help='category, e.g. "Snezhnaya" or "Nod Krai"')
    ap.add_argument("--title")
    ap.add_argument("--yes", action="store_true", help="accept the suggested title")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    src = Path(a.wav)
    secs = duration(src)
    title = a.title
    if not title:
        title = official_title(secs)
        if not a.yes and input(f'  Use "{title}"? [Y/n] ').strip().lower() == "n":
            title = input("  Official title: ").strip()

    compact = re.sub(r"[^a-z0-9]", "", a.region.lower())
    name = f"{slug(title)}-{compact}"
    STAGE.mkdir(exist_ok=True)
    out, preview = STAGE / f"{name}.mp3", STAGE / f"{name}-preview.mp3"
    print(f'  {src.name} -> {out.name} ("{title}", {a.region})')

    process(src, out, preview)
    ENVELOPES.mkdir(parents=True, exist_ok=True)
    (ENVELOPES / f"{name}.txt").write_text(envelope(out), encoding="ascii")

    if not a.dry_run:
        upload(out)
        upload(preview)
        print("  uploaded to R2")

    tracks = json.loads(TRACKS.read_text(encoding="utf-8"))
    entry = {"id": name, "title": title, "category": a.region, "filename": out.name,
             "duration": round(duration(out)), "url": f"{R2_BASE}/{out.name}",
             "preview": f"{R2_BASE}/{preview.name}"}
    tracks = [t for t in tracks if t.get("filename") != out.name] + [entry]
    if not a.dry_run:
        TRACKS.write_text(json.dumps(tracks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  tracks.json: {len(tracks)} tracks")
    else:
        print(f"  (dry run) would add: {json.dumps(entry, ensure_ascii=False)}")

    if a.push and not a.dry_run:
        run(["git", "add", str(TRACKS), str(ENVELOPES / f"{name}.txt")], cwd=ROOT)
        run(["git", "commit", "-m", f"Add {title} ({a.region}) to the playlist"], cwd=ROOT)
        run(["git", "push"], cwd=ROOT)
        print("  pushed; the site redeploys in a few minutes")


if __name__ == "__main__":
    main()
