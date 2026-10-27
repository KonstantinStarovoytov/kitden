# Phase 8: Check and finish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the mockup alignment. Give the README an animated hero (big house, door glow, smoke from the d) with the slogan. Close the carried items. Check the page against the mockup and the motion spec. Bring the docs up to date.

**Architecture:**
- The hero is an animated SVG made by a small script, in two files: light and dark. The README shows it through `<picture>`.
- It is plain SVG and CSS keyframes. It has no script and no outside font: the words are glyph paths.
- The rest of the phase is small fixes in the page and a check pass with the mockup open beside the page. The docs come last, so they describe what was finally built.

**Tech Stack:** Python 3.13 + Starlette, plain ES modules, one style.css, SVG + CSS. The hero script runs once with `uv run --with fonttools --with brotli python scripts/make_hero.py`. fontTools is not added to the project.

**Spec:**
- Master plan `docs/superpowers/plans/2026-10-24-mockup-alignment.md` ("Phase 8: Check and finish", and the "Notes from Phase …" lists).
- `design/logo-motion.md` (the logo gesture) and `design/kitden-cloud-smoke.html` (its mockup).
- `design/motion-spec.md` M1–M8 and `design/kitden-motion.html`.
- Owner, 2026-10-27:
  - the README gets the big house, the door glow, the smoke, the slogan and the branding, "so it catches the eye";
  - the slogan is **"Your AI coding tools, under one roof."**;
  - the gesture **repeats with a pause of about 6 s**.

## Global Constraints

- **AGENTS.md in full.**
  - Simple English in code, comments, page words and docs.
  - Tests use sandbox homes only.
  - A changing fact about another tool (here: how GitHub and PyPI show an SVG in a README) gets the date it was checked and its source.
- **Every write** goes preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`. This phase adds no new write.
- **Main pages** show a name, the client and an action. Paths, addresses and commands stay under Technical details.
- **CSP** stays `script-src 'self'; style-src 'self'`.
  - No innerHTML, no inline `style=""` in strings, no `<style>`, no `cssText` in the page.
  - CSSOM properties and `setProperty` only. Icons go through `icon()`.
  - The README hero is an image, not the page, so its own `<style>` is allowed.
- **Calm motion only**, from `motion.js`.
  - Every motion has a reduced-motion path that lands at once.
  - Nothing stays at opacity 0, and nothing loops on the page.
  - The README hero is the one loop, and only in the README (owner, 2026-10-27). It is still under reduced motion.
- **The logo stays as built:** `--hearth`, `.brand`, `.brand-mark`, `startLogo` in logo.js, the Identity paragraph and the Logo row in design.md. The hero copies its values; it changes none of them.
- **README.md is also the PyPI page:** every image and link uses a full `https://` address (docs/development.md, Release).
- **Guarded functions do not grow:** `gatewayTree`, `layoutTree`, `mapView`'s `draw`, `detailsCard`. Add small named helpers instead.
- **Docs and tests.**
  - `docs/design.md` changes in the same commit as the page change it describes.
  - New page words are pinned in `tests/unit/test_page_words.py`.
  - `tests/unit/test_contrast.py` keeps 4.5:1 (3:1 for edges and focus rings) in both themes.
- **Before each commit:** `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- **Git and processes.**
  - Never stage `design/`. Stage only your own files, by name. No `git stash`.
  - Never `pkill` in any form; stop only your own process, by its pid. The owner's pages run from `/tmp/kitden-check`; leave them.
  - No version bump, no tag, no push to main: a release is the owner's call.
- **Commit messages:** a short plain subject, one to three simple lines, ending with the Co-Authored-By line of the model that wrote the commit.

## Review Focus

1. **The hero is shown through `<img>` on GitHub and PyPI, so no script and no outside file loads.** A `<text>` in Inter would fall back to another font, and a link to a font or image would be blocked. The wordmark must be glyph paths, with no `href` to another file and no `<script>`, `<foreignObject>` or `@import`. (Task 1 test.)
2. **GitHub's light and dark themes.** `<picture>` picks `hero-dark.svg` under the dark theme. The wordmark keeps at least 3:1 (large text) on GitHub's page colours, #FFFFFF light and #0D1117 dark. (Task 1 test.)
3. **Between two plays the hero is the plain logo.** In the resting part of each cycle every puff is at opacity 0 and the door light is at 0. Nothing is left half-shown when the cycle starts again. (Task 1 test.)
4. **Reduced motion shows the plain logo, still.** No glow and no smoke: the puffs' and the light's resting opacity is 0, and the media rule turns the animations off. (Task 1 test.)
5. **The draw backstop must not draw twice.** When the frame and the timer both fire, one draw lands, and the timer is cleared when the frame comes first. (Task 2 test.)

---

### Task 1: The README hero

**Files:**
- Create:
  - `scripts/make_hero.py`;
  - `docs/images/hero.svg` and `docs/images/hero-dark.svg` (written by the script, then committed);
  - `tests/unit/test_hero.py`.
- Modify:
  - `README.md` (the top block only);
  - `docs/design.md` (one line under Identity: the README hero, where it is made, and that it loops only there).

**Interfaces:**
- **Consumes:**
  - the house path from `src/kitden/web/static/brand/kitden.svg` (64 × 64 box, the door cut out at x 12–28, y 36–58, arch radius 8);
  - `src/kitden/web/static/fonts/inter-latin-wght-normal.woff2`, the variable font, instanced at weight 600;
  - the values in `design/logo-motion.md`.
- **Produces:** `make_hero(theme: str) -> str`, where theme is `"light"` or `"dark"`; `main()` writes both files. Task 4 links to both files.

**Values (from logo-motion.md, scaled to the hero):**
- **Canvas:** viewBox width 880 and height 260, transparent background.
- **The lockup, centred like the mockup's `.kd-lockup`:**
  - wordmark "Kitden" in Inter 600 at 120 units, letter-spacing −.055 em;
  - house 150 × 150 (1.25 em), with a gap of 32.5 (13/48 em) before the word;
  - room above for the smoke, so no puff is cut at its highest point.
- **Colours:**
  - house #C85835 in both themes;
  - wordmark #161A21 light, #F2F3F5 dark;
  - smoke #626977 light, #A5ADBA dark;
  - warm #E6B46D light, #F3CC8F dark;
  - door core #FFF3DC.
- **Door light:**
  - shaped to the arch;
  - a radial gradient from the core at the bottom middle to warm at .92;
  - a soft shadow of warm spilling 5 px down (2 px at the mockup's 60 px house, × 2.5).
- **Ground glow:**
  - warm at .42;
  - a radial ellipse 56 × 42 % of the house;
  - its middle on the house's bottom edge;
  - blur 3.75 px.
- **Puffs:**
  - twelve, the mockup's shape: a rect 22 × 14.4 with r 7, an ellipse at (8, 1.8) of 7.5 × 6.75 and an ellipse at (19.5, 4) of 8.5 × 6.3, in a 28 × 20 box with viewBox `0 -5 28 20`;
  - widths cycling .30, .32, .34, .36, .38 em;
  - anchor at 80 % of the d glyph's width and 89 % of its height, measured from the glyph's outline;
  - left edge .06 em left of the anchor, bottom on it;
  - scaling around 30 % / 85 % of the puff's box, from .7 to 1.4;
  - blur 1.5 px growing to 2.5 px (.6 → 1 px at 48 px, × 2.5);
  - opacity 0 → .31 at 20 % of its path → .22 at 60 % → 0;
  - path points, as a share of right .95 em and up .42 em: 0 % (0, −.12), 20 % (.15, .40), 60 % (.60, .78), 100 % (1, .92), linear.
- **Times:**
  - one cycle is 10 510 ms: the 4510 ms gesture, then 6000 ms of rest; it repeats for ever;
  - the first cycle starts 400 ms after the image loads;
  - the door light grows over 0–1200 ms with `cubic-bezier(.45, 0, .25, 1)`, holds, and goes out over 3810–4510 ms;
  - puff i starts at 500 + 110·i ms and lasts 2600 ms, so the last one fades at 4310 ms.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` turns every animation off. The resting state, with no light and no puffs, is what shows.
- **Words:**
  - a `<title>` "Kitden";
  - `role="img"` and `aria-label` "Kitden: Your AI coding tools, under one roof.".
- **README top block:**
  - the old `logo.svg` line and the `<h1>` become `<picture>` with `hero-dark.svg` for `(prefers-color-scheme: dark)` and `hero.svg` as the `<img>`, width 100 %, with the alt from the aria-label;
  - then `<h3 align="center">Your AI coding tools, under one roof.</h3>`;
  - then today's lines "See and safely change what your AI coding agents load." and the two after it;
  - full `https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/…` addresses;
  - `docs/images/logo.svg` stays, because other places may link to it.

- [x] **Step 1: Write the failing tests** in `tests/unit/test_hero.py`. They read the two committed files and parse them with `xml.etree`:
  - `test_the_hero_loads_nothing_and_draws_its_words_as_paths`: no `<text>`, `<script>`, `<foreignObject>`, `@import`, `url(http` or `href` to another file;
  - `test_the_hero_has_twelve_puffs_with_the_logo_times`: 12 puffs; their delays are 900 + 110·i ms (400 + 500 + 110·i); the cycle is 10 510 ms; `infinite`; the puff and light keyframes match the times above;
  - `test_between_plays_the_hero_is_the_plain_logo` (Review Focus 3): from the active end to 100 %, every puff keyframe has opacity 0 and the light 0, and the 0 % frames are 0;
  - `test_reduced_motion_stills_the_hero` (Review Focus 4): the media rule sets `animation: none`, and the base opacity of puffs and light is 0;
  - `test_the_hero_colours_follow_the_theme` (Review Focus 2): light and dark colours as above, the house #C85835 in both, and the wordmark at least 3:1 on #FFFFFF and on #0D1117 (use the helper `test_contrast.py` already has);
  - `test_the_readme_shows_the_hero_and_the_slogan`: `<picture>` with both files at full `https://` addresses, and the slogan line.
- [x] **Step 2: Run** `uv run pytest tests/unit/test_hero.py -q`. Expected: FAIL (no files).
- [x] **Step 3: Write `scripts/make_hero.py`.**
  - **Font:** fontTools `TTFont`, then `varLib.instancer.instantiateVariableFont(font, {"wght": 600})`.
  - **Glyph paths:** use `SVGPathPen`, with the kerning from GPOS where it is easy and plain advance widths otherwise. The script must not need the network.
  - **Anchor:** measure the d's bounding box from its glyph for the smoke anchor.
  - **Comment:** one comment at the top names the source values (logo-motion.md) and the command that runs it.
- [x] **Step 4:** Run the script, then `uv run pytest tests/unit/test_hero.py -q`. Expected: PASS.
- [x] **Step 5: Look at it.**
  - **In the browser:** serve `docs/images` with your own `python -m http.server` (stop it by its pid). Open both files in the browser, beside `design/kitden-cloud-smoke.html`, with light and dark. The stream must read like the mockup: a soft ribbon over "en", not twelve dots.
  - **On GitHub:** check how GitHub and PyPI show an animated SVG in an `<img>`, from their docs or a known repository, and write the date and source in design.md's new line.
- [x] **Step 6: Edit README.md's top block and design.md, and run all four checks.**
- [x] **Step 7: Commit:** `README: an animated hero with the slogan`.

### Task 2: The carried fixes

**Files:**
- Modify:
  - `docs/images/how-it-works-dark.svg:47` (the old amber #E0A347 becomes the dark theme's warn colour from style.css);
  - `src/kitden/web/static/style.css` (the hit paths' keyboard look);
  - `src/kitden/web/static/js/map-view.js` (the draw backstop, as a small helper outside `draw`);
  - the project menu's code in `src/kitden/web/static/js/parts.js` or `app.js`, wherever the menu lives (the active ring).
- Test: `tests/frontend/map-view.test.mjs` (or the file that tests mapView's scheduling), `tests/frontend/parts.test.mjs` (or the menu's test), `tests/unit/test_page_words.py` (the svg colour).

**Interfaces:**
- **Consumes:** mapView's frame scheduling, and the project menu's open path.
- **Produces:** `drawSoon(run: () => void, { frame = requestAnimationFrame, wait = 120 } = {}) -> void` in map-view.js. It runs `run` once on the next frame, or after `wait` ms when no frame comes; whichever fires first clears the other.

**Rulings:**
- **Safari and `:focus-visible` on SVG.** Safari does not always match `:focus-visible` on SVG paths. A hit path is reached by Tab and its look is the hover look, so the rule uses `:focus` for the hit paths. A click that focuses a path shows the same hover look, which is harmless.
- **The project menu's active ring.** The mockup decides the look (master plan), and it has no ring when the menu opens by mouse. So the ring shows only when the menu was opened by keyboard, or after an arrow key.

- [x] **Step 1: Write the failing tests.**
  - `drawSoon draws once on the next frame and clears its timer`;
  - `drawSoon draws once after 120 ms when no frame comes` (Review Focus 5; a fake `frame` that never fires);
  - `the hit paths take the hover look on keyboard focus without focus-visible` (a CSS rule test);
  - `the project menu opened by mouse shows no active ring; an arrow key shows it`;
  - `how-it-works-dark.svg uses no old amber`.
- [x] **Step 2: Run** them. Expected: FAIL.
- [x] **Step 3: Implement.**
  - mapView's motion clock (`kick`, map-view.js ~1034) waits for a frame through `drawSoon`.
  - A stalled frame then still steps the motions to their end and settles `run`'s promise.
  - Keep `draw` itself the same size.
- [x] **Step 4: Run** all four checks. Expected: PASS.
- [x] **Step 5: Commit:** `Map: a draw lands without frames; Safari focus; menu ring`.

### Task 3: Check against the mockup and the motion spec

**Files:**
- Modify: only what the check finds. Each fix must be small (about 20 lines or fewer) and keep to the Global Constraints. A larger difference becomes a ROADMAP.md "Next" line instead.
- Create: `docs/mockup/phase8-check.md`, one line per frame and per motion: "matches", "fixed in <commit>" or "left: <why>".
- Test: a test for each behaviour fix, in the file that already tests that code.

**Interfaces:**
- **Consumes:** the demo home (`uv run kitden demo --no-browser --size large`, your own process); `design/kitden-motion.html`, served by your own `python -m http.server` from `design/`; `?slow=4`, which motion.js already reads (`D()` multiplies every time).
- **Produces:** `docs/mockup/phase8-check.md`, which Task 4 links from design.md.

**What to check:**
- **Frames and themes:**
  - every frame of the mockup: Overview, Gateway map and List, Details, the tray and toast, the add panel, Library map and List, Instructions, Changes;
  - at 1440 × 900, light and dark, the page beside the mockup;
  - the Pencil MCP may be disconnected, so the mockup HTML is the reference.
- **Motion:** M1–M8 of motion-spec.md at `?slow=4`, each duration and curve by eye against the spec's numbers.
- **The Gateway view transition** (Map ↔ List) in both themes.
- **The large demo's 39-server Gateway map:**
  - select a server and glance across the map;
  - record a performance trace in the browser and look for long tasks over 50 ms during the select;
  - note them and fix one only if it is simple.

- [x] **Step 1:** Start the demo and the mockup server. Walk every frame and motion, and write `docs/mockup/phase8-check.md` as you go.
- [x] **Step 2:** For each small difference: write the failing test (for a behaviour; a look-only CSS fix needs no test), fix it, and run the four checks. Commit in small plain commits, e.g. `Gateway: the List row height of the mockup`.
- [x] **Step 3:** Move each left difference into ROADMAP.md "Next" in one line.
- [x] **Step 4:** Stop your demo and server by their pids. Run the four checks. Commit `docs/mockup/phase8-check.md`: `Check: Phase 8 side by side with the mockup`.

### Task 4: Docs

**Files:**
- Modify:
  - `README.md` (below the hero: the "What you can do" text and its screenshots, the review section, How it works);
  - `docs/images/` (overview, gateway, library and changes shots, light and dark; review-*.jpg removed once nothing links to it);
  - `docs/design.md`;
  - `ROADMAP.md`;
  - the master plan's checkboxes.
- Create: `docs/releases/v0.3.0.md` (a draft for the owner; no version bump).
- Test: `tests/unit/test_readme.py` (create it if no README test exists; otherwise add to the one that does).

**Interfaces:**
- **Consumes:** Task 1's hero files and Task 3's `phase8-check.md`.
- **Produces:** the docs.

**Rulings:**
- **README text** describes the page as it is now, in plain short lines: the preview tray (every change waits in one tray, Apply all keeps one backup, Undo all), the maps (Gateway, Library), the Overview cards, and Changes with Undo and Redo…. The old one-change review text (README ~167–183) goes.
- **Screenshots:**
  - headless Chrome on your own large demo: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --window-size=1440,900 --force-device-scale-factor=2 --screenshot=…`, plus `--force-dark-mode` for the dark shots, then `sips -s format jpeg` at quality 80;
  - the pages are `#overview`, `#gateway?view=map`, `#library?view=map` and `#changes`;
  - for Changes, first make one change on the demo through its own API (preview, then apply) with the demo's token, so the page has a row. This goes through the engine like any change.
- **Release notes:** `docs/releases/v0.3.0.md` is grouped as New, Better and Fixed, from `git log v0.2.0..HEAD`, in plain words. The version bump, the tag and pushing main stay with the owner.
- **ROADMAP.md:**
  - the "Not released yet" section lists what this branch adds;
  - the "Last updated" date is 2026-10-27;
  - every "Left for later" note in the master plan's "Notes from Phase …" lists is a ROADMAP "Next" line, unless it is already there or done.
- **Master plan:**
  - tick Tasks 8.1–8.3 and the Part 4 checkboxes that are done;
  - add "Notes from Phase 8".

- [x] **Step 1: Write the failing test** `test_every_readme_image_is_a_full_address_to_a_file_we_have`. Every `src` and `srcset` in README.md starts with `https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/`, and the file exists in `docs/images/`. Add `test_the_readme_names_no_old_review` (no "Every change opens a review first").
- [x] **Step 2: Run** it. Expected: FAIL (review.jpg and the old text are still there).
- [x] **Step 3: Update the docs.** Take the shots and rewrite the README sections. Update design.md (link `docs/mockup/phase8-check.md`) and ROADMAP.md, write the release notes draft, and tick the plan.
- [x] **Step 4: Run** all four checks. Expected: PASS.
- [x] **Step 5: Commit:** `Docs: README, design and roadmap for the new look`.
