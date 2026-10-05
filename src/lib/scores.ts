// src/lib/scores.ts
// ── One page per piece ───────────────────────────────────────────────────
// scores.json has one entry per video. A piece can have more than one video
// (a re-recording, an extended cut), so entries are grouped by a slug made
// from the cleaned piece name. Each group becomes /scores/<slug>.
import scores from "../data/scores.json";

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
  return [...bySlug.values()];
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
