# Library page in the mockup: notes for the build (Calm only)

Sources read in full: `docs/mockup/kitden-motion.html` (v11) `Library` (1058-1229), `motion-spec.md` M7 (and the Library lines in
M0-M6), decisions D23-D28 in `docs/superpowers/plans/2026-10-24-mockup-alignment.md`. Line numbers are in `kitden-motion.html` unless
marked. "Calm" = `S.rich` false. `D(ms)` = 0 under reduced motion. Default Web Animation ease = CALM `cubic-bezier(.2,.8,.2,1)`, fill
`backwards`, default 300 ms. OUT3 = 1-(1-t)^3 (`E.out`), IN3 = t^3 (`E.in`). Map tweens use OUT3 in Calm.

| Thing | Function / CSS | Line |
|---|---|---|
| Sample data | `LBD`, `LCLIENTS`, `lname` | 1059-1064 |
| Mount, head, tabs | `Library.mount`, `head()` | 1067-1069, 1303 |
| Layout, block HTML, links | `layout` 1071, `spec` 1076, `linksFor` 1087, `build` 1092 | |
| Tab / unfold move | `relayout` 1093, `origin` 1100, `enter` 1101 | |
| Click, hover, keys, List button | `wire` | 1106-1119 |
| Link x and Connection panel | `hookLinks` 1120, `previewKey` 1121, `linkTip` 1124, `linkRemove` 1125, `linkClick` 1127, `linkPanel` 1129 | |
| Remove / turn off (tray rows) | `removeFrom` 1134, `offSkill` 1140 | |
| Select | `unsel` 1147, `client` 1150, `plugin` 1154, `lightPlugin` 1159, `select` 1208, `skill` 1215, `file` 1220, `imp` 1224 | |
| Plugin Details, checklist | `pluginPanel` 1160, `wirePlugin` 1166, `pickClient` 1169, `syncLibPicks` 1177 | |
| Add (tray) | `add` 1179, `refreshItem` 1190 | |
| Drag | `dropWhy` 1193, `dragStart` 1194 | |
| Find | `filter` 1227 (= `Gateway.filter` 1055) | |
| Block / link / panel CSS | `.blk` 116-121, `.srv` 136-139, `.tool` 146-148, `.mark` 149-151, `.lk` 163-171, `.edge-x` 377-380, `.panel` 202-216, `.pick` 302-309, `.dragtip` 319 | |
| Map engine, panel helpers, tray | `MapView` 484-526, `openPanel`..`closePanel` 531-539, `tray` 606-642 | |

Shared pieces (panel shell, tray, toast, link x, shake) are the same as in `gateway-notes.md` and `add-notes.md`; this file only
repeats what is Library-specific.

## 1. Page head

- Built by `head('Library', lede, scope, true, tabs)` (1303). Title `h1` "Library" (24px / 600, blur-in). Lede (12px `--muted`, margin-top 4):
  **"Follow the source. Connect only what you need."**
- Tabs (`.seg.sm`, id `ltab`, margin-top 12, `width:max-content`, 11px, buttons padding 3px 8px): **"Plugins and skills"** (pressed
  at start) | **"Instructions"**. The raised mark starts in place (`segGlide(...,true)`), then glides 280 CALM on a click.
- Scope bar (`.scope`, margin-top 12, 11px `--muted`): `layers` icon 14 + **"Shared setup · project overrides stay separate"**. With
  a project picked: accent class, `folder` icon + **"Project <name>"**. The Library has no `project()` hook, so a project change only
  rewrites this line; the map does not change (setProject 1333).
- Right of the head (`.head-acts`): `Map | List` pill (`#viewseg`, 12px buttons, Map pressed). The "Demo data" chip is study-only.
- Entrance (`go`, 1310): `h1` blur-in; lede and scope rise (y 6, delay 120, step 60). Tabs have no entrance of their own.
- Hint line (bottom of the page, 11px, `info` icon 13), verbatim: **"Point at a link and press × to remove it · drag a plugin onto
  a client to add it there · + adds it for all projects · click anything for its Details"** (1066). The right-hand tag
  "Library · motion study · demo data" is study-only; do not build.
- `Library.unmount` calls `tray.discard()`: leaving the page drops every row still in preview.

## 2. Plugins and skills map

Map host `#lmap`: `MapView` 740 x 420 inside `.stage` (margin-top 22, padding 6 6 10 6, margin-left -6, scrolls sideways).
Blocks are absolutely placed (`x, y, w, h`), links are SVG paths from the right port of A to the left port of B (cubic curve,
control offset `max(18, |dx| * .5)`), stroke 1.2 `--wire`.

### 2.1 Layout (`layout`, 1071-1074)

| Column | x | What | Size | y |
|---|---|---|---|---|
| Clients | 0 | caption "Clients" | 150 x 18 | 0 |
| | 0 | 3 client blocks | 150 x 54 | 140, 212, 284 (72 apart) |
| Plugins and skills | 250 | caption "Plugins and skills" + inline `+ Add` button | 200 x 26 | -4 |
| | 250 | group caption | 200 x 18 | first at 37, then +24 below it |
| | 250 | plugin card | 180 x 60 | gap 4 under each card, +15 after a group |
| | 250 | slim skill row | 180 x 34 | same |
| Inside | 500 | caption "Inside" | 150 x 18 | 0 |
| | 500 | inside item | 200 x 34 | 42 apart, the stack centred on the plugin's middle (`y + 30`), top never above 26 |

Resulting y with the sample data: Community caption 37, Developer kit 61, Docs writer 125; Team caption 204, Design tools 228; Your
skills caption 307, Release notes 331. Developer kit's four inside rows sit at 26, 68, 110, 152.

- Group captions (`.cap.grp`: 11px / 600 `--ink-2`, icon 13): **"Community marketplace"** (`store`), **"Team marketplace"** (`store`),
  **"Your skills"** (`user-round`). Column captions (`.cap`, 11px `--muted`): **"Clients"**, **"Plugins and skills"**, **"Inside"**.
  No counts and no "N more" anywhere: the sample has 4 plugins and 1 skill, and nothing pages or collapses.
- Caption button `+ Add` (`btn xs`, `plus` icon 12, text "Add", `data-add`). In the mockup it always previews "Design tools" for
  Claude Code and Codex; it opens no panel. See section 11.

### 2.2 Client block (`spec`, `k==='c'`)

`.blk.client` 150 x 54: tile image 28 (`tile(id)`), `<b>` name 12px / 600, small line: lamp (green when on) + state word. States in
the sample: **"Connected"** (Claude Code, Codex), **"Via Claude Code"** (Cursor). Port on the right. Hover on a client with nothing
selected and no drag: focus on it, its items and its links (others `filter:opacity(.4) saturate(.6)`, links stroke-opacity .16).

### 2.3 Plugin card (`k==='i'`, not a skill), class `blk srv`

- `.itile` (28 x 28, `puzzle` icon 15) + name (`<b>`) + one small line. Left port always; right port only when the plugin is open
  (see 3.1); a round **count badge** (20 x 20, 10px, at right -10, centred) shows the number of inside items and fades (opacity 0, scale
  .3) while the plugin is open. Badge hidden for a plugin that is not added.
- Small line, by state:
  - On: green lamp + **"3 of 4 on"** (number in `.num`). D25 replaces this with **"4 items"**; the lamp is green if the plugin is on in
    at least one client.
  - Not added: grey lamp + **"Not added"**, and a `btn xs` `+` button (margin-left auto, `aria-label="Add <name> for all projects"`).
  - In preview: `lamp pv` (transparent, dashed accent ring 1.5px) + accent **"Preview · Codex"** or **"Preview · for all projects"**.
    Block gets `.preview` (dashed 1px `--preview-line`, `--preview-fill`), `title="In preview. Click to take it out."`, and a hover/
    focus-visible `×` badge (`.unx`, 18 x 18, at top -8 right -8, accent border, opacity 0 scale .5 -> 1).
- Open plugin: `.srv.open` accent border. Selected: `.blk.sel` select fill + accent border, ports accent.
- Block base: padding 0 12, gap 10, 1px `--line`, radius 8, hover = 38 % accent in the border, press scale .98.

### 2.4 Slim skill row (`it.skill`)

`blk tool` 180 x 34 (padding 0 10, gap 9): `.mark.on` dot (6px, `--ok`), name 12px, right-aligned kind **"Skill"** with `sparkles` 11
(10.5px `--faint`). Left port only. Standalone skills are draggable and clickable like plugins; they cannot be opened.

### 2.5 Inside item (`k==='k'`)

`blk tool` 200 x 34: `.mark` (green if the plugin is added and the item is not off; grey otherwise), name, kind with icon:
**"Skill"** (`sparkles`) or **"Command"** (`square-terminal`). Left port only. Names in the sample: "/ship" is the only Command.

### 2.6 Link kinds (`linksFor`, 1087-1091; CSS 163-171, 315-317, 374)

| Class | Look | Used for |
|---|---|---|
| (none) `L~client~item` | solid `--wire`, 1.2 | client has the plugin or skill |
| (none) `L~k~plugin~i` | solid | plugin -> inside item |
| `preview` `P~client~item` | dashed 4 4, accent, opacity .65 | add in the tray |
| `preview leaving` | dashed, `--muted`, opacity .4 | a removal in the tray; also all inside links of a plugin that is not added |
| `preview on` `L~drop` | dashed accent | the temporary wire while dragging |
| `.on` | accent, 1.7 | lit path |
| `.hov` / `.picked` | accent, 2.4, opacity 1 | pointer on it / its Connection panel is open |
Rich-only marching dashes (`@keyframes march`) are not built (D28).

### 2.7 Entrance (`enter`, 1101-1104, Calm)

All blocks (17: Clients caption, 3 clients, Plugins caption, 3 captions + 4 cards/rows, Inside caption, 4 inside items: layout
order) start at y + 6, opacity 0, then move to place with opacity 1: 260 OUT3, stagger 22 (ends at 612). Links draw with their nodes
(no beam in Calm).

## 3. Select, unfold and Details

State: `st.open` (the plugin whose Inside column is shown; starts as `devkit`, nothing selected) and `st.sel` (one thing at a time).
`unsel` (1147) clears `.sel`, unfocuses the map, closes the panel (out 180 ease-in). Every select starts with `unsel`; clicking the
same thing again only deselects. A click on empty map (not a block, not a button) also calls `unsel`. The click handler is 1107-1114.

### 3.1 Click a plugin (`plugin`, 1154-1158)

1. `unsel`. If it was the selected plugin and it is open: fold it (`st.open = null`, `relayout`), done.
2. Else: block gets `.sel`. If it was not open, `st.open = a`, `.srv.open` moves, and `relayout()` runs; the path lights after it ends.
   If it was already open (the sample starts with Developer kit open), the path lights at once.
3. `relayout` (1093, Calm): blocks that stay move 260 OUT3; new inside rows and caption start at (plugin x + w - 100, plugin middle - 17),
   scale .3, opacity 0, and grow to place, 220 OUT3, 15 apart; old inside rows go back into the old plugin the same way, 160 IN3,
   then are removed. (Quirk: the "Inside" caption always folds into Developer kit.)
4. Path lit (`lightPlugin`, 1159): `lit` = groups [client -> plugin links] and [plugin -> inside links]; lit nodes = those clients, the
   plugin, its inside rows; everything else dims (`filter:opacity(.4) saturate(.6)`, 300). Lit links get `.on` (accent 1.7) and an
   overlay path that fades in 180.
5. Panel `Plugin` opens through `panelLoad` (skeleton, then content after 160 ms, children rise 260 / 20 ms apart, y 6). Panel
   `dataset.for = 'i~<id>'`.

A not-added plugin that has a pending add is a different click: it takes **all its tray rows out** (`lib~<id>~*`), nothing else (1111).

### 3.2 Plugin Details (`pluginPanel`, 1160-1165)

Top to bottom (panel shell as in `add-notes.md` 1; width min(320, 100% - 44), right 22, top 190, bottom 46):
1. Kick row: **"Plugin"** + `×` (`aria-label="Close"`).
2. Head: `.itile` (puzzle 15) + title (17px / 600) + id line = the source name (e.g. **"Community marketplace"**).
3. Facts (`dl.facts`, columns 94px / 1fr, row gap 11, border top and bottom):
   - **State**: lamp + **"On"** / **"In preview"** (dashed lamp) / **"Not added"**.
   - **Inside**: **"3 skills · 1 command"** (singular "1 skill"; the command part only when there is one; plural "commands").
   - **Clients**: client tiles (20 px) + names joined by ", ", or muted **"None yet"**.
   - **Comes from**: **"All projects"** or muted **"Not added"**.
4. Say line (`.p-say`, 12px `--ink-2`). On: **"Claude Code and Codex load it in every project. Cursor gets it through Claude Code."**
   (names come from `it.by`). Not added: **"Not added yet. Drag it onto a client to add it there, or add it for all projects."**
5. Actions (`.p-acts`, column, gap 8):
   - Added: primary **"Add to Codex…"** (or **"Add to Claude Code or Codex…"** when both lack it; hidden when none lacks it), then
     **"Turn off for all projects…"** (plain; no handler in the mockup).
   - Not added: primary `+` **"Add for all projects…"** (only if both clients lack it) and **"Add to one client…"** (if any lacks it).
   "Lacks it" = in neither `by` nor `pend`, over Claude Code and Codex only (Cursor is never offered).
6. Foot row (`.p-tech`): **"Technical details"** + `chevron-right` 14. It has no content in the mockup (Kitden puts paths, commands and
   file lines here).
`refreshPlugin` re-renders the open panel after every add, remove or undo, unless the checklist step is showing.

### 3.3 "Add to <client>…" / "Add to one client…" checklist (`pickClient`, 1169-1176)

- Panel steps forward (`swapPanel`, old content out 130 ease-in with a -18 px slide, new in 220 from +22 px).
- Kick: `arrow-left` button (`aria-label="Back"`) + crumb **"Plugin · Developer kit"** + `×`. Title: **"Add Developer kit"** `<br>`
  **"to the clients you pick"**. Say line: **"You can also drag Developer kit onto a client on the map."**
- Rows (`.pick.multi`, `role="checkbox"`, `aria-checked`): client tile, name, note, a 16 px box (`.chk`, 4 px radius). All three clients
  are listed. Notes: **"Not added"** (free), **"Has it already"** (disabled), **"Gets plugins through Claude Code"** (Cursor, always disabled).
  Disabled rows: opacity .45, `disabled`. Footer button **"Done"**.
- Tick = `add(a,[client])` (a tray row); the row takes select fill + accent border (180), the box fills (200), tick fades in (160) and
  scales .5 -> 1 (320 SPRING), box pops .6 -> 1 (160 CALM, not on first draw), note becomes **"In preview"**. Untick = `tray.remove`.
  `syncLibPicks` keeps boxes in step with the tray when a row is removed from the tray bar.
- Done / Back: `reopenPlugin(a,'back')` (panel steps back, slide from -22). Apply with the checklist open: steps back by itself.

### 3.4 Click an inside item (`select`, 1208-1214)

Item gets `.sel`; path = client -> plugin links, then plugin -> that item (plugin stays open). Panel kick = **"Skill"** or **"Command"**,
title = the name, id line = snake-case-with-hyphens of the name (e.g. "code-review"), facts **Plugin** (puzzle + name), **State**
(green mark **"On"** or **"Comes with the plugin"** when the plugin is not added), **Comes from** (**"All projects"** / **"Not added"**), **Source**
(the marketplace name), **Clients** (tiles + "N client(s)"). Say: **"Claude Code and Codex load this skill in every project. Cursor gets it
through Claude Code."** or **"It comes with Developer kit, which is not added yet."** Actions: **"Turn off for all projects…"** and
**"Turn off in one project…"** (no handlers); not added: primary **"Add Developer kit for all projects…"** (adds for Claude Code and
Codex). D25 replaces all of this: no switch or turn-off button; the panel says **"Follows its plugin"**.

### 3.5 Click a standalone skill (`skill`, 1215-1219)

Skill gets `.sel`; path = client -> skill links. Panel kick **"Skill"**, title name, id line (snake-hyphen, "release-notes"). Facts:
**Plugin** muted **"None, a skill on its own"**, **State** green mark **"On"**, **Comes from** **"All projects"**, **Source** (`user-round` +
**"Your skills folder"**), **Clients** (tiles + **"2 clients"**). Say (study chatter, do not copy): "The same kind of thing as Code review inside
Developer kit. It sits in the second column because it comes straight from your skills folder, not from a plugin. Drag it onto Codex to add
it there." Actions: **"Turn off for all projects…"**, **"Turn off in one project…"**. The mockup has no project choices and no handlers
for these two buttons; the project step must come from Gateway's "Turn on in some projects…" checklist (D13, `gateway-notes.md`),
one tray row per ticked project.

### 3.6 Click a client (`client`, 1150-1153)

Client gets `.sel`; its links and their items light. Panel kick **"Client"**, head (tile, name, state word), section **"Loads in every
project"** (`.sw-head` 11px / 600) with a bordered list (`.sw-list`, rows 8px 10px, `.itile` 24 px): name, small line **"Plugin · 4 inside"**
/ **"Skill"** / **"File"**; empty: **"Nothing yet"**. Say: Cursor **"Cursor has no plugins of its own here. It loads skills through Claude
Code."**, others **"Drag a plugin onto this client to add it here."** Then "Technical details".

## 4. Drags (`dragStart`, 1194-1207; `dropWhy`, 1193)

- Only a block with id `i~...` drags: plugin cards and standalone skills (not clients, not inside rows, not files). Not from a button.
  Primary button only. Pointer capture on the block.
- Start after 5 px of movement. Then: block gets `.lift` (shadow, accent border, grabbing cursor, z-index 5); `unsel` (panel closes);
  focus on the block and all 3 clients, no links on; a tip (`.dragtip`) is added to the map layer.
- Move: the block follows the pointer (x, y). Calm: no rotation, no scale. Target test in map coordinates: pointer x in
  (client.x - 24, client.x + w + 40) and y in (client.y - 16, client.y + h + 16).
- Tip (`.dragtip`: padding 3px 9px, radius 10, 11px `--muted`, panel fill, 1px `--line`, shadow; at block x + 6, y - 28). Words:
  - no client under the pointer: **"Drop on a client"**
  - allowed client: **"Add to Codex"** (class `.on`: select fill, accent border, accent text)
  - blocked client: the reason, in the plain style (below)
- Allowed client: client gets `.blk.drop` (accent border, select fill, scale 1.05), and a temporary dashed wire `L~drop` (class
  `preview on`) from the client to the plugin. Blocked or none: no target look, no wire.
- `dropWhy` order and words (exact): Cursor -> **"Cursor gets plugins through Claude Code"**; client already has it -> **"Already in
  Claude Code"** (name of the client); already in the tray for that client -> **"Already in preview"**; otherwise allowed. The Cursor
  line is the same for a standalone skill (the code does not tell them apart).
- Release (`up`): tip removed, focus released, temporary wire removed, then the block always flies back to its layout place, 220
  OUT3 (rotation 0). Blocked target: that **client shakes** (`shake`: translateX 0, -7, 6, -3, 0 over 380 ease-out). Allowed: `add(a,[client])`.
  A drag that moved sets `this.dragged` for one tick so the click that follows is ignored. A press that did not pass 5 px is a click.
- `add` (1179): if nothing is left to add the block shakes. Otherwise the block takes the preview look and a **dashed accent link**
  client -> plugin fades in 300 CALM (the second client's link 90 ms later); the Details panel (if this plugin's) re-renders.
- "+" on a not-added card, "Add for all projects…" and the caption "Add" button: `add(a,['claude','codex'])`, two preview links,
  block says **"Preview · for all projects"**.
- Nothing else drags. Keyboard has no drag (the checklist in 3.3 is the route).

## 5. Link x (`hookLinks`, 1120-1133; engine 484-500)

- Only these links take the pointer (`canHit`): client -> plugin or skill (`L~claude|codex|cursor~...`), plugin -> inside item
  (`L~k~...`), and preview links (`P~...`). A 14 px invisible stroke over the link takes the pointer (off while the link is below .5 opacity).
- Point at a link: it turns accent 2.4 (`.hov`), and a round `×` (`.edge-x`, 16 x 16, accent border, panel fill, 10 px icon, hover fill
  accent) fades in (120 ms) at the middle of the path. It stays 240 ms after the pointer leaves, so it can be reached. Its hit area is 6 px
  larger on every side. Tooltip and `aria-label` = the words below.
- Words (`linkTip`, 1124): client -> plugin or skill **"Remove Developer kit from Codex"**; plugin -> inside **"Turn off Code review in Developer kit"**;
  preview link **"Take it out of the preview"**.
- What × does (all go to the tray; nothing is written until Apply):
  - preview link: `tray.remove` the matching row (`lib~...`, `libk~...` or `librm~...`).
  - client -> plugin or skill (`removeFrom`, 1134): link becomes the leaving look (dash 300). Row: icon `x`, title **"Remove Developer kit
    from Codex"**, detail **"Codex stops loading it and the skills inside. Other clients keep it."** (a skill: "...stops loading it.
    Other clients keep it."), who "Codex's settings". Lands: link undraws; if no client keeps a plugin, it becomes "Not added" with the `+` button and its inside links
    switch to muted dashes. Undo: link draws back, 480. Toast **"Removed Developer kit from Codex"**.
  - plugin -> inside (`offSkill`, 1140): row `toggle-right` **"Turn off Code review in Developer kit"**, detail **"Claude Code and Codex stop loading it. The
    rest of Developer kit stays."** Toast **"Turned off Code review in Developer kit"**. **D25 removes this: those links are not hittable
    and have no ×.**
- Click the link itself (not ×): link becomes `picked` (accent 2.4, × stays), focus on its two ends, panel **Connection**
  (`linkPanel`, 1129): kick "Connection"; title **"Claude Code → Developer kit"**; id line **"Loaded by the client"** / **"Inside the plugin"**;
  facts **From**, **To**, **State** (**"In preview"** dashed lamp / **"In place"** green), **Written in** (**"Claude Code's settings"**); say: **"Claude
  Code loads Developer kit in every project."** / **"Code review is on inside Developer kit: every client that loads Developer kit gets it."**
  / for a preview **"This link is a change in preview. Nothing is written until you Apply."**; button `x` + the tip words + "…" (or
  **"Take it out of the preview"**); foot "Technical details". Click again: deselect.
- Read-only: instruction links (`L~f~`, `L~m~`) are not hittable at all: no hover, no ×, no click. The `L~drop` wire is not hittable.

## 6. Instructions tab

Switch (`#ltab` click, 1118): the pill glides, `unsel`, `st.tab` changes, `relayout()` runs, then Rich-only beams (none in Calm).
`relayout` in Calm: clients and "Clients" caption stay and move (260); leaving blocks (plugin column and Inside column) go to x 150, own y,
scale .4, opacity 0, 160 IN3, then removed; arriving blocks start at x 150, y 200, scale .4, opacity 0 and grow to place, 220 OUT3, 15 apart.
Open plugin (`st.open`) is kept for the way back.

Layout (`layout`, 1073): caption **"Files"** (250, 0, 150 x 18); caption **"Imports"** (500, 0, 150 x 18); file cards at x 250, y 140 + 72 i,
190 x 54; import blocks at x 500, y 150 + 56 i, 200 x 40.

- **File card** (`f~`): `.itile` (`file-text` 15), name in mono 12px / 500, small line: green lamp + meta: **"Claude Code · this project"**,
  **"Codex · all projects"**, **"Cursor · 2 rules"**. Ports left and right. Link: owning client -> file (`L~f~<id>`).
- **Import block** (`m~`, `blk tool` 40 high): `scroll-text` 13 + name in mono 11px: **"docs/design.md"**, **"docs/development.md"**. Port left. Link: file -> import
  (`L~m~<file>~<import>`) for each import a file lists.
- Click a file (`file`, 1220): `.sel`; lit = [its client link] + [its import links]; lit nodes = client, file, its imports. Panel kick
  **"Instruction file"**; title mono 15px (file name); id line = meta; a code box (`.p-lines`: mono 11px / 1.6, `--inset`, 1px `--line`,
  radius 6, padding 10 12) with placeholder lines ("# Working on the demo project", ...); say **"Kitden only reads this file. It brings in 2
  more."** (or **"It imports nothing."**); "Technical details".
- Click an import (`imp`, 1224): `.sel`; lit = links into it; lit nodes = it + the files that bring it in (not the client). Panel kick
  **"Imported file"**; title mono 15px; id line **"Brought in by CLAUDE.md and AGENTS.md"**; code box (placeholder); say **"Kitden only reads it."**
- Click a client here: same as 3.6 (it lights its file links).
- Sample wiring: Claude Code -> CLAUDE.md -> docs/design.md, docs/development.md; Codex -> AGENTS.md -> docs/development.md; Cursor ->
  .cursor/rules -> nothing. (D27: the Codex file gets no import link.)
- Nothing here is changeable: no ×, no drag, no add button, nothing enters the tray.

## 7. List view

**The Library has no List view in the mockup.** The `Map | List` pill is drawn, but a click on **List** (1117) only runs `shake(#viewseg)`
(380) and shows the toast **"In this mockup the List view is on Gateway."** (no Undo; the toast auto-closes after 9 s, bar `scaleX 1 -> 0`;
pauses on hover). The pill stays on Map. There is no "Differences" filter and no "Add missing" in the mockup. Plan Task 6.6 and the owner's
2026-10-23 ruling keep both "in the new look", so the planner must design the Library List from the Gateway List, not from this file.
What exists to copy (Gateway, 1020-1048; CSS 190-199):
- Grid `minmax(0,1fr) 130px 150px 100px`, gap 12, padding 0 12. Header row 30 (11px `--muted`, bottom border). Group rows 30
  (`.lg`: 11px / 600 `--ink-2`, icon 13). Rows 40, sub-rows 34 indented 44; row border-bottom 1px `--line`; hover `--dim` (180); selected
  `--select`. Cells: name (+icon), "Used by" client tiles (20 px), a state cell, an end cell (button or chevron).
- Swap between Map and List in Calm: map fades out 120 ease-in with a -4 px slide, list in 260 CALM from +6 px. Selection is cleared
  and the tray stays.
- Find (`#find`, top bar) works on the map only: `filter(q)` (1227) toggles `.find` on the map host; a block whose `data-name` does not
  contain the text gets `filter:opacity(.3) saturate(.5) blur(1.2px)`, links stroke-opacity .2; 300 ease. Captions stay. Empty text = back.
  Clients, plugins, skills, inside rows, files and imports all have a name. A page switch clears the field.

## 8. Apply and Undo words, tray rows for Library changes

Every Library change is `tray.add({key, icon, title, detail, who, onRemove, onCommit, onUndo, toast})` (606-642). Keys: `lib~<id>~<c1+c2>` (add),
`librm~<id>~<client>` (remove), `libk~<id>~<i>` (turn off an inside item; D25 drops it).

| Change | Icon | Title | Detail | Toast (with Undo) |
|---|---|---|---|---|
| Add to one client | `plus` | "Add Developer kit to Codex" | "Only Codex. The other clients stay as they are." | "Added Developer kit to Codex" |
| Add for all projects | `plus` | "Add Design tools for all projects" | "Claude Code and Codex get 2 skills. Cursor gets them through Claude Code." (a plugin) / "...get it. Cursor gets it through Claude Code." (a skill) | "Added Design tools for all projects" |
| Remove from a client | `x` | "Remove Developer kit from Codex" | "Codex stops loading it and the skills inside. Other clients keep it." | "Removed Developer kit from Codex" |
| Turn off inside item (D25: gone) | `toggle-right` | "Turn off Code review in Developer kit" | "Claude Code and Codex stop loading it. The rest of Developer kit stays." | "Turned off Code review in Developer kit" |

- `who` (shown if Apply fails): "Codex's settings" (first client). Tray bar, one row: title, detail, **Cancel** / **Apply**. Several rows: **"N changes in
  preview"**, **"Nothing is written until you Apply. Click one on the map to take it out."**, **Cancel all** / **Apply all**; each row has its own `×`
  (**"Take it out of the preview"**). On failure: **"Nothing was changed"** + "<who> changed while Kitden was writing. Kitden put the files back.",
  **Try again**. After Apply: button **"Applied"** / **"All applied"**, toast **"Applied N changes"** with **"Undo all"** for several.
- Lands (Calm): preview link fades (240); solid link draws in 260 CALM; the card re-renders as On (Calm: no pop); an open checklist steps back to
  the plugin panel; the plugin panel re-renders. Rows land 60 ms apart. Undo: new links undraw (380), the plugin returns to "Not added" if no client
  keeps it; a removed link draws back 480.
- The "In preview" word on the Details buttons (carried to Phase 6 in the plan) is not in the mockup's Library; the checklist note is the only place.

## 9. Sample data (`LBD`, `LCLIENTS`, 1059-1064)

- Clients: `claude` "Claude Code" Connected; `codex` "Codex" Connected; `cursor` "Cursor" "Via Claude Code".
- Groups: `community` "Community marketplace" [devkit, docs]; `team` "Team marketplace" [design]; `yours` "Your skills" [release].
- Items (`by` = clients that load it; `inside` = [name, kind]; runtime adds `pend` [] and `off` []):
  - `devkit` "Developer kit", by claude + codex, inside: Code review (Skill), Test helper (Skill), Commit helper (Skill), /ship (Command).
  - `docs` "Docs writer", by claude, inside: Draft README (Skill), Changelog (Skill).
  - `design` "Design tools", `added:false`, by none, inside: Interface review (Skill), Design tokens (Skill).
  - `release` "Release notes", `skill:true`, by claude + cursor, no inside.
- Files: `claude-md` "CLAUDE.md" meta "Claude Code · this project" by claude, imports design + dev; `agents-md` "AGENTS.md" "Codex · all projects"
  by codex, imports dev; `rules` ".cursor/rules" "Cursor · 2 rules" by cursor, imports none. Imports: `design` "docs/design.md", `dev` "docs/development.md".
- Placeholder file lines are fake ("not a real file"); a real build reads the file.

## 10. Keyboard and accessibility

- Every block (`.blk`): `tabindex=0`, `role="button"`, `aria-label` = name (`MapView.add`). Enter or Space on the focused block runs its click (1115).
  Focus ring `.nd:focus-visible`: 2px accent, offset 2. Captions are not focusable. The inline `+` and caption `Add` are real buttons.
- Panel: `×` buttons have `aria-label="Close"` / `"Back"`; the mockup does not move focus into the panel, trap it, return it, or close on
  Escape (there is no `Escape` handler in the file). Checklist rows are `role="checkbox"` + `aria-checked`; disabled rows use `disabled`.
- The link `×` has `aria-label` and `title` = its words and `:focus-visible` ring, but it only shows on pointer hover or after a link click; links are not
  focusable, so a keyboard user cannot reach it. Drag has no keyboard form. Toast has `role="status"`. The drag tip has no live region.
- Reduced motion: `D()` = 0, so moves, fades, shakes and draws are instant. Dark and light themes both use the tokens.
- Gaps for the planner: keyboard route to "Remove from <client>…" (for example a row in the plugin's Details), focus into and back from the panel,
  Escape, and a live region for the drag tip words.

## 11. Differences to note

Clashes with Kitden's rules or the owner's decisions; the build must not copy these:
1. **D25.** "3 of 4 on" and the green/grey inside marks, `offSkill`, the `libk` tray row, "Turn off Code review in Developer kit", the × on `L~k~` links, the
   inside-item "State: On / Comes with the plugin", "Turn off for all projects…" and "Turn off in one project…" on inside items, and the inside-link muted
   dashes meaning "off". Build: card says "4 items"; inside rows have no switch and no ×; their panel says "Follows its plugin".
2. **D26.** The mockup lists Cursor in the checklist (disabled, "Gets plugins through Claude Code") and drag refuses it with "Cursor gets plugins through
   Claude Code", which fits. But the sample gives the standalone skill "Release notes" a Cursor link, and `canHit` lets the × remove it ("Remove Release notes from Cursor"),
   and the skill drag and `dropWhy` treat Cursor the same as for plugins. Cursor must never be a target for a plugin (and no plugin remove from Cursor); decide what a skill
   may do with Cursor before copying.
3. **D27.** `AGENTS.md` (Codex) has an import link to `docs/development.md`. Only Claude Code files may have import links; the Codex and Cursor files show no imports.
4. **D23 / D24.** No sign-in words in Library. Counts: the Add tray detail says "2 skills" using `inside.length` (a plugin with a command would be miscounted:
   Developer kit would say "4 skills" though it has 3 skills and 1 command); the badge and "N inside" also count items. Show only counts Kitden has read.
   Client state words "Connected" and "Via Claude Code" are hard-coded; they must be Kitden's own facts.
5. **Nothing written before Apply.** All changes in the mockup go through the tray: good. But the plugin Details "Turn off for all projects…", the skill's two buttons and the
   caption `Add` / `+` shortcuts do nothing or are hard-coded (`add('design', claude+codex)`, `add(a,['claude','codex'])`). Each must make a real preview (and Codex/Claude Code
   rows per client or project). Taking a pending add out of the tray by clicking its card (1111) is fine (it undoes a preview, writes nothing).
6. **No paths on main pages.** The Instructions map shows file names/paths as block titles (`CLAUDE.md`, `.cursor/rules`, `docs/design.md`) and meta like "Codex · all
   projects"; the Details panels show file lines inline; skill panels show an id ("code-review") and "Your skills folder". Keep names that are the item's name; put real paths,
   file lines and ids behind "Technical details". Plan Task 6.5 says file lines go under Technical details.
7. **"+ Add" on the Library.** The mockup has no panel for it. Plan Task 6.1: a plugin nobody has shows only in the add panel (not as a "Not added" card), so the mockup's
   Design tools card and its inside links in muted dashes need an owner/planner call.
8. **List view, Differences, Add missing** are not in the mockup (section 7). Design them from the Gateway List and the owner's ruling; they must keep preview -> Apply.
9. **Study-only.** "Demo data" chip, the footer tag, Rich ripple/beam/pop/marching dashes (D28), the tutorial-style say line on the skill panel.
10. Small: the nested `button` inside `role="button"` (the card `+`); `.primary` is not cleared by a non-× close of the Add panel; `Inside` caption always folds into Developer kit; the
    "Add to ..." button lists `Claude Code or Codex` but the add itself always means "all clients that lack it" only for the `+`; `missing` ignores Cursor on purpose.
