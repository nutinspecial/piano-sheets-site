"""
match_audio.py
──────────────
Matches every recording in ~/Downloads/Youtube/Audio to the YouTube upload it
was released as, by comparing the music itself (which notes sound when), not
the file name or length.

  python match_audio.py --refs <folder with YouTube audio + refs.json>

refs.json lists {id, title, dur} for each upload; the audio files in that
folder are named <id>.<ext> (yt-dlp -o "%(id)s.%(ext)s").

Writes match_results.json: for each local file, the top three uploads with a
similarity score (1.0 = identical), the official title of the best one, and a
confidence label. Fingerprints are cached in .match-cache/ so re-runs are quick.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
LOCAL = Path.home() / "Downloads" / "Youtube" / "Audio"
CACHE = ROOT / ".match-cache"
SR, WIN, HOP = 4000, 2048, 2000            # 0.5 s frames
AUDIO = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".opus", ".ogg"}


def fingerprint(path: Path) -> np.ndarray:
    """Chroma: for each half second, how much of each of the 12 pitch classes sounds."""
    key = hashlib.md5(f"{path}|{path.stat().st_mtime}|{path.stat().st_size}".encode()).hexdigest()
    cached = CACHE / f"{key}.npy"
    if cached.exists():
        return np.load(cached)
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype=np.int16).astype(np.float32)
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    ok = (freqs > 55) & (freqs < 1800)
    pc = (np.round(12 * np.log2(freqs[ok] / 440)) % 12).astype(int)
    win = np.hanning(WIN).astype(np.float32)
    frames = []
    for i in range(0, max(0, len(x) - WIN), HOP):
        mag = np.abs(np.fft.rfft(x[i:i + WIN] * win))[ok]
        frames.append(np.bincount(pc, weights=mag, minlength=12))
    c = np.array(frames, dtype=np.float32) if frames else np.zeros((1, 12), np.float32)
    loud = c.sum(1) > np.percentile(c.sum(1), 15)          # ignore near-silent frames
    c = c / (np.linalg.norm(c, axis=1, keepdims=True) + 1e-9)
    c[~loud] = 0
    CACHE.mkdir(exist_ok=True)
    np.save(cached, c.astype(np.float16))
    return c


def similarity(a: np.ndarray, b: np.ndarray, max_lag: int = 80) -> float:
    """Best average frame-by-frame agreement over time offsets of up to +-40 s."""
    a = a.astype(np.float32); b = b.astype(np.float32)
    best = 0.0
    for lag in range(-max_lag, max_lag + 1):
        A, B = (a[lag:], b) if lag >= 0 else (a, b[-lag:])
        n = min(len(A), len(B))
        if n < 30:
            continue
        dots = np.sum(A[:n] * B[:n], axis=1)
        live = (np.abs(A[:n]).sum(1) > 0) & (np.abs(B[:n]).sum(1) > 0)
        if live.sum() < 30:
            continue
        best = max(best, float(dots[live].mean()))
    return best


def official_title(video_title: str) -> str:
    t = video_title.replace("‘", "'").replace("’", "'").split("|")[0]
    t = re.sub(r"^\s*(?:genshin|movie|studio ghibli)\s+ost:\s*", "", t, flags=re.I)
    m = re.search(r"'(.+?)'(?![\w])", t)
    if m:
        return m[1].strip()
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"\s+[-–]\s+[^-–]*\b(?:OST|BGM|Theme Song)\b.*$", "", t, flags=re.I)
    return re.sub(r"\s{2,}", " ", t).strip(" -–:")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", required=True)
    ap.add_argument("--top", type=int, default=24, help="uploads checked in detail per file")
    a = ap.parse_args()
    refdir = Path(a.refs)
    meta = {r["id"]: r for r in json.loads((refdir / "refs.json").read_text(encoding="utf-8"))}

    refs = {}
    for p in refdir.iterdir():
        if p.suffix.lower() in AUDIO and p.stem in meta:
            refs[p.stem] = fingerprint(p)
    print(f"{len(refs)} upload fingerprints")
    ref_ids = list(refs)
    ref_profile = np.array([refs[i].astype(np.float32).mean(0) for i in ref_ids])
    ref_profile /= np.linalg.norm(ref_profile, axis=1, keepdims=True) + 1e-9

    local = sorted(p for p in LOCAL.iterdir() if p.suffix.lower() in AUDIO)
    results = []
    for k, path in enumerate(local, 1):
        fp = fingerprint(path)
        secs = len(fp) * HOP / SR
        prof = fp.astype(np.float32).mean(0); prof /= np.linalg.norm(prof) + 1e-9
        # Shortlist by overall pitch profile (key and harmony), then compare in time
        shortlist = [ref_ids[i] for i in np.argsort(-(ref_profile @ prof))[: a.top]]
        scored = sorted(((similarity(fp, refs[r]), r) for r in shortlist), reverse=True)[:3]
        top = [{"id": r, "score": round(s, 3), "title": official_title(meta[r]["title"]),
                "video": meta[r]["title"], "dur": meta[r]["dur"]} for s, r in scored]
        s1 = top[0]["score"] if top else 0
        margin = s1 - (top[1]["score"] if len(top) > 1 else 0)
        conf = "high" if s1 >= 0.9 and margin >= 0.08 else "medium" if s1 >= 0.8 and margin >= 0.04 else "low"
        results.append({"file": path.name, "secs": round(secs), "confidence": conf, "candidates": top})
        if k % 25 == 0:
            print(f"  {k}/{len(local)}")
    (ROOT / "match_results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = {c: sum(r["confidence"] == c for r in results) for c in ("high", "medium", "low")}
    print(f"{len(results)} files: {counts}")


if __name__ == "__main__":
    main()
