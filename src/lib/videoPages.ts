// src/lib/videoPages.ts
// ── What each /videos/<slug> page is for, as far as Google is concerned ──
// Most video pages repeat the YouTube description and embed the same video
// as their score page, so Google files them as near-duplicates. Each page
// now gets one role:
//   collection → a compilation; keeps its own page with a linked tracklist
//   score      → canonical points at the piece's score page
//   thin       → noindex (no score page and not a compilation)
// Only collections stay in the sitemap (filter in astro.config.mjs).
import { pieces, pieceByVideoId, slugify, type Piece } from "./scores";
import { parseTracklist, isCollection } from "./tracklist.mjs";

type Video = { videoId: string; title: string; description: string; slug: string };

export type VideoRole =
  | { kind: "collection" }
  | { kind: "score"; piece: Piece }
  | { kind: "thin" };

export function videoRole(video: Video): VideoRole {
  if (isCollection(video)) return { kind: "collection" };
  const piece = pieceByVideoId.get(video.videoId);
  return piece ? { kind: "score", piece } : { kind: "thin" };
}

// ── Tracklist name → score page ─────────────────────────────────────────
const bySlug = new Map<string, Piece>();
for (const p of pieces) {
  bySlug.set(slugify(p.name), p);
  bySlug.set(p.slug, p);
}

function findPiece(name: string): Piece | null {
  const s = slugify(name);
  if (!s) return null;
  const hit = bySlug.get(s);
  if (hit) return hit;
  // "Ann's Quiescent Residence" vs a piece named with an extra word or two
  for (const [k, p] of bySlug) {
    if (s.length >= 8 && (k.startsWith(s) || s.startsWith(k)) && Math.abs(k.length - s.length) <= 12) {
      return p;
    }
  }
  return null;
}

export interface TrackRow {
  time: string;
  seconds: number;
  name: string;
  note: string;
  piece: Piece | null;
}

export function tracklist(video: Video): TrackRow[] {
  return parseTracklist(video.description).map((t) => ({
    ...t,
    piece: findPiece(t.name) ?? (t.note ? findPiece(t.note) : null),
  }));
}

// ── Region playlist for a compilation ───────────────────────────────────
const REGION_PAGES: Record<string, string> = {
  "Mondstadt": "mondstadt", "Liyue": "liyue", "Inazuma": "inazuma",
  "Sumeru": "sumeru", "Fontaine": "fontaine", "Natlan": "natlan",
  "Snezhnaya": "snezhnaya", "Nod-Krai": "nod-krai",
};

/** { name, href } of the region page: exactly one region named in the title,
 *  and most matched tracks belong to it. Mixed playlists get none. */
export function collectionRegion(rows: TrackRow[], title: string): { name: string; href: string } | null {
  const named = Object.keys(REGION_PAGES).filter((r) =>
    new RegExp(r.replace("-", "[\\s-]?"), "i").test(title));
  if (named.length !== 1) return null;
  const counts = new Map<string, number>();
  for (const r of rows) {
    const reg = r.piece?.region;
    if (reg && REGION_PAGES[reg]) counts.set(reg, (counts.get(reg) ?? 0) + 1);
  }
  const matched = rows.filter((r) => r.piece).length;
  const [best] = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  if (!best || best[0] !== named[0] || matched < 3 || best[1] / matched < 0.6) return null;
  return { name: best[0], href: `/playlist/${REGION_PAGES[best[0]]}/` };
}
