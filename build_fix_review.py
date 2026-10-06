"""
build_fix_review.py
Builds fix-review/index.html: one row per playlist track whose title disagrees
with its matched YouTube upload, with the live audio, the upload link, the
proposed title and a region guess. Export the page's choices to
~/Downloads/playlist_fixes.json, then apply with apply_playlist_fixes.py.
"""
import html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from standardize_audio_names import FOLDER, original_ids  # noqa: E402

REGIONS = [
    (r"nod[\s-]?krai|columbina|sandrone|hiisi|kratti|barrowmoss|silvermoon|linnea|piramida|aila", "Nod Krai"),
    (r"snezhnaya|snezhnograd|vodyanitsa|odette|korolevskiy|morepesok", "Snezhnaya"),
    (r"natlan|tonatiuh|xilonen|tecoloapan|ameyalco|capitano", "Natlan"),
    (r"fontaine|belleau|beryl|navia|neuvillette|focalors|freminet|springvale|escoffier|emilie|petrichor|thelxie|coruscating|clio|masquerade|pluie sur la ville|lustrous stars|via col vento|romaritime", "Fontaine"),
    (r"sumeru|vourukasha|khvarena|riddles, for wonders|gone with the wind", "Sumeru"),
    (r"inazuma|aisa|kazuha|kiseru", "Inazuma"),
    (r"liyue|adeptus|chasm", "Liyue"),
    (r"mondstadt|bennett|pure sky|winery|new day with hope", "Mondstadt"),
    (r"veluriyam", "Veluriyam Mirage"), (r"simulanka", "Simulanka"),
    (r"golden apple", "Golden Apple Archipelago"),
    (r"honkai:?\s*star rail|\bhsr\b", "Honkai Starrail"), (r"honkai impact", "Honkai Impact"),
    (r"\bzzz\b|zenless", "ZZZ"), (r"wuthering|shorekeeper", "Wuthering Waves"),
    (r"laufey|norah jones|jazz piano cover|pop", "Pop Covers"),
    (r"anime", "Anime"), (r"k-?drama", "K-Drama"), (r"\bfilm\b|movie", "Film"),
]

def guess(video_title):
    for pat, name in REGIONS:
        if re.search(pat, video_title, re.I):
            return name
    return ""

tracks = json.loads((ROOT / "src/data/tracks.json").read_text(encoding="utf-8"))
by_id = {t["id"]: t for t in tracks}
decisions = {d["file"]: d["title"] for d in json.loads((Path.home() / "Downloads/rename_decisions.json").read_text(encoding="utf-8"))}
matches = {m["file"]: m for m in json.loads((ROOT / "match_results.json").read_text(encoding="utf-8"))}
ids = {p.name: i for p, i in original_ids().items() if p.parent == FOLDER}

rows = []
for file, tid in ids.items():
    t, new = by_id.get(tid), decisions.get(file)
    if not t or not new or t["title"] == new:
        continue
    cand = next((c for c in matches.get(file, {}).get("candidates", []) if c["title"] == new), None)
    vt = cand["video"] if cand else ""
    rows.append({"id": tid, "file": file, "cur_title": t["title"], "cur_region": t["category"],
                 "new_title": new, "region": guess(vt) or t["category"], "video": vt,
                 "yt": cand["id"] if cand else "", "score": cand["score"] if cand else None,
                 "url": t["url"]})
rows.sort(key=lambda r: (r["region"] == r["cur_region"], r["region"], r["new_title"]))
cats = sorted({t["category"] for t in tracks} | {r["region"] for r in rows})

page = (ROOT / "fix-review/template.html").read_text(encoding="utf-8")
page = page.replace("/*DATA*/", json.dumps({"rows": rows, "cats": cats, "out": "playlist_fixes.json"}, ensure_ascii=False))
page = page.replace("/*TITLE*/", "Playlist title review").replace("/*OUT*/", "playlist_fixes.json")
(ROOT / "fix-review/index.html").write_text(page, encoding="utf-8")
print(f"{len(rows)} rows, {sum(r['region'] != r['cur_region'] for r in rows)} with a region change")
