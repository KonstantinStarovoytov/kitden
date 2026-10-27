# Overview and Changes in the mockup: notes for the build (Calm only)

Sources read in full: `docs/mockup/kitden-motion.html` (v11) `Overview` (1231-1270) and `Changes` (1273-1300), the helpers they call
(`rise` 471, `blurIn` 473, `roll` 474, `countUp` 475, `fold` 480, `panelLoad` 534, `dock.toast` 542), `motion-spec.md` M8 (401-444), and
decisions D21-D24 in `docs/superpowers/plans/2026-10-24-mockup-alignment.md`. Line numbers are in `kitden-motion.html` unless marked.
"Calm" = `S.rich` false. `D(ms)` = 0 under reduced motion. Default Web Animation ease = CALM `cubic-bezier(.2,.8,.2,1)`, default 300 ms.
`rise` in Calm = opacity 0 → 1 and translateY 6px → 0, 260 ms, no blur.

| Thing | Function / CSS | Line |
|---|---|---|
| Overview data (4 cards) | `Overview.cards` | 1233-1236 |
| Overview mount, mini-map | `mount` | 1237-1247 |
| Card HTML | `card(c)` | 1248 |
| Entrance | `enter` | 1249-1254 |
| Hover, map click, fold, buttons | `wire` | 1255-1259 |
| Fix flow, collapse, undo | `act` | 1260-1268 |
| Overview CSS | `.ov-grid` .. `.ov-foot` | 252-267 |
| Changes data (5 rows) | `Changes.rows` | 1275-1279 |
| Changes mount, row HTML, entrance | `mount` 1280, `row` 1286, `enter` 1287 | |
| Select, Details card | `select` | 1289-1294 |
| Undo and Redo | `undo` | 1295-1300 |
| Changes CSS | `.tl` .. `.row .state` | 269-290 |
| Panel / toast CSS | `.panel` 202-217, `.toast` 244-246 | |
| Page head helper, page switch | `head` 1303, `go` 1310 | |

## 1. Overview head

- `h1` (24px / 600, `data-blur`): **"Your setup, connected."** Calm: rise 260, delay 0 (`blurIn` 473).
- Lede (12px `--muted`, margin-top 4), verbatim with live numbers:
  **"2 things need your attention. Everything else looks fine: 3 clients, 4 projects."**
  - The three numbers are `.num` spans (tabular figures): `#need-n` 2, `#cl-n` 3, `#pr-n` 4. They count up from 0 in 700 ms OUT3,
    delays 200 / 260 / 320.
  - `#need-w` is "things need"; at count 1 it is "thing needs" (swapped at once, no motion).
  - Nothing says what happens at 0 ("Everything looks fine" is missing); the build needs its own all-clear words.
- Scope bar (`.scope`, 11px `--muted`, margin-top 12): `layers` icon 14 + **"All projects · 3 clients · demo workspace"**. With a project
  picked the shared `head()` shows an accent `folder` + "Project <name>", but Overview does not use `head()`, so a project change does
  nothing here in the mockup.
- Right of the head: the "Demo data" chip (study-only; do not build).
- Lede and scope rise: y 6, 260, delay 120 and 180 (the `go` call at 1317, since Overview skips `blurIn` there).
- Hint line (bottom of the page, 11px), verbatim: **"Hover a card · Fix… · Show notes · click Kitden gateway or Library"** (1232).
  Rewrite it for the build; it names "Fix…" which not every card uses.

## 2. Overview cards

Layout (`.ov-grid` 252): two columns `minmax(0,690px) minmax(0,480px)`, gap 40, margin-top 20, top aligned. Left = cards and notes,
right = "Your setup". At 900px wide or less: one column.

### 2.1 Groups

- Captions (`.ov-cap`: flex, gap 6, 11px / 600, `--ink-2`, margin 14px 0 8px; the first one has margin-top 0):
  - `triangle-alert` icon 13 (colour `--warn`) + **"Needs attention"**. Holds `#need`.
  - `sparkles` icon 13 + **"Can improve"**. Holds `#can`.
- Card lists (`.cards`): column, gap 8.
- Sample split: Needs attention = GitHub, Linear. Can improve = Dropbox, Cursor.
- Empty group: the caption stays when its last card collapses (not handled in the mockup; hide the caption when the group is empty).

### 2.2 Card parts (`.card` 258-262, `card()` 1248)

- Box: flex, align centre, gap 12, padding 12px 14px, `--panel` fill, 1px `--line` border, radius 8. No hover style of its own.
- Left to right:
  1. Icon tile (`.itile`: 28x28, radius 6, 1px line, `--inset` fill, icon 15 in `--ink-2`). Icons: git-branch, square-kanban,
     package-open, plug.
  2. Text (`.tx`: column, gap 2, flex 1): name in 12px / 600; the line under it in 11px `--muted`.
  3. Client tiles (`.who`: flex, gap 4, small 20x20 `tile(id,1)` images, radius 5; Claude Code has 3px padding).
  4. One button (`.btn`; `.primary` for the two "Needs attention" cards).
- Sample lines, verbatim:

| Card | Group | Line | Tiles | Button |
|---|---|---|---|---|
| GitHub | need | "Set up twice: in Claude Code and in the gateway." | Claude Code | **Fix…** (primary) |
| Linear | need | "Needs sign-in. Its tools stay off until then." | Claude Code, Codex | **Sign in…** (primary) |
| Dropbox | can | "Skips the gateway, so Kitden's rules don't reach it." | Claude Code | **Move in…** |
| Cursor | can | "Not connected to the gateway yet." | Cursor | **Connect…** |

- What the button does in the mockup (`act` 1260):
  - Dropbox "Move in…" only switches page: `go('gateway',{arrive:'o~dropbox'})`. After the Gateway entrance, the Dropbox block gets the
    lit look for 1600 ms (Rich: ripple .7).
  - The other three run a fake in-place fix, section 2.4. **The build must not copy this.** Decision D22: each button adds a preview
    to the tray (title, detail, who); the card leaves only after Apply verifies. Words stay "Fix…", "Connect…", "Move in…" (the "…" means
    "opens a preview first"). "Sign in…" goes (D23).
  - Toast words in the mockup (`c.done`): "Fixed GitHub: one entry left, in the gateway" and "Connected Cursor to the gateway". In the
    build the tray's own toast ("Applied N changes" / the row's sentence) replaces them.

### 2.3 Hover focuses the mini-map

- Yes. `pointerover` on `main` (1256): pointer onto a card calls `m.focus(card.focus.n, card.focus.l)` and `m.beam(...)`.
  - Calm: only the focus. Blocks off the path get `filter: opacity(.4) saturate(.6)`, links off the path `stroke-opacity .16`, lit links
    accent 1.7px, lit ports accent border; all CSS 300 ms ease (161, 170, 134). Beam does nothing in Calm (`beam` returns at once).
  - Pointer onto anything that is not a card: `m.unfocus()`, but only when it was on a card before (`this._hc` guard). So focus set by
    a click on a client block (2.5 and section 3) stays until the pointer next enters and leaves a card.
- Focus sets per card (clients and gateway/Library blocks, then links):
  - GitHub: Claude Code, gateway; link Claude Code → gateway.
  - Linear: Claude Code, Codex, gateway; both links to the gateway.
  - Dropbox: Claude Code, gateway; link Claude Code → gateway. (The mockup lights the gateway link although the point is that Dropbox
    skips it; in the build, light the client and the outside server's route.)
  - Cursor: Cursor, gateway; link Cursor → Library (mismatch: the gateway block is lit, the Library block is not; light the client and
    the link only, or the client and the gateway if the fix is "Connect to the gateway").
- Keyboard focus on a card does nothing (no `focusin` handler); the build should mirror hover on `focusin`/`focusout` of the button.

### 2.4 The collapse after a fix (`act` 1260-1268), Calm timings

1. Button: `pointer-events:none`, width pinned, content = spinner icon (`rotate-cw` 14, spin, 800 per turn). Wait 700.
2. Button turns green: loses `.primary`, gains `.ok` (fill `--ok-fill`, text `--on-ok`; CSS 180). A check icon replaces the spinner and
   draws in 300 (`drawSvg`, DRAW curve). Wait 150 (Rich: spark, wait 420).
3. Card leaves: opacity 1 → 0, translateX 0 → 28px, 180 ease-in, fill forwards (Rich 320 with blur 6).
4. Card collapses: height (its own) → 0, margin-bottom 0 → -8px, padding top and bottom → 0, border width → 0; 160 CALM, fill forwards
   (Rich 260). Then `card.hidden = true` and its animations cancelled.
5. Siblings in the same list slide: translateY(oldTop - newTop) → 0, 220 CALM (Rich 520).
6. If the card was in "Needs attention": counter `left--`, `#need-n` rolls down (`roll`: old value out 140 ease-in, new in 200 CALM),
   `#need-w` text swaps at once.
7. Toast with Undo (section 6 for the shell). Mockup undo (1268): card unhidden, button restored, card fades back
   opacity 0 → 1 with translateY -8px and scale .98 → none, 220 CALM (Rich 520); `left++`, number rolls up, `#need-w` = "things need".

**The collapse jump.** Step 5 reads each sibling's top before step 3 (`first`, line 1263). By the end of step 4 the siblings have already
slid up with the collapsing card (the card's height and gap reach zero). Step 5 then measures `old - new`, which is the full distance,
snaps the siblings back to their old tops and slides them again: a visible jump back, then a second move. Fix for the build (plan Task
7.1): do steps 3 and 4 only (let the collapse move the siblings) and skip step 5 entirely. In Calm the collapse is 160 CALM and the
leave is 180 ease-in; they may overlap by starting the collapse at 100 ms if the owner wants it tighter, but the mockup runs them in turn.

### 2.5 The folded notes

- Button `.fold` (`all:unset`, flex, gap 6, margin-top 12, 12px `--ink-2`, pointer): `chevron-right` icon 14 + label.
  - Closed: **"Show 3 notes (nothing to fix)"**. Open: **"Hide 3 notes"**. Label swaps at once; `aria-expanded` toggles.
  - Chevron turns 90deg by CSS `rotate`, 280 ms SPRING (always, also in Calm; 264).
  - Build: count is the real number; hide the whole button at 0 notes.
- Notes box `#notes` (`hidden`, `overflow:hidden`). Each note (`.note`: flex, gap 10, align centre, padding 9px 2px, 12px `--muted`,
  1px `--line` bottom border) = `info` icon 13 + one plain sentence. Sample sentences, verbatim:
  - "Codex reads AGENTS.md in 2 projects."
  - "Cursor loads 2 rules from .cursor/rules."
  - "Developer kit has an update in the Community marketplace."
- Open (`fold` 480): box shown, height 0 → full and opacity 0 → 1, 280 CALM (Rich 460 SPRING); when it ends the notes rise (y 6, no blur,
  260 each, 40 apart). Close: height → 0 and opacity → 0, 220 ease-in, then hidden.
- Notes are sentences, not rows with buttons; no action on them.

### 2.6 "N more servers skip the gateway" card

- **Not in the mockup.** Only one such card exists: Dropbox, one server, one client. There is no aggregate or "N more" card, and no
  limit on how many cards a group shows. The build must decide this itself (suggest: one card per finding, same card shape; if more
  than a few, a "Show N more" fold using the same `.fold` pattern as the notes).

## 3. "Your setup" mini-map

- Right column. Caption `.ov-cap` **"Your setup"** (margin-top 0). Under it `.stage` (margin-top 4; shared stage: padding 6px 6px 10px 6px,
  margin-left -6px, overflow-x auto) holding `#omap`, a `MapView` of **470 x 250** (1241).
- Node layout (x, y, w x h), all in map pixels:

| Block | x | y | Size | Content |
|---|---|---|---|---|
| Claude Code | 0 | 22 | 160x54 | 28px tile, name 12px / 600, small line: lamp (green) + **"2.1.4"**, port on the right |
| Codex | 0 | 94 | 160x54 | tile, "Codex", lamp (green) + **"0.48"** |
| Cursor | 0 | 166 | 160x54 | tile, "Cursor", lamp (amber) + **"1.9 · not tested"** (text amber) |
| Kitden gateway | 250 | 40 | 220x60 | `house` itile 15, "Kitden gateway", lamp (green) + **"4 servers · 11 tools"**, faint `arrow-up-right` 14 at the right, port on the left |
| Library | 250 | 148 | 220x60 | `library` itile 15, "Library", lamp (green) + **"3 plugins · 6 skills"**, faint `arrow-up-right` 14, port on the left |

- Block look is the shared `.blk` (116): flex, gap 10, padding 0 12px, `--panel` fill, 1px line border, radius 8, hover border 38% accent
  (180 ms), press scale .98 (260 SPRING). Ports are 9px rings (`.port`, 130-133). The numbers "4, 11, 3, 6" are `.num` spans that count
  up (section 7).
- Each block is `tabindex 0`, `role button`, `aria-label` = its name (498). Keyboard Enter/Space is **not** wired on this map (the
  Gateway map has it at 707); add it.
- Links (`m.link`, default curve, from the client's right port to the block's left port, 1.2px `--wire`):
  - Claude Code → gateway, Codex → gateway.
  - Claude Code → Library, Codex → Library, Cursor → Library.
  - No Cursor → gateway link (Cursor is not connected). No dotted "faint" link exists on Overview: the dotted grey look
    (`.lk.direct`, 1.5/4 at .8, D8) is only used on Gateway for servers that skip the gateway. The only faint state here is the
    focus dimming (links `stroke-opacity .16`, blocks `opacity(.4) saturate(.6)`).
  - Links are not removable here (no hit paths, no ×).
- Foot (`.ov-foot`: flex, gap 6, 11px `--muted`, margin-top 8): `folder` icon 13 + **"4 projects · 1 has its own rules"**. In the build:
  "N projects · N have their own rules" with the right plural ("1 has", "2 have"). Static text, no click in the mockup.
- Clicks (`wire` 1257):
  - Kitden gateway → `go('gateway')`. Library → `go('library')` (page switch, M1).
  - A client → `m.focus([client, ...its link targets], its links)` and `m.beam`. No panel opens. Focus stays until the pointer enters and
    leaves a card.
- Hover on a mini-map block: only the shared border hover. Mini-map hover does not focus anything (unlike the Gateway map).

## 4. Changes timeline

- Page head via `head('Changes', lede, scope)` (1280):
  - h1 **"Changes"**; lede **"Every change made from this page. Each one has a backup; Undo puts the previous file back."**
  - Scope **"All projects · 5 changes this week"** (with a project picked: accent "Project <name>").
  - Entrance: h1 blur-in (Calm rise 260), lede and scope rise y 6 at 120 and 180.
  - Hint (1274): **"Click a row · Undo · See it on the map"**. No Map/List pill here, only the "Demo data" chip.
- Timeline wrapper `.tl` (margin-top 16, max-width 912).
- Day groups: label `.day` (11px `--muted`, margin 14px 0 6px) then a `.rows` list. Labels in the sample: **"Today"**, **"Yesterday"**.
  The mockup hard-codes these two. Build: "Today", "Yesterday", then a date for older days (e.g. "Mon 21 Oct"); date format is not in the
  mockup, so pick one plain format and pin it in a test.
- `.rows` (270): relative, column, gap 8, padding-left 22.
  - Rail `i.rail-line`: absolute, left 7, top 22, bottom 22, width 1, `--line`, `transform-origin: top`. One rail per day group, from the
    first row's middle to the last row's middle. Calm: static (no draw).
  - Dot `i.dot` per row: 9x9 circle, absolute left -19, vertical centre, fill `--canvas`, 1.5px `--wire` border. Selected row: dot fill and
    border `--accent` (no transition).
- Row (`.row`, 273): grid, columns `52px minmax(0,1fr) auto auto auto`, gap 12, height 46, padding 0 12, `--panel` fill, 1px line border,
  radius 8, pointer. Hover: border 38% accent mix, 180 ms ease. Selected: `--select` fill, accent border. `tabindex 0`; focus ring 2px accent,
  offset 2 (56). Parts:
  1. `time` 11px `--faint`, tabular figures ("14:02").
  2. Title `.t` 12px / 500, one line with ellipsis; holds an empty `i.strike`.
  3. Client tiles (`.who`, 20px tiles, gap 4).
  4. State (`.state`, 11px `--muted`, gap 6): 6px lamp + word. "Applied" = green lamp; "Undone" = grey lamp. The word sits in `span.sw` so it
     can roll. A failed row: amber lamp and the whole phrase **"Not applied: the file changed first"** in `--warn`.
  5. Action cell: **Undo** button (`.btn.sm`, `undo-2` icon 13 + "Undo") only on Applied rows; empty otherwise.
- Undone row look: `.row.undone .t` colour `--muted`; the strike line (`.strike`: absolute, left 0, right 0, top 50%, 1px, `currentColor`)
  shows at `scaleX(1)` (from left). Cancelled / failed rows get **no** strike in the mockup (only the amber state phrase); the owner's
  brief says "undone and cancelled": use the strike and muted title for Undone and for Cancelled; Failed keeps the amber phrase only.
- The first row is selected at mount without ripple (`select(0,true)`) and its Details panel loads at once.
- Narrow (900px or less, 399): columns `44px 1fr auto`, height auto, min-height 46; tiles and state hidden.

## 5. Change Details (the panel)

Shared panel shell (`.panel` 202: absolute, right 22, top 190, bottom 46, width min(320px, 100% - 44px), `--panel`, 1px line, radius 10,
padding 18, column, gap 16, shadow, scroll). Built by `panelLoad('Change', ...)` (1290): skeleton at once, real content after 160 ms (Calm),
children rise 20 ms apart (260). First open: panel in 240 CALM (opacity, translateX 28 → 0, scale .98 → 1). Another row: panel stays, back
to the skeleton, then loads again.

Content, top to bottom:
1. Kicker row `.p-kick` (11px `--faint`): **"Change"** and a close `x` (24px, aria-label "Close").
2. Title `.p-title` (17px / 600): the row title. Under it `.p-id` (11px `--muted`, sans font): **"Today 14:02"** (day + time).
3. Facts `dl.facts` (grid `94px 1fr`, gap 11px 8px, padding 12px 0, top and bottom 1px line, 12px; `dt` 11px `--muted`; `dd` flex gap 6):

| Label | Value, verbatim |
|---|---|
| Project | `folder` icon 13 + "mcp-gateway" (hard-coded in the mockup; use the change's real project, "All projects" when it has none) |
| State | lamp + **"Applied and checked"** (green) / **"Not applied"** (amber) / **"Undone"** (grey) |
| Backup | **"Kept · Undo puts it back"** (same for all rows in the mockup, even the failed one; a failed or undone row should say what is true, e.g. "None, nothing was written") |
| Takes effect | amber text (`.warn`): "Codex: start a new session", "Claude Code: start a new session", "Nothing to do", "Both: start a new session", "Try again from Gateway" |
| Clients | the client tiles (20px) + "2 clients" / "1 client" |

4. History `.p-hist` (flex wrap, gap 6, 11px `--muted`; spans `.on` = `--ink`): steps joined by an `arrow-right` icon 11. Sample steps:
   "14:02 Preview → 14:02 Applied → 14:02 Checked"; an undone row "11:15 Applied → 11:22 Undone"; a failed row
   "17:05 Preview → 17:05 Stopped: the file changed first". Arrows between steps only, none before the first. Calm: no fade-in of steps
   (Rich only: opacity .2 → 1, 300, from 420, 220 apart).
5. Actions `.p-acts` (column, gap 8, left aligned):
   - **Undo** (`.btn`, text only, `data-pundo`) on Applied rows only. Same flow as the row button (section 6).
   - **See it on the map** (`.btn`) when the row has a `map` target (only the first sample row, `['github',3]`). Click = `go('gateway',{open:'github',select:['github',3]})`:
     Gateway opens with GitHub unfolded and the tool "Push files" selected after the entrance. In the build, link to the page and
     item the change touched; show the button only when the change maps to one.
   - **Redo…** is not drawn in the Details panel; it lives only in the toast (D21). Offer it in the panel on Undone rows too, same
     behaviour (a fresh preview in the tray, never a direct write).
6. Foot `.p-tech` (margin-top auto, top line, 12px `--muted`): **"Technical details"** + `chevron-right` 14. In the mockup it is inert; in the build
   it opens the paths, backup file and commands (they must never be on the main list or the facts above).

## 6. Undo toast and the Undo flow

Undo (row button or panel button) (`undo` 1295):
1. Button: `pointer-events:none`, content = spinner (`rotate-cw` 13). Wait 600.
2. Row gets `.undone`. Strike line animates scaleX 0 → 1 from the left: **Calm 200 ms**, `cubic-bezier(.6,0,.2,1)` (STRIKE); Rich 420. The title
   turns muted at once (no transition).
3. Lamp loses `.on` (colour to grey, 400 ms ease, CSS 127). The state word rolls "Applied" → "Undone" (`roll`: out 140 ease-in, in 200 CALM; for
   words the roll goes down: old leaves toward +70%, new arrives from -70%).
4. The row Undo button: opacity 1 → 0, scale 1 → .8, 180 (default ease), then removed.
5. If this row is the selected one the panel reloads (`select(i,true)`: skeleton, then content with State "Undone", history gets the new line, no Undo button).
6. Toast (the shared dock toast, bottom left). Words, verbatim: **"Undid “Allow Push files in mcp-gateway”. The backup is back in place."**
   (curly quotes around the title) with the button **"Redo"** (`undo-2` icon 13 + label).
   - Toast shell: `.toast` 244: flex, gap 10, padding 9px 10px 9px 14px, `--panel`, 1px line, radius 10, shadow, 12px, no wrap. Green
     `circle-check` 16, text, buttons (`.btn.sm`), 2px green life bar at .7 opacity under it.
   - Timing (Calm): in 200 (opacity 0 → 1, translateY 14 → 0); life bar scaleX 1 → 0 linear over **9000 ms**, paused while the pointer is on the
     toast; at the end the toast leaves 160 ease-in (translateY 10). A new toast replaces the old at once. Clicking Redo also ends the toast.
7. Redo in the mockup (toast button): row state back to Applied at once (strike and muted title gone), lamp green (400), word rolls "Undone" → "Applied", the
   Undo button comes back (opacity 0 → 1, scale .8 → 1, 300). It writes nothing to the panel; the panel is not reloaded (stale if open).
   - **Build (D21):** the button reads **"Redo…"**; a click adds a fresh preview "Redo <title>" to the tray. The row stays Undone until that
     change is applied and verified; then the row returns to Applied (strike off, lamp green, word rolls, Undo returns, 300) and the panel reloads.
   - No "Undid" toast without the real undo having finished and verified (truth first).

## 7. Motion values (M8, Calm)

| Moment | Element | From → to | ms | Delay / step | Easing |
|---|---|---|---|---|---|
| Overview in | h1 | opacity 0 → 1, y 6 → 0 | 260 | 0 | CALM |
| | Lede, scope | same | 260 | 120, 180 | CALM |
| | Lede numbers 2, 3, 4 | count from 0 | 700 | 200, 260, 320 | OUT3 |
| | Mini-map numbers 4, 11 / 3, 6 | count from 0 | 900 | 500 / 560 | OUT3 |
| | 8 items in page order (3 captions incl. "Your setup", 4 cards, the fold) | same rise | 260 | 160, then 40 apart | CALM |
| | Mini-map (one piece) | same rise | 260 | 200 | CALM |
| Card hover | map focus / unfocus | dim blocks and links | 300 | 0 | ease |
| Fix flow | spinner | | 700 | | |
| | button green | fill | 180 | 0 | ease |
| | check draw | stroke draw | 300 | 0 | DRAW |
| | pause | | 150 | | |
| | card leave | opacity 1 → 0, x 0 → 28 | 180 | 0 | ease-in |
| | card collapse | height, padding, border → 0; margin-bottom 0 → -8 | 160 | 0 | CALM |
| | siblings slide (**skip in build**) | y old - new → 0 | 220 | 0 | CALM |
| | counter | roll | 140 + 200 | | ease-in, CALM |
| | undo returns the card | opacity 0 → 1, y -8 → 0, scale .98 → 1 | 220 | 0 | CALM |
| Notes | chevron | turn 90deg | 280 | 0 | SPRING |
| | box open | height 0 → full, opacity 0 → 1 | 280 | 0 | CALM |
| | notes rise | y 6 → 0 | 260 | 40 apart | CALM |
| | box close | height → 0, opacity → 0 | 220 | 0 | ease-in |
| Changes in | day labels and rows, 7 items in order | opacity 0 → 1, y 6 → 0 | 260 | 0, then 40 apart | CALM |
| | first row | selected at once, panel opens (240 in, 160 skeleton) | | | |
| Select a row | border, fill | to accent / select fill | 180 | 0 | ease |
| | panel | skeleton, then content, children rise | 160 wait, 260 each | 20 apart | CALM |
| Undo | spinner | | 600 | | |
| | strike | scaleX 0 → 1 | 200 | 0 | STRIKE |
| | lamp | grey | 400 | 0 | ease |
| | word | roll | 140 + 200 | | ease-in, CALM |
| | Undo button out | opacity, scale 1 → .8 | 180 | 0 | default |
| | toast | in 200, life 9000, out 160 | | | |
| Redo | strike and title | at once | 0 | | |
| | lamp | green | 400 | | ease |
| | Undo button in | opacity 0 → 1, scale .8 → 1 | 300 | 0 | CALM |
| Timeline insert after Apply | **no value in the mockup** (it has no way to add a row) | | | | |

- Timeline insert (the spec asks for it, the mockup has none): use the page's own rise for the new row at the top of "Today" (opacity 0 → 1,
  y -8 → 0, scale .98 → 1, 220 CALM, the same as the card's return), the rows below move by the layout change. Rail and dot appear with the row. Mark this
  as a build choice, not a mockup value.
- Rich-only parts left out: rail draw 700 DRAW, rows from -14px with blur 5 at 560, dot scale 520, ripple on select, history fade, beams, spark,
  card icon ripples.

## 8. Sample data

Overview: 4 cards (section 2.2), 3 notes (2.5), clients Claude Code 2.1.4 / Codex 0.48 / Cursor "1.9 · not tested", gateway 4 servers
11 tools, Library 3 plugins 6 skills, 4 projects, 1 with its own rules, 3 clients, 2 things need attention.

Changes (`Changes.rows` 1275-1279), time, title, clients, state, takes effect, history:

| # | Day | Time | Title | Clients | State | Takes effect | History |
|---|---|---|---|---|---|---|---|
| 0 | Today | 14:02 | Allow Push files in mcp-gateway | Claude Code, Codex | Applied | Codex: start a new session | 14:02 Preview, 14:02 Applied, 14:02 Checked; map = GitHub tool 3 |
| 1 | Today | 13:40 | Move Dropbox into the gateway | Claude Code | Applied | Claude Code: start a new session | 13:40 Preview, Applied, Checked |
| 2 | Today | 11:15 | Turn off Code review in mcp-gateway | Claude Code, Codex | Undone | Nothing to do | 11:15 Applied, 11:22 Undone |
| 3 | Yesterday | 18:20 | Add Developer kit | Claude Code, Codex | Applied | Both: start a new session | 18:20 Preview, Applied, 18:21 Checked |
| 4 | Yesterday | 17:05 | Connect Codex to the gateway | Codex | Failed | Try again from Gateway | 17:05 Preview, 17:05 Stopped: the file changed first |

Titles follow the pattern "<verb> <thing> in <project>"; with a project they name it, otherwise they do not.

## 9. Keyboard and accessibility

- Mockup: rows are `tabindex 0`; `keydown` handles **Enter** only (1283; add Space). Focus ring on rows and buttons: 2px accent, offset 2.
  Map blocks on Overview have `tabindex 0`, `role button` and an aria-label but no key handler. Cards have no handler; their button is a
  real `<button>`. The fold is a `<button>` with `aria-expanded`. The toast has `role status`. The close `x` has aria-label "Close".
- Build adds: Space on rows; Arrow Up/Down moves between rows; Escape closes the panel; `aria-current` or `aria-selected` on the selected row;
  the day group as a labelled list; lamp state as text (the state word is already visible, keep it); the strike line has no meaning on its
  own, so the state word carries "Undone"; focus stays on the Undo button's cell (or the row) after Undo; card hover focus also on keyboard
  focus; `prefers-reduced-motion`: every duration above becomes 0 (the mockup also sets CSS `transition:none; animation:none`, 406).
- Colour is never the only signal: lamp + word on every row; amber text always has words.

## 10. Differences to note

1. **Writes (D22).** Mockup cards fix in place and show "Fixed…" toasts; the build: card button adds a tray preview, Apply writes, the card collapses
   after the verified result. Undo of a fix is the tray toast's "Undo", not a card-only undo.
2. **Redo (D21).** Mockup "Redo" re-applies at once. Build: "Redo…" adds a fresh preview; the row changes only after Apply. Also the mockup
   has no Redo in the panel and no stale-panel refresh; add both.
3. **Sign-in words (D23).** Linear card "Needs sign-in. Its tools stay off until then." and the button "Sign in…", toast "Signed in to Linear": drop all.
   Replace with a card Kitden can truly show (e.g. a setup problem it found). No sign-in rows in Changes either.
4. **Unknown facts (D24).** Cursor's "1.9 · not tested" and the amber lamp ("not tested with Kitden") go; show only the version Kitden read
   and a plain "Not connected". Server and tool counts on the gateway block are fine (Kitden knows them); do not add counts for
   outside or marketplace servers.
5. **Paths and commands on main pages.** Note "Cursor loads 2 rules from .cursor/rules." shows a path; "Codex reads AGENTS.md in 2 projects." shows a file name.
   Write them as plain sentences ("Cursor loads 2 rules.") and put the file names behind Details. Change titles such as
   "Allow Push files in mcp-gateway" use a project name only (fine). "Technical details" must hold all paths, backup file names and commands.
6. **Hard-coded values.** Project always "mcp-gateway", Backup always "Kept", failed row says "Kept" too; wire from the real change record. "Takes effect"
   text is invented; take it from what Kitden knows (it must not claim a restart need it cannot know; D24).
7. **Dropbox card and Cursor card focus** light the gateway even though the point is that they skip it or connect to Library; fix as in 2.3.
8. **Collapse jump** (2.4): skip the sibling slide. **Empty group** and **all-clear** words are missing in the mockup.
9. **Demo data chip, "Rich" parts and "demo workspace"** in the scope bar are study-only. Scope in the build: "All projects · N clients" or
   "Project <name>".
10. **Project picker.** The mockup Overview ignores the picker; in the build the lede counts, cards and the foot should follow the picked project
    (or the scope bar states plainly that Overview is for all projects).
11. **Timeline insert** has no mockup value (section 7); **older day labels** are undefined (section 4).
12. **"See it on the map"** exists only on one sample row; build it for every change that has a map target and nowhere else.
