"""Sends the 7 approved MP3 twins (a WAV of the same recording is kept) to the Recycle Bin."""
from pathlib import Path
from version_rules import to_recycle_bin

FOLDER = Path.home() / "Downloads" / "Youtube" / "Audio"
TWINS = ["a mild melody edited.mp3", "Creeks of Nostalgia edited.mp3", "maiden's longing edited.mp3",
         "OPERA eclipse edited.mp3", "port osmo night edited.mp3", "song cinn kalimba edited.mp3",
         "trace of grace edited.mp3"]

for name in TWINS:
    p = FOLDER / name
    if p.exists():
        to_recycle_bin(p)
        print(f"  Recycle Bin: {name}")
    else:
        print(f"  not found:   {name}")
