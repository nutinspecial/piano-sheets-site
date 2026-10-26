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

## Phase 2: Overture restyle (2026-10-25 to 10-26, live b3bd626)

- Time: build 25 Oct ~15:30-18:15, then a design round with the user on 26 Oct ~09:15-11:50.
- Shipped: region paintings fill the whole page behind frosted cards; Bodoni Moda headings; each
  region has its own music-following effect (Inazuma painted petals, Sumeru painted leaves, Fontaine
  light shafts and bubbles, Liyue painted sky lanterns, Mondstadt seeds and soft air, Natlan cooling
  embers from the crater, Nod Krai moon bloom and lake glints, Snezhnaya mostly round snow with
  small crystals). Effects read precomputed loudness curves (public/envelopes, all 195 tracks)
  because R2 sends no CORS header. Every effect caps its pieces on screen (lower on phones).
- Caught by validator: /scores eyebrow unreadable over the Liyue sky; fixed with ivory text + halo.
- Caught by user: ripples too faint to see; "More from Inazuma" over Snezhnaya cards (small regions
  are topped up, now each card names its region); La vaguelette and the Vourukasha medley credited
  the wrong arranger per link (credits now come from the arranger named beside each link in the
  video description, links listed in description order); lanterns flooded the screen on long
  tracks (caps added); code-drawn shapes looked cartoonish (painted cut-outs or fine detail instead).
- Caught in testing: body's own dark fill hid the fixed painting (made transparent on painted pages);
  Nod Krai beams came from the wrong corner (now mapped to the painted moon through object-fit).
- Waste: the LAN phone preview was killed 3 times by Claude Code's low-memory reaper. Fix: open it in
  its own PowerShell window (Start-Process), which the reaper leaves alone. The PC's LAN IP also
  changed overnight (.4 to .3); check it before sending phone links.
- Waste: Pollinations gpt-image-2 credits ran out mid-session (HTTP 402); flux misread a sprite
  request. Fine procedural drawing (hair-thin strokes, pre-rendered once to a strip) worked as well.
- Lesson: simple code shapes read as cartoonish; painted cut-outs (chroma key or black + luminance
  alpha) or many hair-fine strokes read as natural. Ask for a still frame after ~30 s to catch build-up.

## Phase 3: Fontaine region page (2026-10-26, live adf74ac)

- Shipped: /playlist/fontaine, 29 tracks in a listening order (bright day, afternoon and rain,
  Furina's story, night, re-recorded takes last). Underwater painting with light shafts and bubbles,
  intro in the user's voice, MusicPlaylist JSON-LD. Linked from Fontaine score pages (Keep listening),
  the phone menu and the /playlist Fontaine chip.
- Caught by user: both kalimba covers removed (playlist is piano-only, kept in tracks-quarantine.json);
  "Onduations" typo, now "Ondulations du rythme"; "Que Piano" is really "Que le vent soit doux".
- Near miss: Clair de lune was briefly moved to Classical. It is the Genshin Opera Epiclese night
  theme, not Debussy (the video description says so). Check the video description before recategorising.
- Next: Search Console check on /playlist/fontaine in 1-2 weeks; phase 4 Natlan then Mondstadt.

## Phase 4a: Natlan + Mondstadt region pages (2026-10-26, live 5db73ce, 93e8d16)

- Shipped: /playlist/natlan (20 tracks, tribes by day > partings > Capitano's war > night) and
  /playlist/mondstadt (12 tracks, morning > Springvale > Dragonspine > night > dawn at the winery),
  both copies of the Fontaine page. Linked from menu, score pages' Keep listening, /playlist pills.
- Built without waiting for Fontaine Search Console data (user's call); review all region pages together.
- Caught by fingerprint: Mondstadt "Waves" was the same recording as Mesmerizing Waves (Golden Apple),
  quarantined. Natlan had Whirl of Chalchiuhtlicue twice (WAV + MP3), MP3 quarantined.
- Caught by user: "Dragon Spine" placeholder is Fragile Fantasy (renamed, new R2 key, old key deleted).
- Next: Liyue, Inazuma, Sumeru, Snezhnaya region pages; Search Console review of all region pages.

## Phase 4b: Liyue + Inazuma pages, score sheet gaps (2026-10-26, live 9097296, ad67aef)

- Shipped: /playlist/liyue (12) and /playlist/inazuma (8). Published Another Hopeful Tomorrow; replaced the
  wrong Fading Stories with the user's new export (3:54).
- Real titles from the user: Aisa Bathhouse OST 1 = Misty Redolence; "Inazuma City" = Dream of Scattered
  Petals (full Animuz take), the shorter take is "(Short Ver.)".
- Caught by fingerprint: copies Falling Maples Sad, Sangonomiya Shrine, Theatre Troupe; Creeks of Nostalgia
  older take (kept the one matching YouTube). All in tracks-quarantine.json.
- Score sheets: 15 ChewieMelodies videos name the Patreon with no URL, so they never got score pages.
  fetch_and_parse.py now links the Patreon for that wording (16 new pages incl. one mymusicsheet score);
  --offline re-parses videos.json. Second takes share their piece's sheet link (scoresByTrack).
- Lesson: check every region's tracks for twins and placeholder names before building its page; the
  fingerprint pass took minutes and found 7 bad entries across 4 regions.
- Next: Sumeru and Snezhnaya (6 tracks each) once more covers exist; Search Console review of region pages.
