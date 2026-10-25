# Gateway page in the mockup: notes for the build (Calm only)

Sources read in full: `docs/mockup/kitden-motion.html` (v11), `docs/mockup/motion-spec.md` M0-M6, decisions D1-D28 in
`docs/superpowers/plans/2026-10-24-mockup-alignment.md`. Line numbers are in `kitden-motion.html` unless marked.
"Calm" = `S.rich` false. `D(ms)` = 0 under reduced motion. Default Web Animation ease = CALM `cubic-bezier(.2,.8,.2,1)`,
fill `backwards`, default duration 300. OUT3 = 1-(1-t)^3, IN3 = t^3 (map tweens, `E.out` / `E.in`, line 465).

## 0. Quick map: mockup function -> line

| Thing | Function | Line |
|---|---|---|
| Block CSS | `.blk`, `.gw`, `.tool`, `.out`, `.srv`, `.badge`, `.port`, `.lamp`, `.mark`, `.unx`, `.slot`, `.drop`, `.lift`, `.leaving` | 113-162, 318, 359-364, 381 |
| Link CSS | `.lk`, `.lk.direct`, `.preview`, `.on`, `.hov`, `.ov`, `.edge-x`, `.hit` | 163-174, 315-317, 369-380 |
| Panel CSS | `.panel`, `.p-*`, `.facts`, `.sk`, `.sw-*`, `.switch`, `.pick`, `.radio`, `.chk`, `.exs`, `.chip-s` | 202-250, 288-343, 365-387 |
| Page shell | `.head`, `h1`, `.lede`, `.scope`, `.seg`, `.hintline`, `.stage` | 74-90, 109 |
| Map engine | `MapView` (`place`, `link`, `unlink`, `d`, `move`, `focus`, `unfocus`, `lit`, `drawIn`, `dash`, `undraw`) | 484-526 |
| Panel helpers | `openPanel` 532, `skeleton` 533, `panelLoad` 534, `swapPanel` 536-538, `closePanel` 539 | 531-539 |
| Tray | `tray.add/remove/removeAll/render/apply` | 606-642 |
| Data | `GWD`, `GW`, `CLIENTS`, `PROJECTS`, `eff`, `ownRules` | 574-597 |
| Gateway: mount/scope/meta/tag/toolHTML/spec | | 646-664 |
| Gateway: layout/linksFor/origin/build/relayout/enter | | 665-703 |
| Gateway: wire (click/hover/keys), hover | | 704-717 |
| Gateway: toggle/lightServer/selectServer | server unfold | 719-726 |
| Gateway: selectClient, clientPanel, connect, setConn, refreshPanels | | 727-753 |
| Gateway: selectGateway, gwPanel | | 754-762 |
| Gateway: selectOutside, moveIn | | 763-769 |
| Gateway: hookLinks, previewKey, linkTip, linkRemove, linkClick, linkPanel | | 771-794 |
| Gateway: removeFromGw, restoreServer, removeOutside, clearSel | | 795-809 |
| Gateway: selectTool, toolPanel, wireToolPanel, reopenTool | | 810-829 |
| Gateway: pickProject, changeProject, pendTag, syncPicks, change, applyTool | | 831-878 |
| Gateway: serverPanel, wireServerPanel, syncSwitches, changeServer | | 879-901 |
| Gateway: pickClient, moveOut, commitOut, backIn | move out | 903-929 |
| Gateway: openAdd, resRow, preview, resDrag, commitAdd, removeServer (Phase 5) | | 931-980 |
| Gateway: lightGw, wireStart, dragStart, dropIn, moveBack | drags | 981-1018 |
| Gateway: project, sweep, listHTML, setView, swap, filter | | 1020-1055 |
| Page head, `go`, project picker, find | `head` 1303, `go` 1310, `projBtn` 1326, `setProject` 1333, find 1343 | |
| Library `dropWhy` (refusal pattern to copy) | | 1193-1206 |

## 0b. Decisions that cut what the mockup shows (summary; details in each section)

| Decision | What it removes or changes on the Gateway page | Who wins |
|---|---|---|
| D5 | Panel floats (already the mockup). Keep narrow layout under 1024 px | mockup |
| D7 | Words: "Reads only" (not "Read only"), "Permission" (not "State"), "in every project", caption "· drag one in", "Use all projects" | mockup. NOTE: the mockup's own Tool panel button is "Use the shared rule…" and its Server-panel link is "Use all projects". Use each where the mockup uses it (confirm with owner) |
| D11 | Each tray row keeps a small "Show changes" (mockup has none) | decision |
| D12 | Click on a preview block / link takes its row out (mockup too) | mockup |
| D13 | "Turn on in some projects…" checkbox step; each ticked project = one tray row | mockup |
| D14 | Free client wire allowed. Grip only on outside servers the gateway can take. Refused drop says why | decision |
| D15 | Project switch keeps tray; rows show their project | mockup |
| D17 | Switches only add a pending tray row, never write | mockup |
| D18 | Mockup drops strict mode, writing-tools batch, Refresh, Put back, Keychain, Move all, Add another gateway, Set up / Turn on / Open app. KEEP all, under "Technical details" or a "More" row | decision |
| D19 | Keep narrow layout, "N more", first-run slot, registered gateways | decision |
| D20 | Tray row checks appear together at verified, not one by one | decision |
| D23 | NO sign-in words: "Sign in needed", "Sign in…", "Signed in there", "Sign-in" fact rows, key-round icons, amber server lamp | decision |
| D24 | NO "Running", NO "New tools: Stay off until you turn them on", NO "not tested with Kitden", NO tool counts on outside or marketplace servers ("Moves in · 3 tools", outside "N tools", outside list "N tools", "Preview · N tools") | decision |
| D28 | No Rich, no marching dashes, no beams, no ripples, no spotlight, no sweep, no border beam (`.bb`) | decision |

Not built (study controls, Rich-only): Motion pill, Slow x4, Fail next Apply, Replay, "Demo data" chip, `#tag` ("Gateway · motion study · demo data"), `ripple`, `spark`, `beam`, `.sweep`, `.bb`, dots canvas.

---

## 1. Block looks (Task 4.1)

### 1.1 Shared block (`.blk`, lines 116-121)

- Layout: flex, centre, gap 10, padding 0 12, bg `--panel`, border 1px `--line`, radius 8, cursor pointer, no text select.
- Text: name `<b>` 12px / 600 / `--ink` (Inter), meta `<small>` 11px / `--muted`, flex gap 5, `.tx` column gap 2.
- Transitions: border-color 180 ease, background-color 180 ease, box-shadow 300 ease, filter 300 ease, `scale` 260 SPRING.
- Hover: border = 38 % accent mixed into `--line`. Press (`:active`): scale .98 (stays while the pointer is captured in a drag).
- Each node: `tabindex=0 role=button aria-label=<name>`, Enter / Space = click (line 498, 707).
- Block sizes and places (layout, lines 665-673):

| Block | w x h | x | y |
|---|---|---|---|
| Captions Clients / Gateway | 150 x 18 | 0 / 196 | 0 |
| Caption Servers (holds "+ Add") | 200 x 26 | 396 | -4 |
| Client | 150 x 54 | 0 | 124 + 72 i |
| Gateway | 150 x 124 | 196 | 124 |
| Group caption Remote, Local | 170 x 18 | 396 | Remote at 58; next = prev server y + 70 + 3 (+70 if the slot is in the group) |
| Server | 170 x 60 | 396 | caption y + 23, then +70 each |
| Slot | 170 x 60 | 396 | after last server of its group |
| Caption "Outside the gateway" | 260 x 18 | 396 | after last group: y + 18 |
| Outside | 170 x 50 (mockup: 66 when "Signed in there"; D23: always 50) | 396 | caption y + 21, then +h+6 |
| Caption Tools (only while a server is open) | 190 x 18 | 636 | 0 |
| Tool | 200 x 34 | 636 | max(24, serverMid - (42 n - 8)/2) + 42 i |

  Map starts 860 x 520; height = max(500, lowest bottom + 24). Gaps: client->gateway 46, gateway->server 50, server->tool 70.
- Port (`.port`, 130-139): 9px circle, bg `--canvas`, border 1.5px `--wire`, centred vertically, `left:-5px` / `right:-5px`. Border -> accent 200 ease when block is selected or lit. `.port.amber` = border `--faint` (outside block's left port; never turns accent).
- Lamp (`.lamp`, 127-129, 363-364): 6px dot, bg `--faint` (off); `.on` `--ok`; `.warn` `--warn` (D23: unused here); `.pv` transparent + 1.5px DASHED accent ring = in preview; `.dir` transparent + 1.5px SOLID `--faint` ring = works outside the gateway. Colour change 400 ease. Flip pop: scale 2.2 -> 1, 200 CALM (server lamp, `syncMeta` 653); client lamp 2.4 -> 1, 200 CALM (`setConn` 748).
- Mark (`.mark`, 149-151): same 6px dot for tools: grey / `.on` green / `.pv` dashed accent ring. 400 ease. Flip pop 1.9 -> 1, 200 CALM.
- Roll numbers (`roll`, 474): old moves 70 % of its height and fades, 140 ease-in; new comes in 200 CALM; up if bigger, down if smaller (text: always down).

### 1.2 Server block (`spec` k=s, line 659; `meta` 652)

- Content, left to right: `.itile` 28 x 28 (radius 6, border 1px line, bg `--inset`, colour `--ink-2`) with a 15px icon; `.tx` = name + meta line; count badge; ports.
- Meta line normal: lamp (on when n > 0) + `<n> of <m> on` (n inside a `.num` that rolls). Words: "n of m on".
- Meta in preview: dashed lamp + accent text "Preview · N tools" (marketplace add) or "Moves in · N tools" (outside moving in). D24: show only "Preview" / "Moves in" (no count).
- Meta signin: amber lamp + "Sign in needed" -> D23: not built.
- Count badge `.badge` (135-138): 20px circle, bg `--raised`, border 1px line, 10px text `--ink-2`, `right:-10px`, vertically centred; text = number of tools. Open: opacity 1 -> 0 (200 ease) and scale 1 -> .3 (300 SPRING).
- Right port: hidden (opacity 0, scale .4) until open: opacity 0 -> 1 (200 ease), scale .4 -> 1 (300 SPRING), border accent. Left port always.
- Open server (`.srv.open`): border accent (180). It is NOT given `.sel` (the select fill is for the active click target only; opening a server does not add `.sel`).
- Name font: Inter (not mono). Icon per server is demo data (git-branch, square-kanban, folder, globe, package-open, bug, database, monitor-play). Kitden needs its own rule for an icon; all icons the Gateway page uses already exist in `src/kitden/web/static/js/icons.js`.
- Grip: none on gateway servers (they are still draggable, see 6.2).
- Group captions: "Remote" with `cloud` 13px; "Local" with `hard-drive` 13px; `.cap.grp` = 11px, weight 600, colour `--ink-2`.

### 1.3 Gateway block (`spec` k=gw, line 658; CSS 140-145)

- 150 x 124, flex column, centred, gap 1, padding 10, bg `--raised`, border accent. Selected (`.gw.sel`): bg `--select`.
- Top to bottom: house logo (Kitden mark, fill #C85835) svg 26 x 26, margin `0 auto 4px`; `<b>Kitden gateway</b>` 13px; small centred: green lamp + "On this Mac"; stats row (flex, centred, gap 10, margin-top 7, 11px `--ink-2`): `monitor` 12px + "<n> clients", `server` 12px + "<n> servers".
- Numbers roll (140 ease-in + 200 CALM) when they change: clients on Apply / Undo of connect (`setConn` 750), servers on add / remove / move (`roll($('#gw-n'))`). `#gw-c` = connected clients; `#gw-n` = servers in the gateway that are not in preview.
- Mockup always says "clients" / "servers" even for 1 (plan: use singular for 1).
- Both ports (left, right) always visible.
- The mockup puts `title="Running"` on the lamp line. D24: drop "Running" (Kitden does not know it).
- Drop-target look: see 1.9.

### 1.4 Tool block (`spec` k=t 660; `toolHTML` 655; `tag` 654; CSS 146-148, 312-314)

- 200 x 34, gap 9, padding 0 10. Left to right: mark (6px dot) -> name (12px `--ink`, one line with ellipsis) -> project tag (right, `margin-left:auto`) -> left port.
- Project tag `.ptag`: 10.5px `--muted`, `folder` 11px + text, gap 4.
  - Under "All projects": shows when the tool has own rules: "N project" / "N projects" (N = projects with an own rule for this tool).
  - Under a project: shows "This project" in accent (`.ptag.acc`) when that project has an own rule.
  - Waiting in the tray (`pendTag` 849): accent `.ptag.acc.pend`: the project name (one) or "N projects" (several). Pop opacity 0, scale .7 -> 1, 180 (Calm; `changeProject`), 280 (`change` 862), 200 (`applyTool` 874 and `project` 1022).
- Selected tool (`.blk.sel`): bg `--select`, border accent.
- A tool link exists only when the tool is on. Off tools have a grey mark and no link.

### 1.5 Client block (`spec` k=c, line 657)

- 150 x 54. Client logo `.tile` 28 x 28 (radius 6, border 1px line, bg #12151A; Claude Code gets padding 4) -> `.tx`: name + small: lamp (green when connected) + "Connected" / "Not connected"; right port only.
- Free client (not connected, not in preview): `.free` = `cursor:grab`. No grip icon.
- Mockup also had Cursor "1.9 · not tested". D24: never show "not tested with Kitden".

### 1.6 Outside block (`spec` k=o 661; CSS 152-154)

- 170 x 50, bg `--dim`. Left to right: grip (`grip-vertical` 13px, `--faint`, cursor grab, margin-right -4) -> server icon 15px (`--ink-2`, no tile box) -> `.tx`: name + small: grey-ring lamp (`.lamp.dir`) + "In Cursor" / "In Claude Code" (`In <client>`) -> left port with `.amber` (grey).
- "Signed in there" second line (key-round 11px): D23 drop.
- Preview ("Moves to <client>"): lamp `.pv` + accent text "Moves to Codex"; `.blk.preview`; × badge.
- D14: grip only where the gateway can take the server (OAuth, project files, plugin roots: no grip).
- Caption (line 663): `info` 13px in amber (`--warn`) + bold "Outside the gateway" (weight 600, `--ink-2`) + normal muted " · drag one in".

### 1.7 Preview look (`.blk.preview` 156-157, `.unx` 359-361)

- bg `--preview-fill` (dark #F09A7C10, light #A4422612), border 1px DASHED `--preview-line` (dark #F09A7C80, light #A4422680), meta text accent.
- Title attribute: "In preview. Click to take it out." Click = take row out of tray (D12).
- × badge `.unx`: 18px circle at top -8 / right -8, bg `--panel`, border 1px accent, accent `x` icon 11px; opacity 0 / scale .5 until `.blk.preview:hover` or `:focus-visible`, then opacity 1 / scale 1 (opacity 180 ease, scale 320 SPRING). Hover also: border = full accent. The × is `aria-hidden` and `pointer-events:none` (the whole block is the click target).

### 1.8 Leaving look (`.blk.leaving` 381)

- `filter: opacity(.45)` (300 ease via the filter transition) and `border-style: dashed` (instant). Added when a removal is in the tray (server, outside server). Removed when the row is taken out (`clear`), or the block is deleted on Apply.

### 1.9 Lit / selected / dim / find / drop / lift

| Class on map or block | Look | Time |
|---|---|---|
| `.map.focus .nd.blk:not(.lit):not(.sel)` | `filter: opacity(.4) saturate(.6)` | 300 ease |
| `.map.focus .lk:not(.on)` | stroke-opacity .16 | 300 |
| `.blk.sel` | bg `--select`, border accent | 180 |
| `.lit` / `.sel` ports | border accent | 200 |
| `.map.find .nd.blk.miss` | `opacity(.3) saturate(.5) blur(1.2px)` | 300 ease |
| `.map.find .lk` | stroke-opacity .2 | 300 |
| `.blk.drop` | border accent, bg `--select`, `scale:1.05` | border/bg 180, scale 260 SPRING |
| `.blk.lift` | `box-shadow: var(--shadow)` (dark `0 18px 44px -14px rgb(0 0 0/.7)`, light `0 18px 44px -18px rgb(26 31 42/.28)`), border accent, cursor grabbing, z-index 5 | shadow 300 |
| `.slot` | like preview: dashed `--preview-line`, fill `--preview-fill`, radius 8 | |

Captions (not `.blk`) are never dimmed. Hover preview (`hover` 712): pointer on a client or outside block while nothing is selected = focus (no overlay): client -> itself, gateway, servers (not previews, except moving-in), the open server's on tools, its outside servers, and the links between; a client that is not connected -> only its outside servers and bypass links. Pointer on any other block or off the map -> unfocus.

### 1.10 Captions on the page

"Clients", "Gateway", "Servers" + button `+ Add` (`.btn.xs`, `plus` 12px; becomes `.primary` while the Add panel is open), "Remote", "Local", "Tools" (no icon; only while a server is open), "Outside the gateway · drag one in". Only Remote, Local and Outside have icons.

---

## 2. Server unfold and fold (Task 4.2) - `toggle` 719, `relayout` 683-693, `origin` 680

Click rules (`wire` 706): closed server -> `toggle` (open). Open server that is NOT the active selection (a tool or nothing is active) -> becomes active, no fold (`selectServer` + `lightServer`). Open and active -> `toggle` (fold). A tool of a closed server opens that server first (`selectTool` 810). Preview server click -> takes its row out.

Open, in order (Calm, t = click):

| t | What | Time | Ease |
|---|---|---|---|
| 0 | `.open` on block: border -> accent (180); badge out (opacity 200, scale 300 SPRING); right port in (opacity 200, scale 300 SPRING, accent border) | | |
| 0 | `selectServer` -> panel opens with skeleton (see 3.1); real content at 160 | | |
| 0 | New nodes made: "Tools" caption + one tool block per tool, placed on their FINAL x/y, scale 1, opacity 0 | | |
| 0 | Map height set at once (`size`) | | |
| 0 | Tool links (only for tools that are on) draw from the server's RIGHT port to the tool's LEFT port, all together | 170 | CALM |
| 170 | Caption + tool blocks fade in 0 -> 1 (position fixed already), in layout order (caption first), 15 apart | 120 each | OUT3 |
| end | Links start following block opacity again | | |
| end of relayout | Path lights (`lightServer` 724): groups in order client->gateway links, gateway->server link, the server's tool links; overlay 2.1px accent fades 0 -> 1 all at once | 180 | CALM |
| any | Other blocks that change place glide (all layout blocks are re-tweened) | 260 | OUT3 |

Total until tools are all visible: 170 + 120 + 15 x (tools). No cap (D9).

Fold (second click on the active open server, or opening another server):
- `.open` removed (CSS back: border, badge in, port out).
- `clearSel` -> overlays fade 1 -> 0 over 160 ease-in then removed; dim/focus off (300); panel out 180 ease-in.
- Tool blocks and "Tools" caption go back to a point at the server: x = server right - 100, y = server middle - 17, scale .3, opacity 0, 180 IN3. Their links fade with them (link opacity = lower of its two blocks). Nodes + links removed after.
- Other blocks glide 260 OUT3. Map height recalculated.
- Switching from server A to B: A's fold and B's unfold run in the same relayout.

Phase 4 plan items already agreed: tool links 170 CALM from right port; tools 120 OUT3, 15 apart; fold 180 IN3; glide 260.

---

## 3. Details panels (Task 4.3)

### 3.1 The floating panel (CSS 203; helpers 531-539)

- Box: `position:absolute; right:22px; top:190px; bottom:46px; width:min(320px, 100% - 44px); z-index:20` (dock is 25, hint line 2); bg `--panel`, border 1px `--line`, radius 10, padding 18, flex column gap 16, `--shadow`, `overflow:auto`. It sits in the column to the right of the rail (not over the rail).
- Parts: `.p-kick` (flex, space-between, 11px `--faint`; kind word + close `.x`: 24 x 24, radius 6, `--muted`, hover bg `--dim` + `--ink`, `x` icon 14, aria-label "Close"); `.p-title` 17px / 600 / -.01em; `.p-id` 11px mono `--muted` (tool id) or Inter (inline override for others); `.p-head` flex gap 12 (tile/icon + title/id); `.facts` grid `94px 1fr`, gap 11px 8px, padding 12px 0, border top+bottom 1px line, 12px, dt 11px `--muted`, dd flex gap 6; `.p-say` 12px `--ink-2`; `.p-acts` flex column, align start, gap 8; `.p-tech` (margin-top:auto, flex space-between, padding-top 10, top border 1px line, 12px `--muted`): "Technical details" + `chevron-right` 14 (a plain row in the mockup; Kitden keeps its real Technical details here, D18).
- Open (first panel): opacity 0 -> 1, translateX 28px + scale .98 -> none, 240 CALM.
- Skeleton (`skeleton` 533) shown at once: kick row (kind word + ×); bars `.sk` (bg `--raised`, radius 5, height 10, no shimmer in Calm): 62 % x 16px and 38 % (grid gap 8); a block (padding 12px 0, top+bottom border, gap 12) of 5 bars 70, 54, 80, 46, 60 %; a 90 % bar; a 55 % x 30px bar (radius 7).
- Load (`panelLoad` 534): skeleton, then after 160 the real content replaces it; each direct child rises: opacity 0 -> 1, translateY 6 -> 0, 260 CALM, 20 ms apart.
- Swap (choosing another client / server / tool / gateway while a panel is open): the panel stays; content goes to the skeleton at once, then loads (160 + rise). An outside server, a link, the Add panel: `clearSel()` closes the old panel (180, async) and a NEW panel opens (240) at the same time.
- Close (`closePanel` 539): opacity 1 -> 0, translateX 0 -> 22px, 180 ease-in, then removed. Page switch = instant.
- Step forward / back inside one panel (`swapPanel` 536): old children together: opacity -> 0, translateX 0 -> -18px (back: +18px), 130 ease-in; then new children together: opacity 0 -> 1, translateX +22px -> 0 (back: -22px), 220 CALM (no stagger in Calm).
- Re-render without motion: Client and Gateway panels when a connect row enters or leaves the tray (`refreshPanels` 751); Connection panel after its remove button (784).
- Tool panel re-render when a tool change lands (`applyTool` 878): facts, text, actions rise again: translateY 6 -> 0, 260, 40 apart (children 2-4).
- Server panel on a tool change (`syncSwitches` 893): switches flip (`pending` off, `aria-pressed` set), "n of m on" number rolls, the "Whole server" line text is replaced.
- Project change with a Tool or Server panel open (not in a picker step): steps forward (`reopenTool` / `reopenServer`, 'fwd'). A change landing while the project picker step is open: steps back.
- Closing: × calls `closePanel` and `clearSel`.

### 3.2 Switch (CSS 332-338; `sw` 597)

`<button class="switch [pending]" data-sw aria-pressed aria-label>`; hit area 34 x 24; track 34 x 20, radius 10, bg `--inset`, border 1px line; knob 14 x 14 at top 2 / left 2, `--muted`. On: track bg + border accent, knob translateX(14px), white. Pending: track dashed border, bg `--select`, border accent; knob translateX(7px), accent. Track 250 ease; knob 340 SPRING. Click on a `pending` switch takes its row out of the tray (`tray.remove`); otherwise sets pending and adds a row. A switch never writes (D17).

### 3.3 SERVER panel (`serverPanel` 879-886, wired 887-891)

| Section | Content (exact words) |
|---|---|
| Kick | "Server" + × |
| Title / id | `<name>` / "Remote · in the Kitden gateway" or "Local · in the Kitden gateway" |
| Facts | "Sign-in": "Needed" (amber, key-round) or "Signed in" -> **D23: drop the row**. "Tools": "<n> of <m> on". "Comes from": "All projects". "Clients": two logo tiles + "2 clients" (use real connected clients) |
| Header | "Tools · All projects" or "Tools · <project>" (`.sw-head`: 11px, 600, `--ink-2`) |
| List (border 1px line, radius 8) | Row "Whole server" (bg `--dim`): bold "Whole server" + small "<n> of <m> tools on" or "Every tool is off"; switch (on if any tool is on; label "Whole <name> server"). Then per tool: mono name (snake_case, 11px) + small "<Tool name> · Reads only" or "<Tool name> · May write"; under a project, if it has its own rule, an accent line: folder 11px "Differs from all projects · " + link button "Use all projects"; switch with the tool name as label. Rows separated by 1px line; padding 8px 10px; gap 10 |
| Buttons | (sign-in primary "Sign in…" -> D23 drop) "Move out of the gateway…" -> step to client picker (4.2). D18: "Remove from the gateway…" and the other kept actions go under Technical details or a "More" row (mockup only has the link x for remove) |
| Foot | "Technical details" row |

Tray rows from this panel:

| Control | Key | Icon | Title | Detail | Toast |
|---|---|---|---|---|---|
| Tool switch (All projects) | `tool~<sid>~<i>` | toggle-right | "Turn on|off <Tool> for all projects" | "Claude Code and Codex can call it through Kitden[ wherever a project has no rule of its own]." / "Claude Code and Codex stop calling it through Kitden[...]." (bracket only if tool has own rules) | "Turned on|off <Tool> for all projects" |
| Tool switch (in a project P) | same | toggle-right | "Turn on|off <Tool> in P" | "Only in P. Every other project keeps it on|off.[ Codex: start a new session.]" (last sentence only when turning on) | "Turned on|off <Tool> in P" |
| Whole server switch | `srv~<sid>` | toggle-right | "Turn on|off <Server> for all projects" / "in P" | on: "Claude Code and Codex can call its tools again[, as they were | , the ones that only read]." off: "Claude Code and Codex lose <n> tool(s). <Server> stays in the gateway." | same as title with "Turned" |
| "Use all projects" link | `tool~<sid>~<i>` | toggle-right | "Use the shared rule for <Tool> in P" | "P goes back to on|off, like every other project." | "P uses the shared rule for <Tool>" |

(Hard-coded "Claude Code and Codex": Kitden should name the real clients. Toast extra for project rows: button "Show <project>" when the project is not the current one.)
- Whole server map preview: off -> every tool link of that server blends to preview dashes (300 CALM); on -> nothing on the map. Tool switch map preview: see 3.4. Apply lands tools 80 ms apart (`applyTool`).
- D17 reminder: switch = pending look + row only.

### 3.4 TOOL panel (`toolPanel` 815-825, wired 826-828)

| Section | Content |
|---|---|
| Kick / title / id | "Tool" / tool name / snake_case id (mono) |
| Facts | "Server": icon 13 + "<Server> · Remote|Local". "Permission": mark + "On" / "Off" (under a project: "On in this project" / "Off in this project" when it has its own rule; otherwise "On · from all projects" / "Off · from all projects"). "Comes from": "All projects" or accent "This project · <P>". "Reported": "Reads only" or amber "May write". "Clients": two tiles + "2 clients" |
| "Projects with a rule of their own" | Only under All projects and only if the tool has own rules. `.sw-head` text exactly "Projects with a rule of their own"; rows (flex gap 8, 12px): folder 13 + project name (flex 1) + "On" (accent) or "Off" (muted) + `btn xs` "Show" -> switches the project in place (`setProject`, see 7.4) |
| Sentence (`.p-say`) | No own rule, All projects: on -> "Claude Code and Codex can call this tool through Kitden, in every project." off -> "Claude Code and Codex can't call this tool through Kitden, in any project." plus (if rules) " Except <P>, where it is on|off; <P2>, where it is on|off." Under a project without own rule: "<P> follows the shared rule: on|off." Under a project with own rule: "Claude Code and Codex can|can't call this tool in <P>. Every other project has it on|still has it off." |
| Buttons | All projects: `Turn off|on for all projects…` (primary when the tool is off) and `Turn off|on in some projects…`. Project, follows shared: primary `Turn off|on in <P>…` and `Turn off|on for all projects…`. Project with own rule: primary `Use the shared rule…` and `Turn on|off for all projects…` (value = this project's current value) |
| Foot | "Technical details" |

- Button "…" means "adds a preview"; none writes.
- Tray rows: "Turn on|off for all projects…" -> key `tool~<sid>~<i>`, title "Turn on|off <Tool> for all projects", detail/toast as in 3.3. "Turn … in <P>…" -> "Turn on|off <Tool> in <P>". "Use the shared rule…" -> "Use the shared rule for <Tool> in <P>".
- Map preview for a tool change (`change` 854-872): only if the effective value for the current project changes: the mark gets a dashed ring (`.mark.pv`); turning on -> a new preview link (accent dashes 4/4 at .65) server->tool fades 0 -> 1, 240; turning off -> the existing link blends to preview dashes (300 CALM). A rule for another project than the current: the tool's tag shows that project (pending tag, pop 280). Same key twice replaces the earlier row.
- Lands on Apply (`applyTool` 873): block re-rendered; mark pops 1.9 -> 1 (200 CALM) and turns grey/green (400); tag pops (200); link draws in 260 CALM (turned on) or undraws (380 RETRACT, or fades if dashed); server "n of m on" rolls; server lamp pops 2.2 -> 1 if it flips; open Server panel switches update; open Tool panel re-renders with rise.
- "Turn … in some projects…" step: see 5.

### 3.5 CLIENT panel (`clientPanel` 733-738, wired 739)

| Section | Content |
|---|---|
| Kick / head | "Client"; client tile 28 + title (name) + Inter id "Version <v> · on this Mac" (+ amber " · not tested with Kitden" -> D24 drop) |
| Facts | "Gateway": lamp + "Connected" / "Not connected" (+ accent " · change in preview" when a connect row waits). "Through Kitden": connected -> "<n> servers · <m> tools on"; else muted "Nothing yet". "On its own": amber-ringed chips (`.chip-s`: icon 12 + name; 11px, radius 10, bg `--dim`, border 1px 45 % warn) for each outside server, or muted "Nothing". "Library": Cursor "Skills through Claude Code"; others "2 plugins · 3 skills" (demo; use real counts). "Projects": "All projects" or the project name |
| Sentence | Connected: "<Client> calls <n> servers through Kitden, so Kitden's rules apply to them." Not connected: "<Client> does not use the Kitden gateway yet. Drag it onto the gateway to connect it." plus, if outside servers: " <A> and <B> are|is set up in <Client> on its own and skip|skips those rules." |
| Buttons | Connected: "Disconnect from the gateway…". Not: primary `plug` 13 "Connect to the gateway…". Both disabled (opacity .5) while a row waits. Always: "See what it loads in Library" (goes to Library). |
| Foot | "Technical details" |

Select (`selectClient` 727): `.sel` on the client; lit path groups in order: client->gateway link; gateway->server links (not preview); the open server's tool links that are on; its outside servers and bypass links get `.on` (bypass `on` = muted colour at full opacity, `.lk.direct.on`). Overlay 180 fade-in.

### 3.6 GATEWAY panel (`gwPanel` 757-761, wired 762)

| Section | Content |
|---|---|
| Kick / head | "Gateway"; 32px tile with the house logo + "Kitden gateway" + Inter id "On this Mac" |
| Facts | "State": green lamp + "Running" -> **D24 drop; use today's words**. "Servers": "<n> in the gateway · <m> outside". "Tools": "<on> of <all> on". "Sign-in": amber lamp "<n> server(s) waiting" -> D23 drop. "New tools": "Stay off until you turn them on" -> D24 drop |
| Clients | `.sw-head` "Clients"; list rows: logo tile 20 + bold name + small lamp + "Connected" / "Not connected" (+ accent " · in preview") + `btn xs` "Disconnect…" / "Connect…" (disabled while waiting). |
| Button | `plus` 13 "Add a server…" -> opens the Add panel (Phase 5) |
| Foot | "Technical details" |

Select (`selectGateway` 754): `.sel`; lit groups: all connected clients' links; all gateway->server links; nodes: connected clients, gateway, non-preview servers. D18: "Add another gateway", registered gateways, strict mode, Refresh etc. stay under Technical details / More.

### 3.7 CONNECTION (link) panel (`linkPanel` 787-794; `linkClick` 785; `linkTip` 780; `previewKey` 772)

- Click a link: last selection lets go; link picked (keeps hover look and ×); only its two blocks + link stay bright (`focus`, 300); panel loads with kind "Connection". Click again = let go. Hit/× rules are Phase 2 (done).
- Which links open it: client->gateway (`c`), gateway->server (`s`), server->tool (`t`), bypass (`o`), leaving (`x`), moving-in (`d`), preview tool link (`P~L~t`).
- Words:

| Part | Content |
|---|---|
| Kick | "Connection" + × |
| Title | "<A> -> <B>" (arrow muted). A and B = the two block names (client / "Kitden gateway" / server / tool / outside server) |
| Sub (Inter) | client link "Route through the gateway"; gateway->server "Held by the gateway"; server->tool "Tool on"; bypass "Direct route"; leaving "Leaving the gateway"; moving-in "Direct route, moving in"; other "Change in preview" |
| Facts | "From": A. "To": B. "State": dashed lamp "In preview" or lamp (`.dir` for bypass, `.on` otherwise) "In place". "Written in": client link / bypass "<A>'s settings"; gateway->server "Kitden's gateway file"; tool "Kitden's rules file"; other "Not written yet" |
| Sentence | In preview: "This link is a change in preview. Nothing is written until you Apply." client: "<A> calls <n> servers through Kitden, so Kitden's rules apply." gateway->server: "The gateway holds <B> and passes its tools that are on to <n> client(s)." tool: "<B> is on: clients can call it through <A>." bypass: "<A> calls <B> on its own. Kitden's rules don't reach it." |
| Button | `x` 13 + remove words + "…": see tooltip words below. In preview: "Take it out of the preview" (no "…") |
| Foot | "Technical details" |

- Remove words (`linkTip`): client link "Disconnect <Client>"; gateway->server "Remove <Server> from the gateway"; tool "Turn off <Tool>"; bypass "Remove <Outside server> from <Client>"; preview link "Take it out of the preview". Panel button = same + "…".
- What the button does (`linkRemove` 782): preview link -> `tray.remove(key)`; client -> `connect(cid,false)` (4.1); gateway->server -> `removeFromGw`; tool -> `change(sid,i,PROJ||'all',false)`; bypass -> `removeOutside`.
- Panel text re-renders in place (no motion) after the click.

### 3.8 OUTSIDE SERVER panel (`selectOutside` 763-768)

| Section | Content |
|---|---|
| Kick / head | "Server"; 28px icon tile + name + Inter id "Remote|Local · outside the gateway" |
| Facts | "Set up in": client tile 20 + client name. "Route": grey-ring lamp "Direct, on its own". "Tools": "<n> tools" -> D24 drop. "Sign-in": "Signed in there" / "None needed" -> D23 drop. "Kitden's rules": amber "Don't reach it" |
| Sentence | "<Client> calls <name> on its own, so Kitden can't turn its tools on or off. Move it into the gateway to manage them here. <Client> keeps it either way." |
| Button | primary `log-in` 13 "Move into the gateway…" -> `moveIn` (slot opens 260, block moves 200; tray row `in~<id>`, see 6.1) |
| Foot | "Technical details" |

Select: first `clearSel`, `.sel` on block, focus only on block + its client + its bypass link (no overlay).

### 3.9 Server picker steps (reuse `.pick`, 302-309; `chk` 383-387)

`.pick`: 1px line, radius 8, padding 9px 10px, gap 10, hover border 40 % accent (180); `.on` bg `--select` border accent; disabled opacity .45. `.radio` 14px, 1.5px `--wire` border; on: accent fill + 3px `--panel` inner ring, 200. `.chk` 16px, radius 4, 1.5px `--wire` border; on: accent fill; tick svg opacity 0 -> 1 (160) and scale .5 -> 1 (320 SPRING), stroke 3. Step header (`p-kick`): back `.x` (arrow-left 14, aria-label "Back") + crumb (`margin-right:auto; margin-left:6px`) + ×.

---

## 4. Disconnect and move out (Tasks 4.4, 4.5)

### 4.1 Connect / Disconnect (`connect` 740, `setConn` 747)

Entry points: client panel button; gateway panel row button; client->gateway link × / Connection panel; free-client wire drop (6.3).

| | Connect (client not on) | Disconnect (client on) |
|---|---|---|
| Key / icon | `conn~<cid>` / plug | same |
| Map at add | New link client right port -> gateway left port, class preview (accent dashes 4/4 at .65), fades 0 -> 1, 300 CALM | Existing solid link blends to preview + leaving (muted dashes 4/4 at .4), 300 CALM (solid counts as dash "8 0") |
| Tray title | "Connect <Client> to the gateway" | "Disconnect <Client> from the gateway" |
| Tray detail | "<Client> gets <n> servers through Kitden. Start a new <Client> session after Apply." | "<Client> loses the <n> servers in the gateway. Servers it sets up on its own stay." |
| Who (failure text) | "<Client>'s settings" | same |
| Toast | "Connected <Client> to the gateway" | "Disconnected <Client> from the gateway" |
| Taken out of tray | link unlinks (fade 240 ease-out) | link blends back to solid (300) |
| Apply (`setConn`) | Block `.free` off; lamp text -> "Connected", lamp pops 2.4 -> 1 (200 CALM), grey -> green (400); link goes solid and draws in 260 CALM; "<n> clients" rolls | Block `.free` on; lamp pops 2.4 -> 1 and goes grey; "Not connected"; the dashed link keeps its dashes (no blend back while Apply writes) and fades 240 ease-out then removed; "<n> clients" rolls |
| Undo | reverse (link undraws 380 RETRACT if solid, else fades) | link draws in 260 CALM |

- `n` = servers in the gateway that are not in preview. The Client and Gateway panels re-render without motion; their buttons are disabled and "in preview" shows while the row waits.
- Mockup quirk: `setConn` rewrites the `<small>` HTML, so the lamp is a new element and does not transition colour; keep one element to get the 400 ms colour change.

### 4.2 Move a gateway server out to one client (`pickClient` 903, `moveOut` 909, `commitOut` 922, `backIn` 926)

Entry: panel "Move out of the gateway…" (steps forward) or drag onto a client (6.2).

- Panel step: crumb "Server · <name>"; title "Move <name> out of the gateway"; sentence "Pick the client that keeps it. You can also drag <name> onto a client on the map."; one `.pick` per client: logo tile 28, bold name, small "Uses the gateway now" or "Not connected to the gateway", radio. Click = radio fills (200) and the move is previewed at once (no Done). Foot (`info` 13): "The other clients lose <name>'s tools."
- Map at add: gateway server block is removed (an open server closes, selection lets go); an outside block in preview appears at the block's spot (or the drop spot): grip, icon, name, dashed lamp "Moves to <Client>", × badge. Two links fade in 0 -> 1, 320 CALM: bypass preview link from the client (accent dashes, right angles, channel = largest + 8, min 16+8) and a leaving link from the gateway (muted dashes). Relayout 260 OUT3 carries the block into the Outside list.
- Tray row: key `out~<sid>`, icon log-out, title "Move <Server> into <Client>", detail "Out of the gateway. <Client> sets it up on its own[; <Other client(s)> lose(s) its tools]." (others = other connected clients, joined with " and "), who "<Client>'s settings", toast "Moved <Server> into <Client>".
- Taken out (`backIn(o,false)`): outside block turns back into the server block on the spot; relayout 260; "<n> servers" rolls.
- Apply (`commitOut`): leaving link undraws (it is dashed, so it fades 240); bypass link turns to plain dots and draws 280 CALM; block drops preview look (180) and its × is removed; "<n> servers" rolls; the server's panel closes.
- Undo (`backIn(o,true)`): server block returns on the spot, gateway link draws in 480 CALM, relayout 260, "<n> servers" rolls.
- Task 4.5: `gateway.move_out` = `put_back_steps` + `remove_server_steps` as one change; preview warns when a Keychain secret would be written as plain text into the client file (mockup has no such warning).

### 4.3 Remove a server from the gateway (link ×, Connection panel; `removeFromGw` 795)

- Preview: gateway->server link blends to preview + leaving (300), server block `.leaving`. Row: key `rm~<sid>`, icon x, title "Remove <Server> from the gateway", detail "<n> client(s) lose(s) its <m> tools. Undo puts it back as it was.", who "Kitden's gateway file", toast "Removed <Server> from the gateway".
- Apply (`removeServer` 977): link fades 240; block shrinks into the gateway (to gateway right - 85, middle - 30, scale .4, opacity 0), 180 IN3; blocks below move up 260; "<n> servers" rolls; panel closes.
- Undo (`restoreServer` 800): block grows from the gateway spot, relayout 260, link draws in 480, "<n> servers" rolls.

### 4.4 Remove an outside server from its client (bypass link ×; `removeOutside` 802)

- Preview: bypass link blends to preview dashes, block `.leaving`. Row: key `rmo~<id>`, icon x, title "Remove <Name> from <Client>", detail "<Client> stops calling it. Nothing else changes.", who "<Client>'s settings", toast "Removed <Name> from <Client>".
- Apply: link fades 240; block moves 24px left, scale .85, opacity 0, 180 IN3; list closes up 260. Undo: block returns (from 24px left, scale .85) and the link draws in 480.

---

## 5. Several projects (Task 4.6) - `pickProject` 831, `changeProject` 842, `pendTag` 849, `syncPicks` 851

- Entry: Tool panel (All projects view only) "Turn off|on in some projects…" steps forward (130 + 220).
- Step content: header (back, crumb "Tool · <Tool>", ×); title "Turn on|off <Tool><br>in the projects you pick"; sentence (margin-top 6) "Every other project keeps the shared rule: on|off."; search field "Find a project…" (typing hides non-matching rows at once); list of `.pick.multi` (role checkbox, aria-checked): folder 14 + bold project name + small "<note> · <n> own rule(s) · already on|already off|on now|off now" (project note, e.g. "This repository"; "n own rule" with s when n > 1) + checkbox; button "Done"; foot (`info` 13) text "Tick projects. Each one waits in preview until Apply." -> "<n> project(s) in preview. Apply them from the tray." once ticked.
- Rows already at the target value are disabled (opacity .45). Back and Done both step back.
- Tick: if the tray has `toolp~<sid>~<i>~<P>` it is taken out (untick), else `changeProject` adds a row. Row: key `toolp~<sid>~<i>~<P>`, icon folder, title "Turn on|off <Tool> in <P>", detail "Only in <P>. Every other project keeps it on|off.", who "Kitden's rules file", toast "Turned on|off <Tool> in <P>", toast extra button "Show <P>" when P is not the current project. One row per project (D13); tray rows show their project (D15).
- Tick look (`syncPicks`): row `.on` (select fill + accent border, 180); box fills (200); tick fades in 160, scales .5 -> 1 (320 SPRING); box pops scale .6 -> 1, 160 CALM (not on the first sync). Untick: CSS back.
- Map while rows wait (`pendTag`): the tool block shows an accent pending tag before its port: folder 11 + the project name (one row) or "N projects" (several); pops opacity 0, scale .7 -> 1, 180 (Calm). When none wait, the normal tag returns (no pop). Mark and link do NOT change for per-project rows when they are not the current project.
- While the picker step is open the Tool panel is not shown, so "what the tool panel shows while rows wait" = the checklist above (ticked rows, count line). The main Tool panel text/facts do NOT mark waiting rows (only the map tag and the tray do).
- Lands on Apply (`onCommit` 845): rule written, tag re-rendered, pop 200; open picker step steps back to the Tool panel (130 + 220). Undo restores the old rule (`applyTool`).
- Mockup quirk to fix: `project()` (1021) re-renders tool blocks with `toolHTML(t)`, which drops the pending tag and the `.mark.pv` ring of rows still in the tray. D15 says the tray stays: re-apply pending looks after a project switch.
- `change()` (single tool, all/one project) also uses a replace-by-key rule: a second row with the same key replaces the first (Kitden's Phase 3 refuses clashes at add time instead).

---

## 6. The four drags (Task 4.7) - `dragStart` 995, `wireStart` 983, `dropIn` 1009, `resDrag` 953

### 6.0 Common (lines 995-1008; spec M5)

- `pointerdown` on the map; pointer captured on the block; handlers on that block. `button 0`; ignored if the target is inside a `<button>`.
- Start threshold: pointer moves 5 px (`hypot` < 5 = still a click). A finished drag swallows its click (`dragged` flag cleared on the next tick). While dragging: hover previews off; selection lets go (`clearSel`); `m.unfocus()`.
- Dragged block follows the pointer 1:1, no easing, rotation 0, scale 1 in Calm. Its links redraw on every move. `.lift` look (1.9). The 0.98 press scale from `:active` stays while the pointer is down (plan carried note).
- Tip (`.dragtip`, 319-320): absolute in the map layer, z-index 7, padding 3px 9px, radius 10, bg `--panel`, border 1px line, `--muted` text 11px, `--shadow`, no pointer events. Active (`.on`, when a drop would work): bg `--select`, border accent, text accent. Text changes at once. Position `translate(block.x + 6, block.y - 28)` (wire drag: `pointer + (12, -30)`).
- On every drop: lift look, tip, temp wire, target look and map focus go (CSS times; tip at once).
- Refused drop: the mockup has none on the Gateway page. Pattern to copy is the Library plugin drag (1193-1206): tip shows the reason in the plain (muted) style; the target does NOT take the drop look and gets no wire; on release the block flies home (220 OUT3) and the target shakes (translateX 0, -7, 6, -3, 0; 380 ease-out). Reason words are Kitden's to write (D14).

### 6.1 Outside server into its group (Browser, Dropbox)

| Step | Behaviour |
|---|---|
| Start | `.lift`; focus on the block + gateway + its bypass link (`L~o`, shown `.on`). NO tip in the mockup |
| Zone | Block CENTRE x between 330 and 700 and centre y < (original "Outside" caption y - 4). Zone fires only for the block's own group |
| Enter zone | Gateway takes `.drop` look (accent border, select fill, scale 1.05 over 260 SPRING). A slot (dashed preview box 170 x 60, dashed preview link from the gateway) opens at the end of the block's group: grows from gateway right side (gateway right - 85, middle - 30, scale .4, opacity 0) to its place, 220 OUT3, while blocks below move down 70 (all glide 220). Dragged block is skipped by the relayout |
| Leave zone | Slot shrinks back to the gateway spot, 180 IN3, then removed; blocks move back up 220; gateway look goes |
| Drop in zone (`dropIn` 1009) | Slot removed; block moves onto the slot spot, scale 1, rotation 0, 200 OUT3. Then it becomes a server block in preview (preview look, "Moves in", × on hover) on the same spot; its gateway link fades in 0 -> 1, 300 CALM; the bypass link stays (now to the new block); relayout 260 closes the Outside list up |
| Tray row | key `in~<id>`, icon log-in, title "Move <Name> into the gateway", detail "<Client> keeps it. Its calls go through Kitden's rules.", who "<Client>'s settings", toast "Moved <Name> into the gateway" |
| Drop outside zone / on nothing / over the panel | Block goes home (start x, y), scale 1, rotation 0, 220 OUT3. Tray unchanged |
| Apply | Preview look goes (180), × removed, meta -> lamp + "n of m on"; bypass link fades 240; gateway link turns solid and draws 280 CALM; "<n> servers" rolls |
| Taken out (`moveBack`) | Turns back into the outside block on the spot; new links fade (240); relayout carries it home (260) |
| Panel route | "Move into the gateway…": slot opens (relayout 260), then block moves onto it (200) |

### 6.2 Gateway server onto a client

| Step | Behaviour |
|---|---|
| Start | `.lift`; focus on block + all clients + its gateway link (`.on`); tip "Drop on a client" (muted) |
| Target | Pointer (map coords) inside a client box widened 24 left, 40 right, 16 up, 16 down. First client in order wins; ANY client (also not connected) |
| Over a client | Client `.drop` look; a temp wire `L~drop` (class `preview on`: accent dashes 4/4, 1.7px, .65) from the client's right port to the block's left port appears at once and follows the block; tip "Move into <Client>" (accent) |
| Off the client | Client look goes; wire fades out 240 ease-out (`unlink`) |
| Drop on a client | `moveOut(sid, client, {x,y})`: see 4.2. Block becomes the outside preview block ("Moves to <Client>") where it was dropped; two links fade in 320 CALM; relayout 260 carries it into the Outside list |
| Drop elsewhere / over panel | Block home 220 OUT3; tray unchanged |

### 6.3 Free client wire to the gateway (Cursor in the demo; `wireStart` 983)

| Step | Behaviour |
|---|---|
| Who | Client block with `.free` (not connected, no `conn~` row in tray). Press on it (not on a button) |
| Start (after 5 px) | Selection lets go; focus on client + gateway (no links); a wire path (`lk preview`: accent dashes 4/4 at .65, 1.2px) from the client's right port to the pointer, curve with handles max(18, half the x distance); tip "Drop on the gateway". The client block itself does not move |
| Over gateway | Pointer inside gateway box widened 24 each side, 16 up and 16 down: gateway `.drop` look; wire end snaps to the gateway's LEFT port; tip "Connect <Client>" (accent) |
| Drop on gateway | Wire removed at once; `connect(cid,true)` (4.1): preview link fades in 300 CALM; tray row "Connect <Client> to the gateway" |
| Miss | Wire fades 1 -> 0, 180 CALM, then removed. Tray unchanged |
| Apply | See 4.1 |
| After connect | Client is no longer `.free`, cannot be dragged |

### 6.4 Marketplace row onto the map (Phase 5; note only)

Start (row not in gateway and not in preview): row drops to opacity .4 (`.dragging`); a copy (`.flier.ghost`, fixed, z 60, `--shadow`, grabbing) follows the pointer. Zone: pointer x 180-760, y from -20 px to Outside caption y - 4 (map space), not over the panel. Enter: ghost border accent + select fill (180); slot opens and gateway lights (relayout 220). Drop in zone: ghost flies onto the slot and resizes to 170 x 60, 200 CALM, removed; row returns to full; server appears in preview on that spot, link fades in 300; row shows "In preview". Miss: ghost flies back onto its row, 180 CALM, removed. D24: no tool counts.

---

## 7. Map <-> List, find, project switch (Task 4.8)

### 7.1 View switch (`setView` 1032, `swap` Calm branch 1039)

- Pill `#viewseg`: segmented "Map" | "List". `.seg`: padding 2, gap 2, bg `--inset`, border 1px line, radius 7; buttons padding 4px 11px, 12px, radius 5, `--muted`; pressed = `--ink`, weight 500; raised mark (bg `--raised`, radius 5, shadow `0 1px 2px rgb(0 0 0/.25)`) glides left+width 280 CALM; label colour 180.
- On click: aria-pressed set, pill glides; selection lets go (panel out 180); dock cleared (toast leaves 160 ease-in) if the tray is empty; guarded while switching.
- Old view: opacity 1 -> 0, translateY 0 -> -4px, 120 ease-in; then hidden (map `display:none`; list emptied); new view shown: opacity 0 -> 1, translateY 6 -> 0, 260 CALM. (Rich morph: not built.)

### 7.2 List layout (`listHTML` 1028, CSS 188-200)

- List width 912, 12px. Header `.lh` 30px, 11px `--muted`, bottom border: grid `minmax(0,1fr) 130px 150px 100px`, gap 12, padding 0 12; columns "Name", "Used by", "Tools", "" .
- Group row `.lg` 30px: `cloud` 13 "Remote" / `hard-drive` 13 "Local" (11px, 600, `--ink-2`, bottom border).
- Server row `.lr` 40px (bottom border, hover bg `--dim` 180, `.sel` bg `--select`): name cell (bold) = `chevron-right` (or `chevron-down` for the open server; the mockup hard-codes GitHub open) 13 + name; "Used by" = 20px client logo tiles (Claude Code, Codex); "Tools" = "<n> of <m> on" (or amber "Sign in needed" -> D23); end = `chevron-right` 14 (or "Sign in…" -> D23).
- Tool row `.lr.sub` 34px, padding-left 44: mark + tool name + faint "Read" / "Write" (weight 400; note: the panel says "Reads only" / "May write").
- Outside group: row `.lg` with `info` 13 and the words "Outside the gateway · calls skip Kitden's rules" (the List keeps the OLD wording; "· drag one in" is only on the map caption because the List has no drag; keep the pinned List words). Outside rows: name + icon 13, "Used by" = client tile, "Tools" = "<n> tools" (D24: drop), end `btn sm` "Move in…".
- Only tool rows respond to click: row -> `.sel` (the old one goes back), Tool panel loads (skeleton + rise, as 3.1). No selection by other rows. After a project pick the list re-renders at once.

### 7.3 Find (`filter` 1055; input line 428, 1343)

- Input: top bar, `search` icon 14, placeholder "Search your setup and marketplaces…", aria-label "Search the map", `type=search`. Each keystroke (trim, lower case) calls `filter(q)`; page switch clears it.
- Map class `find` is on while q is not empty. A block whose lower-case name does NOT contain q gets `.miss`: `filter: opacity(.3) saturate(.5) blur(1.2px)` (dim to 30 %, desaturate to 50 %, blur 1.2px; 300 ease). Every link: stroke-opacity .2 (300 ease). Captions stay. Empty text -> all back.
- The plan's "dim to 35 %" differs: the mockup and spec M6 say .3 (30 %). Spec/mockup value is .3.
- No result chip in the mockup. Kitden's existing chip (`findChip` in `map.js` ~481) says "N match(es)" / "No matches"; keep it unless the owner says otherwise (mockup is silent).
- Marketplace results are Phase 5 (the placeholder already promises them).

### 7.4 Project switch in place (`setProject` 1333 -> `Gateway.project` 1020)

All Calm values:

| What | Behaviour |
|---|---|
| Top bar | Project name in the button rolls (text always goes down; 140 ease-in + 200 CALM); turns accent at once (`.acc-on`) |
| Scope line | Text swaps; opacity 0 -> 1, translateY 4px -> 0, 320 CALM. Words: "Project <P> · <n> rule(s) differ(s) from the shared setup" (n = tools with an own rule in P; "1 rule differs", else "rules differ", "0 rules differ"); All projects: "Shared setup · project overrides stay separate". Icons: `folder` 14 accent / `layers` 14 muted |
| Each server | "n of m on" rolls; lamp pops 2.2 -> 1 (200 CALM) if it flips |
| Each tool block | Re-rendered (`toolHTML`); tag pops opacity 0, scale .7 -> 1 (200 CALM) |
| Tool whose effective state flips | Mark pops 1.9 -> 1 (200 CALM) and changes colour (400); link draws in 240 CALM (now on) or undraws 380 RETRACT (now off) |
| Panels | Open Tool or Server panel (not in the picker step) steps forward (130 + 220). Other panels unchanged (mockup: Client panel "Projects" row stays stale) |
| List view | Re-rendered at once |
| Tray | Stays (D15). Quirk: tool blocks lose their pending tag / dashed mark ring (5) |
| Rich sweep | Not built |

Other pages: scope text and colour change at once (not Gateway).

---

## 8. Page head and hint line

- `head('Gateway','Connect your agents. Shape what they can use.','',true)` (line 647, 1303). Layout: flex, space-between, gap 16, `align-items:flex-start`.
- Title `h1`: "Gateway", 24px / 600 / -.018em. Lede: "Connect your agents. Shape what they can use." 12px `--muted`, margin 4px 0 0. Scope line: margin-top 12, 11px `--muted`, gap 6, icon 14: "Shared setup · project overrides stay separate" (layers icon) or accent "Project <P> · <n> rule(s) differ(s) from the shared setup" (folder icon).
- Right: Map | List pill (7.1) and the study chip "Demo data" (not built). D? Phase 2 carried note: the pill should sit at the mockup's right edge (page max-width).
- "+ Add" lives in the "Servers" caption on the map (x 396, y -4), `btn xs`, `plus` 12 + "Add"; goes `.primary` while the Add panel is open (Phase 5 opens it; "Add a server…" in the Gateway panel does too).
- Page entrance (`go` 1317, Calm): h1 rises 6px / 260 CALM at 0; lede at 120; scope at 180 (each 260 CALM); map blocks rise 6px / 260 OUT3, 22 apart in layout order (captions Clients, Gateway, Servers, clients, gateway, Remote cap + its servers, Local cap + its servers, Outside caption + outside blocks, then Tools caption and tools if a server is open). Hint text swaps at once.
- Hint line (`.hintline` 75-77: absolute, left/right 22, bottom 14, z-index 2, 11px `--muted`, no pointer events; `info` 13 + text; right side `#tag` is a study label, not built): exactly

  "Point at a link and press × to remove it · click anything for its Details · several changes wait in preview, then Apply all · drag a server onto a client"

- Main: `padding: 26px 22px 64px`; stage `margin-top 22`, `padding 6px 6px 10px 6px`, `margin-left -6px`, `overflow-x:auto`.

---

## 9. Mockup quirks and gaps (do not copy blindly)

1. `project()` drops pending tags / `.mark.pv` (5). Fix in Kitden.
2. `selectTool` on the same tool does not let go (spec M2 and plan 2.6 say a second click lets go).
3. Tool/outside/marketplace counts and sign-in wording are demo; D23/D24 remove them (see 0b).
4. "Claude Code and Codex" and "2 clients" / "2 plugins · 3 skills" are hard-coded; use the real connected clients and counts.
5. Outside-server drag has no tip in the mockup; spec M5 lists no tip either. Refusal tip is Kitden's to add (D14).
6. Mockup Server panel has no "Remove from the gateway" button (only the link ×); D18 keeps the old action.
7. `setConn` replaces the lamp element (no colour fade). `Object.assign(n,{... })` for the "Tools" caption origin is `{0,0}` when created (Calm sets it to final place, so unseen).
8. Gateway/Client panels do not react to a project change.
9. "clients" / "servers" never singular in the gateway stats.
10. Mockup Cursor "1.9 · not tested" and "Signed in there" second line (outside block 66px) are removed by D24 / D23.
11. List keeps "Outside the gateway · calls skip Kitden's rules"; map caption uses "· drag one in" (D7).
