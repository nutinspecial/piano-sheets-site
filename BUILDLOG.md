# Build log

## Phase 0: Analytics events (2026-10-25, live e9e9b8b)

- Time: about 30 min machine time (plan + baseline, build, own test, independent validator ~4 min).
- Caught: Astro bundled the gtag snippet into a module, so `gtag` was not global. New events would have
  failed silently (you would have seen zero events in Realtime and no error). Fixed with `is:inline`.
- Caught: shell cwd inside `dist/` made `astro build` fail with EPERM. Never cd into dist.
- Waste: PageSpeed API (keyless) was out of daily quota; local `npx lighthouse@12.2.1` works instead.

## Phase 1: listen-here player (2026-10-25, live e5bde2c)

- 116 of 145 score pages get a player; 29 have no track yet (list in the session match-list page).
- Caught by user: 24 Genshin score pages had a blank region (keyword guess missed, e.g. La vaguelette).
  Fixed by taking game/region from the matching track's hand-sorted category; also fixed Sunny Summer
  Fontinalia (Nod-Krai -> Fontaine). Lesson: trust hand-curated data over title guesses.
- Caught by validator: long titles were cut off with an ellipsis on phones; now wrap to 2 lines.
- Waste: auto-mode permission classifier outage stalled ~2 turns; switching out of auto mode got past it.
