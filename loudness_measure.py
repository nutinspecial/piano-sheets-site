"""Download every live track and measure integrated loudness + true peak."""
# Usage: python loudness_measure.py . <workdir>, then python loudness_raise.py . <workdir>,
# then wrangler-upload <workdir>/louder/* under the same keys. Originals go to r2-upload/loudness-backup-<date>.
import json, subprocess, sys, re, csv, pathlib
from concurrent.futures import ThreadPoolExecutor
site, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
tracks = json.loads((site / "src/data/tracks.json").read_text(encoding="utf-8"))
def one(t):
    f = out / "audio" / t["filename"]
    if not f.exists():
        subprocess.run(["curl", "-s", "-o", str(f), t["url"]], check=True)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(f), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    s = r[r.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1)); tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1))
    return {"id": t["id"], "title": t["title"], "category": t["category"], "filename": t["filename"], "lufs": i, "tp": tp}
with ThreadPoolExecutor(6) as ex: rows = list(ex.map(one, tracks))
with open(out / "loudness.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
print(len(rows), "measured")
