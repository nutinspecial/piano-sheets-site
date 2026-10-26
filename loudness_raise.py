"""Raise quiet tracks with plain gain: toward -16 LUFS, capped so true peak stays <= -1 dBTP."""
import csv, sys, subprocess, pathlib, re, shutil
site, work = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
backup = site / "r2-upload/loudness-backup-2026-10-26"; out = work / "louder"
backup.mkdir(parents=True, exist_ok=True); out.mkdir(exist_ok=True)
def measure(f):
    s = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(f), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    s = s[s.rfind("Summary:"):]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1)), float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1))
log = []
for x in csv.DictReader(open(work / "loudness.csv", encoding="utf-8")):
    lufs, tp = float(x["lufs"]), float(x["tp"])
    g = min(-16 - lufs, -1 - tp)
    if g < 1: continue
    src = work / "audio" / x["filename"]; dst = out / x["filename"]
    shutil.copy2(src, backup / x["filename"])
    for attempt in range(3):   # MP3 encoding can add a few tenths of overshoot; back off if so
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", f"volume={g:.2f}dB",
                        "-c:a", "libmp3lame", "-b:a", "320k", "-map_metadata", "0", str(dst)], check=True)
        nl, ntp = measure(dst)
        if ntp <= -0.8: break
        g -= ntp + 1
    log.append((x["title"], x["filename"], lufs, tp, g, nl, ntp))
    print(f"{x['title'][:40]:40} {lufs:6.1f} -> {nl:6.1f} LUFS  peak {tp:5.1f} -> {ntp:5.1f}  (+{g:.1f} dB)")
with open(work / "applied.csv", "w", newline="", encoding="utf-8") as fh:
    csv.writer(fh).writerows([("title","filename","lufs_before","tp_before","gain","lufs_after","tp_after"), *log])
