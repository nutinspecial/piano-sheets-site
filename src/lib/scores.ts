// src/lib/scores.ts
// ── One page per piece ───────────────────────────────────────────────────
// scores.json has one entry per video. A piece can have more than one video
// (a re-recording, an extended cut), so entries are grouped by a slug made
// from the cleaned piece name. Each group becomes /scores/<slug>.
import scores from "../data/scores.json";
import videos from "../data/videos.json";
import { trackForPiece } from "./listen";

export type ScoreEntry = (typeof scores)[number];

export interface Piece {
  slug:     string;
  name:     string;          // "Skazka Skazok"
  game:     string | null;   // "Genshin Impact"
  region:   string | null;   // "Snezhnaya"
  versions: ScoreEntry[];    // newest first
}

// Credits that are really the link host, not an arranger.
const HOST_LABELS = new Set([
  "musescore", "google drive", "gumroad", "dropbox", "imslp", "mediafire",
  "scribd", "onedrive", "pdf", "download",
]);

/** The arranger to credit, or null when the parser only knows the host. */
export function arranger(entry: ScoreEntry): string | null {
  const c = entry.credits?.[0];
  return c && !HOST_LABELS.has(c.toLowerCase()) ? c : null;
}

// ── Who arranged which link ───────────────────────────────────────────────
// scores.json keeps credits and links as two separate lists, and their order
// does not always match (La vaguelette: MaruPiano did the beginning on
// MuseScore, Animuz the latter half on Drive). The video description says
// which is which, so each link takes the arranger named on its own line, or
// failing that on the nearest line above it (up to 3 lines, stopping at
// another link). Names match on their first 6 letters, so "Animuz" finds
// "AnimuzAnimePiano".
const descriptions = new Map(videos.map((v) => [v.videoId, v.description ?? ""]));
const needle = (name: string) => name.toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 6);
const flat   = (line: string) => line.toLowerCase().replace(/[^a-z0-9]/g, "");

/** The entry's links in the order the description lists them. */
export function orderedLinks(entry: ScoreEntry): string[] {
  const d = descriptions.get(entry.videoId) ?? "";
  const at = (l: string) => { const i = d.indexOf(l); return i === -1 ? Infinity : i; };
  return [...entry.scoreLinks].sort((a, b) => at(a) - at(b));
}

/** The arranger of one link, or null when the parser only knows the host. */
export function linkArranger(entry: ScoreEntry, link: string): string | null {
  const names = (entry.credits ?? []).filter((c) => !HOST_LABELS.has(c.toLowerCase()));
  if (names.length < 2 || entry.scoreLinks.length < 2) return arranger(entry);
  const lines = (descriptions.get(entry.videoId) ?? "").split("\n");
  const row = lines.findIndex((l) => l.includes(link));
  if (row === -1) return arranger(entry);
  for (let i = row; i >= Math.max(0, row - 3); i--) {
    if (i < row && /https?:\/\//.test(lines[i])) break;
    const hits = names.filter((n) => flat(lines[i]).includes(needle(n)));
    if (hits.length === 1) return hits[0];
    if (hits.length > 1) break;          // a heading listing everyone: no answer here
  }
  return arranger(entry);
}

export function linkLabel(url: string): string {
  if (url.includes("drive.google.com")) return "Google Drive";
  if (url.includes("gumroad.com"))      return "Gumroad";
  if (url.includes("musescore.com"))    return "MuseScore";
  if (url.includes("dropbox.com"))      return "Dropbox";
  if (url.includes("imslp.org"))        return "IMSLP";
  if (url.includes("mediafire.com"))    return "MediaFire";
  if (url.includes("scribd.com"))       return "Scribd";
  if (url.includes("1drv.ms") || url.includes("sharepoint.com")) return "OneDrive";
  if (url.endsWith(".pdf"))             return "PDF";
  return "Download";
}

/** "'Skazka Skazok' - Calm Night Snezhnaya OST | Genshin Piano + Sheet" → "Skazka Skazok" */
export function pieceName(title: string): string {
  let t = title.split("|")[0];
  t = t.replace(/^\s*(?:genshin|movie|studio ghibli)\s+ost:\s*/i, "");
  t = t.replace(/\s*[-–]\s*piano cover.*$/i, "");

  // A quoted name wins. The closing quote must not be followed by a letter,
  // so "A Dandelion's Promise" stays whole.
  const quoted = t.match(/'(.+?)'(?![\w])/);
  if (quoted) return quoted[1].trim();

  return t
    .replace(/\([^)]*\)/g, "")
    .replace(/\s+[-–]\s+[^-–]*\b(?:OST|BGM|Theme Song)\b.*$/i, "")
    .replace(/[\s:–-]+$/, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function slugify(s: string): string {
  return s
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const REGIONS: [RegExp, string][] = [
  [/nod[\s-]?krai|columbina|sandrone|hiisi|kratti|barrowmoss|silvermoon|linnea|piramida|aila/i, "Nod-Krai"],
  [/snezhnaya|snezhnograd|vodyanitsa|odette|korolevskiy|morepesok/i, "Snezhnaya"],
  [/natlan|tonatiuh|xilonen|tecoloapan|ameyalco|capitano/i, "Natlan"],
  [/fontaine|belleau|beryl|navia|neuvillette|focalors|freminet|springvale|escoffier|emilie|petrichor|thelxie|coruscating|clio|masquerade|pluie sur la ville|lustrous stars|via col vento/i, "Fontaine"],
  [/sumeru|vourukasha|khvarena|riddles, for wonders|gone with the wind/i, "Sumeru"],
  [/inazuma|aisa|kazuha|kiseru/i, "Inazuma"],
  [/liyue|adeptus|chasm/i, "Liyue"],
  [/mondstadt|bennett|pure sky|winery|new day with hope/i, "Mondstadt"],
];

function detectGame(title: string): string | null {
  if (/honkai:?\s*star rail|\bhsr\b/i.test(title)) return "Honkai: Star Rail";
  if (/honkai impact/i.test(title))                return "Honkai Impact 3rd";
  if (/\bzzz\b/i.test(title))                      return "Zenless Zone Zero";
  if (/shorekeeper/i.test(title))                  return "Wuthering Waves";
  if (/genshin|easybreeze|veluriyam|hoyofest/i.test(title)) return "Genshin Impact";
  if (REGIONS.some(([re]) => re.test(title)))      return "Genshin Impact";
  return null;
}

function detectRegion(title: string): string | null {
  if (detectGame(title) !== "Genshin Impact") return null;
  for (const [re, name] of REGIONS) if (re.test(title)) return name;
  return null;
}

function buildPieces(): Piece[] {
  const bySlug = new Map<string, Piece>();
  const sorted = [...scores].sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));

  for (const entry of sorted) {
    const name = pieceName(entry.title);
    const slug = slugify(name) || entry.slug;
    const existing = bySlug.get(slug);
    if (existing) {
      existing.versions.push(entry);
      existing.game   ??= detectGame(entry.title);
      existing.region ??= detectRegion(entry.title);
    } else {
      bySlug.set(slug, {
        slug,
        name,
        game:     detectGame(entry.title),
        region:   detectRegion(entry.title),
        versions: [entry],
      });
    }
  }
  const all = [...bySlug.values()];
  for (const piece of all) fromTrack(piece);
  return all;
}

// The playlist categories were sorted by hand, so a matching track's category
// beats the keyword guess above. [game, region] per category.
const TRACK_CATEGORY: Record<string, [string, string | null]> = {
  "Mondstadt":                ["Genshin Impact", "Mondstadt"],
  "Liyue":                    ["Genshin Impact", "Liyue"],
  "Inazuma":                  ["Genshin Impact", "Inazuma"],
  "Sumeru":                   ["Genshin Impact", "Sumeru"],
  "Fontaine":                 ["Genshin Impact", "Fontaine"],
  "Natlan":                   ["Genshin Impact", "Natlan"],
  "Snezhnaya":                ["Genshin Impact", "Snezhnaya"],
  "Nod Krai":                 ["Genshin Impact", "Nod-Krai"],
  "Simulanka":                ["Genshin Impact", "Simulanka"],
  "Veluriyam Mirage":         ["Genshin Impact", "Veluriyam Mirage"],
  "Golden Apple Archipelago": ["Genshin Impact", "Golden Apple Archipelago"],
  "Genshin Archon Quests":    ["Genshin Impact", null],
  "Honkai Starrail":          ["Honkai: Star Rail", null],
  "Honkai Impact":            ["Honkai Impact 3rd", null],
  "Wuthering Waves":          ["Wuthering Waves", null],
  "ZZZ":                      ["Zenless Zone Zero", null],
};

function fromTrack(piece: Piece) {
  const track = trackForPiece(piece);
  const known = track && TRACK_CATEGORY[track.category];
  if (!known) return;
  piece.game = known[0];
  if (known[1]) piece.region = known[1];
}

export const pieces: Piece[] = buildPieces();

/** videoId → piece, for linking from video pages and the scores table. */
export const pieceByVideoId = new Map<string, Piece>(
  pieces.flatMap((p) => p.versions.map((v) => [v.videoId, p] as [string, Piece]))
);

/** Up to `n` other pieces, same region first, then same game, then newest. */
export function relatedPieces(piece: Piece, n = 6): Piece[] {
  const score = (p: Piece) =>
    (piece.region && p.region === piece.region ? 2 : 0) +
    (piece.game && p.game === piece.game ? 1 : 0);
  return pieces
    .filter((p) => p.slug !== piece.slug)
    .map((p, i) => ({ p, s: score(p), i }))
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .slice(0, n)
    .map(({ p }) => p);
}
