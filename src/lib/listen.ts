// src/lib/listen.ts
// ── Score page → the matching track in the playlist ───────────────────────
// tracks.json is written by publish_track.py / generate_tracks_manifest.py.
// A score page and a track match when their names agree after cleaning.
// track-matches.json overrides that: { "<piece slug>": "<track id>" } to
// force a match, or null to hide the player for a wrong guess.
import tracksData from "../data/tracks.json";
import overrides from "../data/track-matches.json";
import type { Piece } from "./scores";

export interface Track {
  id:       string;
  title:    string;
  category: string;
  url:      string;
  duration: number;
}

// Data shape guard: refuse to build on a track the publish scripts could not
// have written, rather than ship a player that silently fails.
function checkTrack(t: any, i: number): Track {
  const bad = (why: string) => { throw new Error(`tracks.json[${i}] ${why}: ${JSON.stringify(t).slice(0, 120)}`); };
  if (typeof t?.id !== "string" || !t.id)             bad("missing id");
  if (typeof t.title !== "string" || !t.title.trim()) bad("missing title");
  if (typeof t.category !== "string")                 bad("missing category");
  if (typeof t.url !== "string" || !/^https:\/\/\S+\.(mp3|wav|m4a|ogg)$/i.test(t.url)) bad("url is not an https audio file");
  return t as Track;
}

export const tracks: Track[] = (tracksData as unknown[]).map(checkTrack);

const clean = (s: string) => s.toLowerCase().replace(/\([^)]*\)/g, "").replace(/[^a-z0-9]/g, "");

const byName = new Map<string, Track>();
for (const t of tracks) if (!byName.has(clean(t.title))) byName.set(clean(t.title), t);
const byId = new Map(tracks.map((t) => [t.id, t]));

const manual = overrides as Record<string, string | null>;
for (const [slug, id] of Object.entries(manual)) {
  if (id !== null && !byId.has(id)) throw new Error(`track-matches.json: "${slug}" points at unknown track id "${id}"`);
}

/** The track to play on this score page, or null when there isn't one. */
export function trackForPiece(piece: Piece): Track | null {
  if (piece.slug in manual) {
    const id = manual[piece.slug];
    return id === null ? null : byId.get(id)!;
  }
  return byName.get(clean(piece.name)) ?? null;
}

/** Each track's score page. Second takes ("(Re-recorded)", "(Short Ver.)")
 *  with no page of their own share the page of the take they belong to. */
export function scoresByTrack(pieces: Piece[]): Map<string, Piece> {
  const out = new Map<string, Piece>();
  for (const piece of pieces) {
    const t = trackForPiece(piece);
    if (t && !out.has(t.id)) out.set(t.id, piece);
  }
  for (const t of tracks) {
    if (out.has(t.id)) continue;
    const twin = tracks.find((o) => out.has(o.id) && clean(o.title) === clean(t.title));
    if (twin) out.set(t.id, out.get(twin.id)!);
  }
  return out;
}

/** Where "Keep listening" goes: the region's own page, else the filtered playlist. */
export function playlistFor(track: Track): { href: string; label: string } {
  if (track.category === "Nod Krai") return { href: "/playlist/nod-krai", label: "the Nod Krai playlist" };
  if (track.category === "Fontaine") return { href: "/playlist/fontaine", label: "the Fontaine playlist" };
  if (track.category === "Sumeru") return { href: "/playlist/sumeru", label: "the Sumeru playlist" };
  if (track.category === "Snezhnaya") return { href: "/playlist/snezhnaya", label: "the Snezhnaya playlist" };
  if (track.category === "Inazuma") return { href: "/playlist/inazuma", label: "the Inazuma playlist" };
  if (track.category === "Liyue") return { href: "/playlist/liyue", label: "the Liyue playlist" };
  if (track.category === "Mondstadt") return { href: "/playlist/mondstadt", label: "the Mondstadt playlist" };
  if (track.category === "Natlan") return { href: "/playlist/natlan", label: "the Natlan playlist" };
  if (track.category === "Uncategorized") return { href: "/playlist", label: "the full playlist" };
  return {
    href:  `/playlist?region=${encodeURIComponent(track.category)}`,
    label: `the ${track.category} playlist`,
  };
}
