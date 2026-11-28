// src/data/archons.ts
// Archon Shadows cast: region (playlist category) -> silhouette character.
// Used by each region page and by /playlist, which shows the same figure while
// that region's chip is picked. Add a region here when its character ships.
export interface Archon {
  character: string; // file stem in public/archon/
  action: string;    // name of the signature clip in that file
  credit: string;    // model credit, shown small at the end of the page
}

export const ARCHONS: Record<string, Archon> = {
  Mondstadt: {
    character: "venti",
    action: "lyre",
    credit:
      "Venti silhouette made from the official Genshin Impact MMD model (© miHoYo / HoYoverse, model by 神帝宇), motion from Mixamo.",
  },
  Snezhnaya: {
    character: "vodyanitsa",
    action: "sing",
    credit:
      "Vodyanitsa silhouette made from the official Genshin Impact MMD model (© miHoYo / HoYoverse, model by 观海), motion from Mixamo.",
  },
};
