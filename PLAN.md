# BPSP Site Growth Plan: build plan

Spec: "BPSP Site Growth Plan" doc, https://claude.ai/artifact/34AgPobBfynjcfZQognBEt
Tier 4 (public site). Phases 0 to 4, one at a time.

## Gate 0 baseline (2026-10-25)

- No test suite exists. Baseline = `npm run build` clean: 451 pages built, exit 0.
- Lighthouse 12.2.1, mobile, run locally (PageSpeed API quota was used up):

| Page | Score | LCP | CLS | TBT |
| --- | --- | --- | --- | --- |
| Home `/` | 68 | 6.2 s | 0.01 | 200 ms |
| Score `/scores/skazka-skazok/` | 71 | 5.6 s | 0.002 | 130 ms |
| Playlist `/playlist` | 71 | 4.2 s | 0.111 | 240 ms |

- Analytics, 27 Sep to 24 Oct 2026 (Traffic acquisition export):

| Channel | Sessions | Engaged | Avg engagement |
| --- | --- | --- | --- |
| Direct (mostly bots) | 418 | 10% | 5.6 s |
| Organic Search | 107 | 49% | 11.6 s |
| AI Assistant | 15 | 73% | 15.7 s |
| Organic Video | 8 | 63% | 32.1 s |
| Referral + Unassigned | 4 | | |

## Phase 0: Analytics events

1. Make the GA snippet `is:inline` so `gtag` is global (Astro was bundling it into a module).
   Check: built `dist/index.html` contains `gtag('config', 'G-TFZRBF4T9L')` inline.
2. Site-wide tracker in `Layout.astro`: `track_play` (once per track per page load),
   `listen_30s` (once per track), `subscribe_click` (any link to the YouTube channel).
   Check: headless browser on `npm run preview` plays a track, waits 30 s, clicks the channel
   link; all three events appear in `dataLayer` with the right track title.
   Touches: Layout.astro only.

## Later

- Register `track_title` as a custom dimension in GA (Admin > Custom definitions) so titles show in reports.
