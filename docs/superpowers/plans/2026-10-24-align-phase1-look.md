# Alignment Phase 1: Look and shared tokens — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every page wears the mockup's fonts, icons, colours, shell and small parts, and the motion helpers the later phases need exist.

**Architecture:** Values move from the mockup's `:root` into `style.css` under Kitden's own token names. Fonts ship as two local woff2 files. Icons are one ES module of lucide SVG bodies, drawn by `icon()` in `dom.js`. `motion.js` gains the mockup's time and curve helpers. The shell in `index.html` and the project menu in `parts.js` take the mockup's layout. No page logic changes.

**Tech Stack:** plain ES modules, one CSS file, pytest, node's test runner. New static files only.

**Spec:** `docs/superpowers/plans/2026-10-24-mockup-alignment.md` Phase 1 (decisions D1–D7); the mockup `docs/mockup/kitden-motion.html` (CSS lines 1–140 and 286–298, `glideNav`, `go`, `projBtn`, `setProject`, `roll`, `rise`, `A`, `D`); `docs/mockup/motion-spec.md` M0 and M1; frame "M1·1 · Gateway · map" in `design/kitden.pen` (Pencil MCP).

## Global Constraints

- Everything in the master plan's Global Constraints (AGENTS.md, CSP, Calm only, reduced motion, docs and word pins with the code, checks before each commit).
- The CSP stays `default-src 'self'; script-src 'self'; style-src 'self'; …` (`src/kitden/web/security.py`). Local fonts load under `default-src 'self'`. No inline `style=""` in HTML strings; set styles through classes or `el.style`.
- Text keeps 4.5:1 in both themes. The mockup's `--faint` (#6B7381 dark, #80868F light) is for lamps, marks, ports and icons only, never for text; text the mockup draws in faint uses `--ink-4`.
- Token names stay Kitden's. Mapping (mockup → Kitden): `--out` → `--out` (new), `--canvas`, `--panel`, `--inset`, `--dim`, `--ink`, `--ink-2` → same, `--raised` → `--panel-raised`, `--muted` → `--ink-3`, `--line` → `--wire` (now solid), `--wire` → `--link` (new, map strokes), `--accent` → `--route`, `--select` → `--route-soft`, `--ok` → `--lamp-on`, `--ok-fill` → `--success`, `--on-ok` → `--on-success`, `--warn` → `--lamp-warn`, `--faint` → `--lamp-off`, `--shadow` → `--shadow` (new). `--glow` and `--beam` are Rich only and not added.
- Exact values (dark / light): out #0D0F13 / #E4E7EC; wire #3B424D / #E1E4E9; link #59616F / #C3C8D0; lamp-warn #EAC27C / #97590A; lamp-off #6B7381 / #80868F; shadow `0 18px 44px -14px rgb(0 0 0 / .7)` / `0 18px 44px -18px rgb(26 31 42 / .28)`. The other colours already match the mockup.
- Curves: `--calm: cubic-bezier(.2,.8,.2,1)`; `--spring`: the mockup's `linear(0,0.0066,0.0263 2.4%,0.1061 5%,0.2289 7.7%,0.6235 15.9%,0.7837 20.1%,0.8986 24.5%,0.9775 29.4%,1.0122 33.2%,1.031 37.5%,1.0337 42.7%,1.0242 49.5%,1.0048 61.8%,0.9989 75.4%,1)`, fallback `cubic-bezier(.3,1.25,.5,1)` (D4).
- Fonts: `@fontsource-variable/inter@5.2.5` files `inter-latin-wght-normal.woff2` and `inter-latin-ext-wght-normal.woff2`; `@fontsource-variable/jetbrains-mono@5.2.5` file `jetbrains-mono-latin-wght-normal.woff2`, from `https://cdn.jsdelivr.net/npm/<package>@<version>/files/<file>`, saved into `src/kitden/web/static/fonts/` with each package's `LICENSE` as `OFL-Inter.txt` and `OFL-JetBrainsMono.txt`. If 5.2.5 is not there, take the newest 5.x and write the version in `static/fonts/README.md`.
- Icons: `lucide-static@0.469.0` (the mockup's version), `https://cdn.jsdelivr.net/npm/lucide-static@0.469.0/icons/<name>.svg`, ISC licence kept as `static/js/icons.LICENSE`. Only these 46: arrow-left arrow-right arrow-up-right bug check chevron-down chevron-right circle-check cloud database file-text folder git-branch globe grip-vertical hard-drive history hourglass house info key-round layers library log-in log-out monitor monitor-play network package-open plug plus puzzle rotate-ccw rotate-cw scroll-text search server sparkles square-kanban store sun-moon toggle-right triangle-alert undo-2 user-round x.

## Review Focus

- Dark text on `--dim` and `--inset` in the light theme, and `--ink-4` on `--panel` in both: a token change can take them under 4.5:1. Test in Task 3.
- Reduced motion: `animateTo` and `rise` must leave nodes at their final look (opacity 1, no transform) at once. Test in Task 4.
- A narrow window (under 900 px): the rail becomes a top row, as the mockup's `@media (max-width:900px)`; nothing scrolls sideways. Test in Task 5 (CSS rule present) and the visual check.
- The theme switch keeps working with the new "Appearance" button and keeps the stored choice (`kitden-theme`). Test in Task 5.
- An icon name that is not in the module draws nothing and throws nothing. Test in Task 2.

---

### Task 1: Local fonts

**Files:**
- Create: `src/kitden/web/static/fonts/` (three woff2, two OFL texts, `README.md`)
- Modify: `src/kitden/web/static/style.css` (top: `@font-face`, `--sans`, `--mono`)
- Modify: `docs/design.md` (Identity: "Inter, medium-bold…"; the "Keep existing system fonts" line goes)
- Test: `tests/unit/test_assets.py` (new)

**Interfaces:** Produces `--sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif` and `--mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace`.

- [ ] **Step 1: Write the failing tests**

```python
STATIC = Path(__file__).parents[2] / "src/kitden/web/static"
CSS = (STATIC / "style.css").read_text()

def test_fonts_are_local_files():
    urls = re.findall(r"@font-face\s*{[^}]*url\(\"?([^\")]+)", CSS)
    assert urls and all(u.startswith("/static/fonts/") for u in urls)
    assert all((STATIC / u.removeprefix("/static/")).is_file() for u in urls)
    assert (STATIC / "fonts/OFL-Inter.txt").is_file() and (STATIC / "fonts/OFL-JetBrainsMono.txt").is_file()

def test_nothing_loads_from_another_site():
    for path in [STATIC / "index.html", STATIC / "style.css", *STATIC.glob("js/*.js")]:
        assert not re.search(r"(src|href|url)\(?=?\"?https?://", path.read_text()), path.name
```

- [ ] **Step 2:** `uv run pytest tests/unit/test_assets.py -q` → FAIL (no `@font-face`).
- [ ] **Step 3:** Download the files (Global Constraints), add `@font-face` for Inter (latin and latin-ext, `font-weight: 100 900`, `font-display: swap`, `unicode-range` from the fontsource CSS) and JetBrains Mono (latin, `font-weight: 100 800`), set `--sans` and `--mono`.
- [ ] **Step 4:** `uv run pytest tests/unit/test_assets.py -q` → PASS. Rewrite the Identity line and drop "Keep existing system fonts" in `docs/design.md`.
- [ ] **Step 5:** Run the four checks; commit "Look: Inter and JetBrains Mono as local files".

### Task 2: One icon module

**Files:**
- Create: `src/kitden/web/static/js/icons.js`, `src/kitden/web/static/js/icons.LICENSE`
- Modify: `src/kitden/web/static/js/dom.js` (add `icon`)
- Test: `tests/frontend/icons.test.mjs` (new), `tests/unit/test_assets.py`

**Interfaces:** Produces `export const ICONS = { name: "<path …/>…" }` (the inner markup of each lucide SVG, attributes as lucide ships them) and `export function icon(name, size = 16, className = "ic")` in `dom.js`: an `<svg>` element (namespace `http://www.w3.org/2000/svg`), `viewBox="0 0 24 24"`, `width`/`height` = size, `fill="none"`, `stroke="currentColor"`, `stroke-width="1.75"`, `stroke-linecap="round"`, `stroke-linejoin="round"`, `aria-hidden="true"`, class `className`; an unknown name gives an empty `<svg>` of that size.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/icons.test.mjs — stub document.createElementNS with a tiny element that keeps attributes and innerHTML
test('icon draws the lucide body at the asked size', () => {
  const node = icon('house', 14);
  assert.equal(node.getAttribute('width'), '14');
  assert.equal(node.getAttribute('stroke-width'), '1.75');
  assert.match(node.innerHTML, /<path/);
});
test('an unknown icon is empty and does not throw', () => {
  assert.equal(icon('nope').innerHTML, '');
});
```

```python
def test_every_icon_name_used_is_in_the_module():
    module = (STATIC / "js/icons.js").read_text()
    used = set(re.findall(r"icon\(\"([a-z0-9-]+)\"", "".join(p.read_text() for p in STATIC.glob("js/*.js"))))
    assert used <= set(re.findall(r"^\s*\"([a-z0-9-]+)\":", module, re.M))
```

- [ ] **Step 2:** Run both → FAIL.
- [ ] **Step 3:** Fetch the 46 SVGs, write `icons.js` (one line per icon, keys sorted), add `icon()` to `dom.js` (sets `innerHTML` from the constant module only; client text never goes through it).
- [ ] **Step 4:** Run both → PASS. Commit "Look: lucide icons as one local module".

### Task 3: Colour, line and shadow tokens

**Files:**
- Modify: `src/kitden/web/static/style.css` (`:root`, both dark blocks, every `--wire*` use that is a map stroke moves to `--link`)
- Modify: `tests/unit/test_contrast.py`, `docs/design.md` (Color roles table)

**Interfaces:** Produces `--out`, `--link`, `--shadow`, solid `--wire`; `--wire-soft` = `color-mix(in srgb, var(--wire) 60%, transparent)`, `--wire-strong` = `color-mix(in srgb, var(--ink) 18%, var(--wire))`.

- [ ] **Step 1: Write the failing test**

```python
TEXT = ("--ink", "--ink-2", "--ink-3", "--ink-4", "--route")
FILLS = ("--canvas", "--panel", "--panel-raised", "--inset", "--dim", "--route-soft")

def test_text_tokens_are_readable_on_every_fill_in_both_themes():
    for theme in (LIGHT, DARK):
        for t in TEXT:
            for f in FILLS:
                if f == "--route-soft" and t == "--ink-4":
                    continue
                assert contrast(theme[t], theme[f]) >= 4.5, (t, f)

def test_mockup_tokens_are_there():
    assert DARK["--out"] == "#0d0f13" and LIGHT["--out"] == "#e4e7ec"
    assert DARK["--link"] == "#59616f" and LIGHT["--link"] == "#c3c8d0"
    assert DARK["--lamp-warn"] == "#eac27c" and DARK["--lamp-off"] == "#6b7381"
```

- [ ] **Step 2:** `uv run pytest tests/unit/test_contrast.py -q` → FAIL.
- [ ] **Step 3:** Set the tokens (lower-case hex, both dark blocks the same). Raise `--ink-4` only if a pair fails, and say the new value in `docs/design.md`.
- [ ] **Step 4:** PASS; the Color roles table in `docs/design.md` gets Out, Line, Link, Shadow rows and the new lamp values. Commit "Look: the mockup's colours, lines and shadow".

### Task 4: Motion helpers

**Files:**
- Modify: `src/kitden/web/static/js/motion.js`, `src/kitden/web/static/style.css` (`--calm`, `--spring`)
- Modify: `docs/design.md` (Motion → Tokens: `--spring` overshoots 3.4 % on small parts; add `--calm`)
- Test: `tests/frontend/motion.test.mjs`

**Interfaces:** Produces in `motion.js`:
- `export const CALM = "cubic-bezier(.2,.8,.2,1)"`
- `export const OUT3 = (t) => 1 - (1 - t) ** 3`, `export const IN3 = (t) => t ** 3`
- `export const DRAW = "cubic-bezier(.3,.7,.2,1)"`, `export const RETRACT = "cubic-bezier(.4,0,.2,1)"`
- `export function D(ms)`: 0 under reduced motion, else `ms * slow`, where `slow` is the number in the page address `?slow=` (dev only, default 1, never shown in the UI)
- `export function animateTo(node, keyframes, { dur = 300, delay = 0, ease = CALM, fill = "backwards" } = {})`: returns a Promise that resolves when done; under reduced motion or with no `node.animate` it resolves at once and does not animate
- `export function rise(nodes, { delay = 0, step = 0, y = 6, dur = 260 } = {})`: opacity 0 → 1 and `translateY(y)` → none
- `rollTo(holder, value)` keeps its name; its motion becomes: old value 140 ms ease-in moving 70 % of its height and fading, new value 200 ms CALM from the other side

- [ ] **Step 1: Write the failing tests**

```js
test('D is zero under reduced motion', () => { reduce(true); assert.equal(D(300), 0); reduce(false); assert.equal(D(300), 300); });
test('animateTo resolves at once under reduced motion and never animates', async () => {
  reduce(true); let called = false;
  await animateTo({ animate() { called = true; } }, [{ opacity: 0 }, { opacity: 1 }]);
  assert.equal(called, false); reduce(false);
});
test('rise leaves every node visible', () => { const n = fakeNode(); rise([n]); assert.equal(n.style.opacity, ''); });
```

(`reduce(flag)` swaps the stubbed `matchMedia` result; `reducedMotion` must be read on each call, not cached at import.)

- [ ] **Step 2:** `node --test tests/frontend/motion.test.mjs` → FAIL.
- [ ] **Step 3:** Implement; keep `animate`, `transition`, `glide`, `fold`, `fly`, `land`, `entrance` working (their callers stay). `glide` uses 300 ms CALM (the mockup's nav marker), not the spring.
- [ ] **Step 4:** PASS. Commit "Motion: the mockup's curves and helpers".

### Task 5: The shell

**Files:**
- Modify: `src/kitden/web/static/index.html`, `src/kitden/web/static/style.css` (Shell, top bar, page head), `src/kitden/web/static/js/app.js` (theme button, nav marker, hint line), `src/kitden/web/static/js/parts.js` (`scopeBar` gets its icon)
- Modify: `tests/unit/test_page_words.py`, `docs/design.md` (Components: the shell)
- Test: `tests/unit/test_page_words.py`, `tests/frontend/parts.test.mjs`

**Interfaces:** Consumes `icon()` (Task 2). Produces the DOM ids the pages already use (`#main`, `#where-box`, `#q`, `#find-chip`, `#scan-status`, `#rescan`, `#scanned`, `#nav-attention`, `#nav-changes`, `#drawer`, `#toast`) plus `#theme` (now "Appearance") and `#hint` (a line at the bottom of `.content`; each page sets its text with `setHint(text)` from `app.js`).

Values from the mockup: body padding 16 px on `--out`; `.shell` is the app frame (border 1 px `--wire`, radius 12, `overflow: hidden`, `--canvas`); rail 148 px, `--panel`, border-right, gap 26, padding 20 12 18; brand 19 px / 600 / −.015em, mark 28 px; nav items 38 px tall, padding 0 10, radius 8, gap 10, icon 16 (house, library, network, history); the marker: `--route-soft`, 1 px border `color-mix(in srgb, var(--route) 30%, transparent)`, inset 2 px brand bar, glides 300 CALM; rail foot 11 px `--ink-3` keeps "Scanned … · Rescan" and "Let agents read this setup", then "Appearance" (12 px `--ink-2`, sun-moon icon 14); top bar 66 px tall, `--panel`, border-bottom, padding 0 18 0 22, gap 18; project button: folder icon 14, "Project", the name in 600 `--ink` (accent with a project picked), chevron-down 13; search: search icon 14, input 12 px, no box (the mockup's `.find`), find chip and "/" stay; main padding 26 22 64; h1 24 / 600 / −.018em; lede 12 px `--ink-3`; scope bar 11 px with layers (all projects) or folder (a project) icon 14; hint line 11 px `--ink-3`, 14 px from the bottom, info icon 13. Under 900 px: the mockup's narrow rules (rail as a top row, labels hidden).

- [ ] **Step 1: Write the failing tests**

```python
def test_shell_words():
    assert "Appearance" in INDEX and "Dark theme" not in INDEX
    assert ">Project<" in INDEX or "Project</span>" in INDEX
    assert "Let agents read this setup" in INDEX and "Rescan" in INDEX
```

```js
// parts.test.mjs
test('the scope bar leads with the layers icon, or folder in a project', () => {
  assert.equal(scopeBar(null).querySelector('svg').dataset.icon, 'layers');
  assert.equal(scopeBar('website').querySelector('svg').dataset.icon, 'folder');
});
```

(`icon()` sets `data-icon` to its name; add that to Task 2's interface if not there yet.)

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Build it. The theme button keeps `kitden-theme` and the `transition(…, "theme-switch")` path; its hover text says "Switch to light theme" or "Switch to dark theme".
- [ ] **Step 4:** PASS; existing pins that named "Project:", "Dark theme" or "Light theme" move to the new words in the same commit. Commit "Shell: the mockup's rail, top bar, head and hint line".

### Task 6: Small parts

**Files:**
- Modify: `src/kitden/web/static/style.css` (Controls), `src/kitden/web/static/js/parts.js` (switch and checkbox builders if they draw markup)
- Modify: `docs/design.md` (Components)
- Test: `tests/frontend/parts.test.mjs`

Values: `.btn` padding 7 12, radius 7, border `--wire`, fill `--panel-raised`, 12 px / 500, hover border `color-mix(in srgb, var(--route) 40%, var(--wire))`, press scale .97 260 `--spring`; `.btn.small` padding 4 9, 11 px (stays ≥ 24 px tall); `.btn.primary` 600. `.seg`: padding 2, `--inset`, border `--wire`, radius 7; buttons padding 4 11, radius 5, 12 px `--ink-3`; pressed `--ink` 500; the marker is `--panel-raised` with `0 1px 2px rgb(0 0 0 / .25)` and glides 280 CALM. `.chip` 11 px `--ink-3`, border `--wire`, radius 6, padding 3 8. New `.lamp` and `.mark` (6 px round, `--lamp-off`; `.on` `--lamp-on`; `.warn` `--lamp-warn`; `.pv` transparent with 1.5 px dashed `--route`; `.out` transparent with 1.5 px solid `--lamp-off`; colour 400 ease; `.pop` scale 2.2 → 1 200 CALM). `.port` 9 px ring, 1.5 px `--link`, `--canvas` fill. `.switch` 34×20 track in a 24 px button, knob 14 at 2/2: off `--ink-3`; on track `--route`, knob #fff at 14 px; pending dashed `--route` track on `--route-soft`, knob `--route` at 7 px; knob 340 `--spring`, track 250 ease. `.chk` 16 px, radius 4, 1.5 px `--link`; ticked `--route` fill, check icon opacity 160 / scale .5 → 1 320 `--spring`. `.radio` 14 px, 1.5 px `--link`; picked `--route` with a 3 px `--panel` inner ring.

- [ ] **Step 1: Write the failing test**

```js
test('switch looks: off, on and pending', () => {
  assert.equal(switchNode('off').getAttribute('aria-pressed'), 'false');
  assert.equal(switchNode('on').getAttribute('aria-pressed'), 'true');
  assert.ok(switchNode('pending').classList.contains('pending'));
});
```

(Use today's switch builder name in `parts.js`; if the switch is built in another module, test it there.)

- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS. Commit "Look: buttons, pills, lamps, ports, switches and checks".

### Task 7: Project menu

**Files:**
- Modify: `src/kitden/web/static/js/parts.js` (`projectMenu`), `src/kitden/web/static/style.css` (`.where-*`)
- Test: `tests/frontend/parts.test.mjs`

Values: the menu is 300 px, padding 6, `--panel`, border `--wire`, radius 10, `--shadow`; it opens with `animateTo(menu, [{opacity:0, transform:"translateY(-8px) scale(.96)"}, {opacity:1, transform:"none"}], {dur:180})` and closes 140 ease-in to `translateY(-4px) scale(.98)`. Options: padding 8 10, radius 7, gap 10, `--ink-2`; hover `--dim`; the picked one `--route-soft` with `--ink` text and a check icon 14 in `--route` at the end; "All projects" leads with layers 14, a project with folder 14; the count ("1 own rule") sits right in `--route` 11 px; the sub line 11 px `--ink-3`. After a pick the name in the button rolls (`rollTo`). Keyboard, find box, roles and words stay as they are.

- [ ] **Step 1: Write the failing test**

```js
test('the picked project carries a check, the others none', () => {
  const menu = projectMenu(PROJECTS, 'website', () => {});
  const picked = menu.querySelector('[aria-selected="true"]');
  assert.equal(picked.querySelector('svg[data-icon="check"]') !== null, true);
  assert.equal(menu.querySelectorAll('svg[data-icon="check"]').length, 1);
});
```

- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. Commit "Project menu: icons, a check and the mockup's motion".

### Task 8: Check against the frame

- [ ] **Step 1:** Start Kitden on the demo home as `docs/development.md` says (sandbox only) and open it at 1440×900.
- [ ] **Step 2:** Read frame "M1·1 · Gateway · map" with the Pencil MCP (`get_app_state`, then `execute` with `Get(<frame id>, {depth: 3})` and `TakeScreenshot`). Compare the rail, top bar, head and scope line: sizes, colours, fonts, icons. The map itself changes in Phases 2 and 4.
- [ ] **Step 3:** Fix any difference in the shell and small parts; light and dark both.
- [ ] **Step 4:** Run the four checks; commit "Look: match the shell to the frames" if anything changed.
