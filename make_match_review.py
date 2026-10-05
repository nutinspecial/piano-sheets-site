"""
make_match_review.py
────────────────────
Builds match-review/index.html from match_results.json: one row per recording
with a player, the matched official title (and runners-up), a link to the
YouTube upload, and a tick box. Export saves rename_decisions.json to
Downloads for apply_audio_renames.py.

Serve the audio folder so the page can play your files:
  python -m http.server 4331 --bind 127.0.0.1 --directory "%USERPROFILE%/Downloads/Youtube/Audio"
then open match-review/index.html.
"""

import html
import json
from collections import defaultdict
from pathlib import Path

from standardize_audio_names import FOLDER
from version_rules import is_compilation, is_working_file, pick_finished

ROOT = Path(__file__).parent
OUT = ROOT / "match-review"

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Recording Name Review</title>
<style>
:root{--bg:#121110;--panel:#1b1a18;--line:#2c2a26;--text:#f2eee6;--dim:#a9a397;--gold:#e0b04a;--good:#7fd1a0;--mid:#e0b04a;--low:#e8836b;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:16px 20px;display:flex;flex-wrap:wrap;gap:12px 20px;align-items:center}
h1{font:600 20px/1.2 Georgia,serif;margin:0;flex:1 1 auto}
.tabs button,.export{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:7px 12px;font:inherit;cursor:pointer}
.tabs button[aria-pressed=true]{border-color:var(--gold);color:var(--gold)}
.export{background:var(--gold);color:#1b1a18;border-color:var(--gold);font-weight:700}
main{max-width:1100px;margin:0 auto;padding:16px 20px 80px}
.help{color:var(--dim);margin:4px 0 18px;max-width:80ch}
.row{display:grid;grid-template-columns:28px minmax(0,1.1fr) minmax(0,1.4fr) 92px;gap:14px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line)}
.row[hidden]{display:none}
.file{font-family:ui-monospace,monospace;font-size:13px;word-break:break-all}
.secs{color:var(--dim);font-size:12px}
audio{width:100%;height:32px;margin-top:6px}
select,input[type=text]{width:100%;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:7px 8px;font:inherit}
input[type=text]{margin-top:6px;display:none}
.yt{display:inline-block;margin-top:6px;color:var(--gold);font-size:13px}
.conf{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.conf.high{color:var(--good)}.conf.medium{color:var(--mid)}.conf.low{color:var(--low)}
.score{color:var(--dim);font-size:12px;font-variant-numeric:tabular-nums}
.note{color:var(--low);font-size:12px;margin-top:2px}
input[type=checkbox]{width:18px;height:18px;accent-color:var(--gold)}
@media(max-width:720px){.row{grid-template-columns:28px 1fr}.row>div:nth-child(3),.row>div:nth-child(4){grid-column:2}}
</style></head><body>
<header><h1>Recording name review</h1>
<div class="tabs" role="group" aria-label="Filter">
<button data-f="all" aria-pressed="true">All</button><button data-f="high">High</button>
<button data-f="medium">Medium</button><button data-f="low">Low</button><button data-f="ticked">Ticked</button></div>
<span id="count" class="score"></span><button class="export" id="export">Export decisions</button></header>
<main><p class="help">Each recording was compared with every YouTube upload by its music. <b>High</b> matches are ticked
already. For the rest, play your file and open the upload to compare, pick the right title (or "Leave unchanged"), and tick it.
Only ticked rows are renamed. Choices are remembered in this browser. When done, press <b>Export decisions</b>.</p>
<div id="rows">__ROWS__</div></main>
<script>
const KEY="bpsp-rename-review";const saved=JSON.parse(localStorage.getItem(KEY)||"{}");
const rows=[...document.querySelectorAll(".row")];
function state(r){const s=r.querySelector("select"),c=r.querySelector("input[type=checkbox]"),t=r.querySelector("input[type=text]");
 return{tick:c.checked,choice:s.value,custom:t.value}}
function save(){const o={};rows.forEach(r=>o[r.dataset.file]=state(r));localStorage.setItem(KEY,JSON.stringify(o));count()}
function count(){const n=rows.filter(r=>r.querySelector("input[type=checkbox]").checked).length;document.getElementById("count").textContent=n+" of "+rows.length+" ticked"}
rows.forEach(r=>{const s=r.querySelector("select"),c=r.querySelector("input[type=checkbox]"),t=r.querySelector("input[type=text]"),y=r.querySelector(".yt");
 const v=saved[r.dataset.file];if(v){c.checked=v.tick;s.value=v.choice;t.value=v.custom}
 const sync=()=>{t.style.display=s.value==="__custom"?"block":"none";const o=s.selectedOptions[0];if(o&&o.dataset.id){y.href="https://www.youtube.com/watch?v="+o.dataset.id;y.style.visibility="visible"}else y.style.visibility="hidden"};
 sync();s.addEventListener("change",()=>{sync();save()});c.addEventListener("change",save);t.addEventListener("input",save)});
document.querySelectorAll(".tabs button").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll(".tabs button").forEach(x=>x.setAttribute("aria-pressed",x===b));
 const f=b.dataset.f;rows.forEach(r=>r.hidden=!(f==="all"||r.dataset.conf===f||(f==="ticked"&&r.querySelector("input[type=checkbox]").checked)))}));
document.getElementById("export").addEventListener("click",()=>{const out=rows.filter(r=>r.querySelector("input[type=checkbox]").checked).map(r=>{const s=state(r);
 return{file:r.dataset.file,title:s.choice==="__custom"?s.custom.trim():s.choice==="__leave"?null:s.choice}});
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:"application/json"}));a.download="rename_decisions.json";a.click()});
document.querySelectorAll("audio").forEach(a=>a.addEventListener("play",()=>document.querySelectorAll("audio").forEach(b=>b!==a&&b.pause())));
count();
</script></body></html>"""


def row(r: dict) -> str:
    e = html.escape
    cands = r["candidates"]
    held = r.get("note")                       # older version or footage working file
    pick = r["confidence"] != "low" and not held
    opts = "".join(
        f'<option value="{e(c["title"])}" data-id="{e(c["id"])}"{" selected" if i == 0 and pick else ""}>'
        f'{e(c["title"])}  ({c["score"]:.2f})</option>' for i, c in enumerate(cands))
    leave_sel = "" if pick else " selected"
    opts += f'<option value="__leave"{leave_sel}>Leave unchanged</option><option value="__custom">Type a title…</option>'
    first = cands[0] if cands else None
    yt = f'https://www.youtube.com/watch?v={first["id"]}' if first else "#"
    note = f'<div class="note">{e(held)}</div>' if held else ""
    return (f'<div class="row" data-file="{e(r["file"])}" data-conf="{r["confidence"]}">'
            f'<input type="checkbox" aria-label="Rename {e(r["file"])}"{" checked" if r["confidence"] == "high" and not held else ""}>'
            f'<div><div class="file">{e(r["file"])}</div><div class="secs">{r["secs"] // 60}:{r["secs"] % 60:02d}</div>{note}'
            f'<audio controls preload="none" src="http://127.0.0.1:4331/{e(r["file"])}"></audio></div>'
            f'<div><select aria-label="Official title">{opts}</select><input type="text" placeholder="Official title">'
            f'<a class="yt" href="{yt}" target="_blank" rel="noopener">Open the YouTube upload ↗</a></div>'
            f'<div><div class="conf {r["confidence"]}">{r["confidence"]}</div>'
            f'<div class="score">{first["score"]:.2f} match</div></div></div>' if first else "")


def main() -> None:
    results = json.loads((ROOT / "match_results.json").read_text(encoding="utf-8"))
    # House rules: footage working files stay as they are; of several versions
    # of a piece, only the highest-numbered one is renamed.
    groups = defaultdict(list)
    for r in results:
        title = r["candidates"][0]["title"] if r["candidates"] else None
        if is_working_file(r["file"], title):
            r["note"] = "Working file (has 'start' in the name): left as is"
        elif r["candidates"] and is_compilation(r["secs"], r["candidates"][0]["dur"]):
            r["note"] = f"Compilation or loop that contains {title} ({r['secs'] // 60} min): left as is"
        elif r["confidence"] in ("high", "medium") and title:
            groups[title].append(r)
    for title, rs in groups.items():
        if len(rs) > 1:
            keep = pick_finished([FOLDER / x["file"] for x in rs]).name
            for x in rs:
                if x["file"] != keep:
                    x["note"] = f"Older version of {title}; {keep} is the finished one"
    order = {"low": 0, "medium": 1, "high": 2}
    results.sort(key=lambda r: (order[r["confidence"]], r["file"].lower()))
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(PAGE.replace("__ROWS__", "".join(row(r) for r in results)), encoding="utf-8")
    print(f"wrote {OUT / 'index.html'} ({len(results)} rows)")


if __name__ == "__main__":
    main()
