"""
build_uncategorized_review.py
Builds fix-review/uncategorized.html: every Uncategorized playlist track with a
region guess. Export saves ~/Downloads/uncategorized_fixes.json.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
GUESS = {
    "adeptus-piano": "Liyue", "fading-stories-2": "Liyue", "xu-shui-chang-liu": "Chinese",
    "mondstad-midnight": "Mondstadt", "hisui-morning-2": "Nod Krai", "marionate": "Nod Krai",
    "sangonomiya-shrine-2": "Inazuma", "matsuri-normal": "Inazuma", "falling-maples-sad": "Inazuma",
    "natlan-ode": "Natlan", "emberedited": "Natlan", "first-ember": "Natlan", "whirl": "Natlan",
    "emilie-2": "Fontaine", "theatre-troupe": "Fontaine", "que-piano": "Fontaine",
    "signal-flags": "Film", "signal-flags-2": "Film", "simu-calm-sea": "Simulanka",
    "sunday": "Pop Covers", "hinoki-wood": "Pop Covers", "love-all-mine": "Pop Covers",
    "seasons": "Pop Covers", "blue-yung-kai": "Pop Covers", "yung-kai-do": "Pop Covers",
    "vaundy-odoriko": "Pop Covers", "haru-haru": "Pop Covers", "sailor-song": "Pop Covers",
    "wish-u-love-slow": "Pop Covers", "fly-me-to-the-moon": "Pop Covers", "meeting-and-passing": "Pop Covers",
    "pure-imagination": "Film", "squid-game-opening": "Film",
    "christmas": "Christmas", "it-s-beginning-to": "Christmas", "white-christmas": "Christmas", "twinkle": "Christmas",
    "the-swan": "Classical", "hadi-not-seen-the-sun-2": "Honkai Starrail",
    "test": "__remove", "untitled": "__remove", "lullaby-editing": "__remove", "lullaby-shorten": "__remove",
}

tracks = json.loads((ROOT / "src/data/tracks.json").read_text(encoding="utf-8"))
rows = [{"id": t["id"], "file": t["filename"], "cur_title": t["title"], "cur_region": t["category"],
         "new_title": t["title"], "region": GUESS.get(t["id"], t["category"]), "video": "", "yt": "",
         "score": None, "url": t["url"]}
        for t in tracks if t["category"] == "Uncategorized"]
rows.sort(key=lambda r: (r["region"] == "Uncategorized", r["region"], r["cur_title"].lower()))
cats = sorted({t["category"] for t in tracks} | {"Chinese", "Christmas"})

page = (ROOT / "fix-review/template.html").read_text(encoding="utf-8")
page = page.replace("/*DATA*/", json.dumps({"rows": rows, "cats": cats, "out": "uncategorized_fixes.json"}, ensure_ascii=False))
page = page.replace("/*TITLE*/", "Uncategorized review").replace("/*OUT*/", "uncategorized_fixes.json")
(ROOT / "fix-review/uncategorized.html").write_text(page, encoding="utf-8")
print(f"{len(rows)} rows, {sum(r['region'] != 'Uncategorized' for r in rows)} with a guess")
