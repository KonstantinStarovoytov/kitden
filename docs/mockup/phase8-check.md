# Phase 8 check: the page beside the mockup

Checked 2026-10-27 on the large demo (`uv run kitden demo --size large`) beside
`design/kitden-motion.html`, at 1440 × 900, light and dark. Frames were compared by screenshots and
by the sizes the browser measured; motion by the times and curves each animation was started with
(read in the page), with `?slow=4` for a look by eye. The demo's data differs from the mockup's
(names, counts, the 154 servers outside the gateway); only looks and motion count here.

Each line says "matches", "fixed in <commit>" or "left: <why>". A left line that is new is in
ROADMAP.md "Next".

## Frames

- Shell (rail, top bar, hint line): matches. The "Demo" tag and the scan time are Kitden's own.
- Overview, cards and "Your setup": fixed in 404aafa (the page used 1180 px, so the cards were
  616 px; now 690 px as in the mockup).
- Overview, "Fix…" and "Sign in…" as primary buttons: matches (decided: D22, D23 in
  overview-changes-notes; the demo shows no fix card).
- Overview, client tiles in light: left: the mockup's tiles are its dark images in both themes;
  Kitden's marks follow the theme. Owner to judge.
- Gateway map, blocks, captions and links: matches (every block on the mockup's x and y).
- Gateway map, "+ Add": fixed in cf6135a (it had no edge or fill).
- Gateway map, the count stays while a server is open: matches (decided: the owner's count
  button, design.md Gateway map).
- Gateway List: fixed in 5e0d967 (no frame, a line under each row, names in Inter, as the
  mockup's list).
- Gateway List, Clients group and the gateway row: matches (decided: design.md Gateway List).
- Gateway List opens past 15 servers: matches (decided: design.md, `view` in the address).
- Details panel, place and size: matches (320 px, 22 px from the right; its top follows the map's
  top, design.md Details beside the page).
- Details panel, actions: fixed in 7fa9842 (they were full width; now as wide as their words).
- Details panel, head: left: the kind is in capitals with a "Close" word; the mockup has the kind
  in sentence case and a 24 px ×. It touches every panel and their tests (ROADMAP Next).
- Details, "Technical details" and "More": matches (decided: D18; a single other action shows
  without More, Phase 7 notes).
- Tray bar: matches (380 px, padding, edge, words). "Show changes" is Kitden's (decided: Phase 3).
- Toast: matches (size, words, Undo).
- Add panel: matches, but for the head (left: as Details' head above). The pill is All · Remote ·
  Local (decided: Phase 5 notes).
- Library map: matches (columns, caption, plugin cards, Inside column).
- Library map, Map | List at the right edge: fixed in 404aafa.
- Library List: fixed in 5e0d967 (the same tree grid as the Gateway's). No List in the mockup.
- Instructions map: matches (decided groups "All projects", "Commands and agents": Phase 6B notes).
- Changes, rows, timeline, selected row: matches.
- Changes, lede: fixed in eb815c1 (it wrapped at 70 ch; the mockup's takes one line).
- Changes, rows keep room for Details: matches (decided: design.md Details beside the page; the
  mockup's rows run under the panel).
- Changes Details, history: left: Kitden lists the steps as a fact, one per line; the mockup shows
  them as one line under the facts (ROADMAP Next).
- The hint line over a tall map or list: matches (the mockup's line sits on the page the same way;
  its pages are short). Known: Phase 1 notes.
- Light and dark: matches in every frame above (tokens and contrast from Phase 1).

## Motion (M1–M8)

- M1 page switch: matches (title 260 CALM, lede +120, scope +180, nav marker 300 CALM; the head
  waits the old page's 120 ms on the Gateway).
- M1 map entrance: matches (6 px, 260 OUT3, 22 ms apart). Kitden ends a long map's wave by 440 ms
  (design.md Map entrance).
- M1 pill: matches (280 CALM).
- M1 Map ↔ List: matches in both themes (out 120 ease-in up 4 px, in 260 CALM from 6 px; no flash
  of another fill between them).
- M2 select: matches (accent lines 180 CALM on every lit link, the tool links too; dimming 300).
- M2 Details: matches (open 240 CALM from 28 px and .98, parts rise 260, 20 ms apart; close 180).
- M2 server unfold and fold: matches (links 170, tools 120 OUT3 15 ms apart, fold 180, moves 260).
- M3 links: matches (× in 120, grace 240, draw 260/240/480, fade in 300, fade out 240, undraw 380,
  blend 300).
- M4 tray: matches (bar 220 CALM, row 200 after 80, row out 180, bar out 160, resize 200, meter
  480 ease-out, check 300 DRAW, toast 200 in, 160 out, life 9 s, landings 60 apart, Undo all
  120 apart). The steps follow the real write, not a 560 ms clock (decided: D20).
- M4 failure: not run (it needs a write that fails); the shake is 380 ease-out.
- M5 drags: matches by their times (home 220 OUT3, slot 220, drop target 1.05). Not driven here.
- M6 add panel: matches (rows that match again 240 CALM from −4 px).
- M6 project menu: fixed in e1598ce (its items now rise 260 CALM together; menu 180 CALM in,
  140 ease-in out, as before).
- M6 project switch: matches (scope 320 from 4 px, counts roll, marks pop 200).
- M6 find: matches (.3, saturate .5, blur 1.2 px).
- M7 Library: matches (fold back 160 IN3, unfold 220 OUT3 15 ms apart, moves 260).
- M8 Overview entrance: matches (cards from 160 ms, 40 ms apart; the map at 200; lede numbers count
  up 700 OUT3 at 200, 260, 320).
- M8 Overview, setup map numbers: left: they do not count up (mockup: 900 ms OUT3 at 500 and
  560 ms) (ROADMAP Next).
- M8 card leave, collapse, slide, notes: matches (180 ease-in, 160, 220, notes 280 in, 220 out).
- M8 "Move in…": matches (decided: D22, it adds a preview instead of the lit look for 1600 ms).
- M8 Changes: matches (rows 260, 40 ms apart; strike 200 STRIKE; lamp 400; Undo out 180). Redo is a
  fresh preview (decided: D21).

## The large Gateway map

The large demo's map: 12 servers in the gateway and 154 outside, paged five at a time; 22 blocks and
72 links drawn (27 and 87 with a server open). Headless Chrome 156, 1440 × 900 at 2×:

- Select a server, three times: no long task over 50 ms. Each draw of the map took 1.8–9.9 ms.
  Chrome logged long animation frames of 108–134 ms with no blocking time (no task over 50 ms; the
  headless browser has no display, so its frames come slowly).
- Glance (the pointer over a client, then across the map), three times: no long task, no long
  frame.
- The same in the app's own browser pane: no long task; draws 3.9–11.5 ms. Its pane was hidden, so
  its numbers are rough.

Nothing to fix.

## Owner to check in Safari

These cannot be driven from here:

- Tab to a map link: it takes its hover look and its ×.
- The project menu: opened by the mouse it shows no ring on the picked row; opened by Down or Enter
  it does.
- The README hero: the smoke's blur.
