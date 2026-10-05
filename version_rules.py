"""
version_rules.py
────────────────
The house rules for which recording of a piece is the finished one.

1. Several versions of one piece: the highest version number wins
   ("edited 3" > "edited2" > "edited"; "2nd" counts as 2, "new" as a half
   step up). A tie goes to the most recently saved file.
2. A file much longer than the upload it matches is a compilation or loop that
   contains the piece, not the piece itself, and is never renamed.
3. A WAV and an MP3 with the same name are the same take: keep the WAV; the
   MP3 goes to the Recycle Bin.
4. A file with "start" in its name is a working file for footage and is never
   renamed, unless the piece itself is "From the Start" (Laufey).
"""

import re
from pathlib import Path


def is_working_file(filename: str, title: str | None = None) -> bool:
    if title and "from the start" in title.lower():
        return False
    return re.search(r"\bstart\b|w[ _-]?start|with[ _-]?start", Path(filename).stem, re.I) is not None


def version(filename: str) -> float:
    stem = Path(filename).stem
    m = re.search(r"edi\w*[\s_-]*(\d+)", stem, re.I) or re.search(r"(\d+)(?:st|nd|rd|th)\b", stem, re.I)
    n = float(m[1]) if m else 1.0
    if re.search(r"\bnew\b", stem, re.I):
        n += 0.5
    return n


def is_compilation(file_secs: float, upload_secs: float) -> bool:
    return upload_secs > 0 and file_secs > upload_secs * 1.4 + 20


def pick_finished(files: list[Path]) -> Path:
    """The finished version among recordings of the same piece: highest version
    number, then a file marked as edited, then the most recently saved."""
    return max(files, key=lambda p: (version(p.name), p.suffix.lower() == ".wav", bool(re.search(r"edi", p.stem, re.I)),
                                     p.stat().st_mtime if p.exists() else 0))


def mp3_twins(folder: Path) -> list[Path]:
    """MP3s that have a WAV of exactly the same name next to them."""
    wavs = {p.stem.lower() for p in folder.iterdir() if p.suffix.lower() == ".wav"}
    return sorted(p for p in folder.iterdir() if p.suffix.lower() == ".mp3" and p.stem.lower() in wavs)


def to_recycle_bin(path: Path) -> None:
    import subprocess
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Add-Type -AssemblyName Microsoft.VisualBasic; "
                    "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($args[0], 'OnlyErrorDialogs', 'SendToRecycleBin')",
                    str(path)], check=True)
