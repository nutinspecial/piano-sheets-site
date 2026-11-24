import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import sitemap from "@astrojs/sitemap";
import { readFileSync } from "node:fs";
import { isCollection } from "./src/lib/tracklist.mjs";

// Video pages either point at their score page (canonical) or are noindex,
// so only compilations (own tracklist page) stay in the sitemap.
// See src/lib/videoPages.ts.
const videos = JSON.parse(readFileSync(new URL("./src/data/videos.json", import.meta.url), "utf8"));
const collectionSlugs = new Set(videos.filter(isCollection).map((v) => v.slug));

export default defineConfig({
  site: "https://bigpianosmallpiano.com",
  integrations: [
    tailwind(),
    sitemap({
      filter: (page) => {
        const m = page.match(/\/videos\/([^/]+)\/?$/);
        return !m || collectionSlugs.has(m[1]);
      },
    }),
  ],
  output: "static",
  trailingSlash: "always",
  compressHTML: true,
});
