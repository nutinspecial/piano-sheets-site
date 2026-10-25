# Build log

## Phase 0: Analytics events (2026-10-25, live e9e9b8b)

- Time: about 30 min machine time (plan + baseline, build, own test, independent validator ~4 min).
- Caught: Astro bundled the gtag snippet into a module, so `gtag` was not global. New events would have
  failed silently (you would have seen zero events in Realtime and no error). Fixed with `is:inline`.
- Caught: shell cwd inside `dist/` made `astro build` fail with EPERM. Never cd into dist.
- Waste: PageSpeed API (keyless) was out of daily quota; local `npx lighthouse@12.2.1` works instead.
