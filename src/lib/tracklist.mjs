// src/lib/tracklist.mjs
// ── Timestamped tracklists in compilation video descriptions ─────────────
// Plain JS so astro.config.mjs (sitemap filter) and the pages share it.
// A line counts as a track when it starts or ends with a timestamp, e.g.
//   "Maiden's Longing - Liyue 0:00"   or   "1:02:15 Good Night, Liyue".

const TIME = /(\d{1,2}:)?\d{1,2}:\d{2}/;
const AT_END = new RegExp(`^(.*?)[\\s(\\[]*(${TIME.source})[)\\]]?\\s*$`);
const AT_START = new RegExp(`^[\\s(\\[]*(${TIME.source})[)\\]]?\\s*[-–:.]?\\s*(.*)$`);

/** Seconds from "1:02:15" or "4:31". */
function toSeconds(t) {
  return t.split(":").reduce((s, n) => s * 60 + Number(n), 0);
}

/** [{ time, seconds, name, note }] in description order. */
export function parseTracklist(description) {
  const out = [];
  for (const raw of String(description || "").split("\n")) {
    const line = raw.trim();
    if (!line || /https?:\/\//.test(line)) continue;
    let m = line.match(AT_START);
    let time, text;
    if (m && m[3]) { time = m[1]; text = m[3]; }
    else if ((m = line.match(AT_END)) && m[1]) { time = m[2]; text = m[1]; }
    else continue;
    // "Name - note", trailing " -" / ":" left when the note is empty
    const [name, ...rest] = text.split(/\s+[-–]\s+|\s+[-–]$/);
    const clean = name.replace(/[\s:–-]+$/, "").trim();
    if (!clean) continue;
    out.push({
      time,
      seconds: toSeconds(time),
      name: clean,
      note: rest.join(" - ").replace(/[\s:–-]+$/, "").trim(),
    });
  }
  return out;
}

/** A compilation: five or more timestamped tracks. */
export function isCollection(video) {
  return parseTracklist(video.description).length >= 5;
}
