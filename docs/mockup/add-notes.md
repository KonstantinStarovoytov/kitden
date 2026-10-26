# "+ Add" panel and marketplace servers in the mockup: notes for the build (Calm only)

Sources read in full: `docs/mockup/kitden-motion.html` (v11), `motion-spec.md` M5 and M6, `gateway-notes.md`. Line numbers are in
`kitden-motion.html` unless marked. "Calm" = `S.rich` false. `D(ms)` = 0 under reduced motion. Default Web Animation ease =
CALM `cubic-bezier(.2,.8,.2,1)`, fill `backwards`, default 300 ms. OUT3 = 1-(1-t)^3, IN3 = t^3.

| Thing | Function / CSS | Line |
|---|---|---|
| Open the panel | `Gateway.openAdd` | 931-936 |
| A result row | `Gateway.resRow` | 937-939 |
| Click adds a preview | `Gateway.preview` | 940-951 |
| Drag a row | `Gateway.resDrag` | 953-967 |
| Take the preview out | `Gateway.unpreviewAdd` | 968-970 |
| Apply lands | `Gateway.commitAdd` | 971-976 |
| Undo | `Gateway.removeServer` | 977-980 |
| Gateway lights | `Gateway.lightGw` (CSS `.blk.drop` 318) | 981 |
| Panel shell, skeleton, close | `openPanel` 532, `skeleton` 533, `panelLoad` 534, `closePanel` 539; `.panel` 202 | |
| Row CSS | `.search` 221-222, `.res-g` 223, `.res*` 224-236, `.flier` 186, `.itile` 126, `.grip` 153, `.slot` 160, `.seg.sm` 90 | |
| Sample data | `TOOLNAMES` 578, `GWD.market` 586-587, `KIND` 577 | |
| Tray row, Apply, toast | `tray` 606-642, `dock.toast` 542 | |

## 1. Where "+ Add" lives and what opens

- Two doors, both call `openAdd()`: the `+ Add` button in the "Servers" caption on the map (`btn xs`, `plus` icon 12, text "Add";
  caption box 200 x 26 at x 396, y -4; click handler 705), and "Add a server…" (`plus` 13) in the Gateway panel (761-762).
- `openAdd` first calls `clearSel()` (the old selection lets go, map focus off, the old panel closes at 180 ease-in), then opens a
  new panel with the skeleton and loads the content after `D(160)`; the children then rise (`rise`, step 20, y 6, 260 CALM).
- "+ Add" gets `.primary` at once (button colour/border transition 180 ms) and loses it when the panel closes through its own ×
  (`onClose`, 933). Any other close (selecting something else, `clearSel`) does not run `onClose`; the mockup leaves `.primary` on
  then. Kitden should clear it on every close.
- Panel (the shared side panel, 202): `position:absolute; right:22px; top:190px; bottom:46px; width:min(320px, 100% - 44px)`;
  z-index 20; panel fill, 1px `--line`, radius 10, padding 18, flex column, gap 16, `--shadow`, `overflow:auto` (scrolls).
- Open (first time only): opacity 0 -> 1, translateX 28px + scale .98 -> none, 240 CALM. Close: opacity 1 -> 0, translateX 0 -> 22px,
  180 ease-in, then removed. If another panel is open, the old one closes while the new one opens (swap rule M2).
- Header (`.p-kick`): "Add a server" (15px, 600, `--ink`) on the left; `×` button (`.x`, 24 x 24, radius 6, `x` icon 14,
  `aria-label="Close"`, hover fill `--dim`) on the right. Clicking × closes the panel and runs `onClose`.
- Focus: the mockup does NOT move focus into the panel, does NOT trap it, does NOT return it, and has NO Escape handler (no
  `Escape` anywhere in the file). Closing is only ×, or opening another selection. (Build: see section 8.)
- Skeleton shown while loading: a "Add a server" kick row with ×, two grey bars (62 % x 16px, 38 %), five bars between lines
  (70/54/80/46/60 %), then bars 90 % and 55 % x 30px. In Calm they do not shimmer.

## 2. The panel's parts (top to bottom, 534 / 932)

1. Search: `label.search` (flex, gap 8, padding 8px 10px, 1px `--line`, radius 7, fill `--inset`, colour `--muted`), `search` icon 14, input
   `#mq` (12px, `--ink`). Placeholder: **"Search the marketplaces…"**. aria-label: "Search the marketplaces". No autofocus.
2. Filter pill (`.seg.sm`, left-aligned, `align-self:flex-start`): **All** (pressed), **Community**, **Team**. Buttons padding 3px 8px,
   11px. The raised mark glides to the pressed button, 280 CALM (starts in place with no motion when the panel loads). It does NOT
   filter anything in the mockup (spec M6 says so). Intended meaning, from the group names: All = both groups; Community = the
   "Community marketplace" group; Team = the "Team marketplace" group.
3. Results `#mres` (flex column, gap 8). Groups in this order, each = a caption then its rows:
   - Caption `.res-g`: `store` icon 13 + source name, 11px / 600 / `--ink-2`, margin-top 4. Names verbatim: **"Community marketplace"**,
     then **"Team marketplace"**. There are no other captions and no counts in them.
   - Rows (below).
4. Footer (`.p-tech`, pushed to the bottom, top border, 12px `--muted`, `info` icon 13, gap 6): **"Click a server or drag it onto the
   map to preview it."**

### The row (`resRow`, 937-939; CSS 224-236)

- `div.res`, `role="button"`, `tabindex="0"`, data `mk` (id) and `name` (lower case). Flex, gap 10, padding 9px 10px, 1px `--line`,
  radius 8, panel fill, `cursor:pointer`. Border and fill transition 180 ms.
- Left to right:
  1. Grip: `.grip` `grip-vertical` icon 12, `--faint`, `cursor:grab`, margin-right -4.
  2. Icon tile `.itile` 26 x 26 (radius 6, 1px `--line`, `--inset`), icon 14 (the server's icon).
  3. Text `.tx`: name `<b>` 12px; below it `<small>` 11px `--muted`: "**Remote · 8 tools**" (group word capitalised: "Remote" or
     "Local", then the tool count). No description line.
  4. Status `.st` on the right, 11px `--faint`: see the words below.
- Words in the status slot (first match wins):
  - Team-marketplace server already in the gateway when the panel opens (data flag `inGw`; only GitHub): **"In the gateway"**.
  - Added by Apply while the panel is open or re-opened (a gateway server that is not in preview): **"Added"** in `--ok` green.
  - Server is in the tray as a preview: **"In preview"** (accent colour).
  - Server needs sign-in: `key-round` icon 11 + **"Sign-in"** (faint). Nothing otherwise (empty).
- Row states:
  - Hover: border = 40 % accent mixed with `--line`, 180 ms.
  - `.on` (in preview): fill `--select`, border `--accent`, status accent.
  - `.off` ("In the gateway" / "Added"): opacity .55, `cursor:default`, no click, no drag. Hover border still tints (no `.off:hover`
    rule), spec M6 says "no hover"; treat as none.
  - `.dragging` (the row being dragged): opacity .4.
- Refused rows with reasons: the mockup has none. Only "In the gateway" greys a row and it gives no reason beyond those words.
  (The Library page has `dropWhy`, 1193-1206, a refusal pattern to copy; not used here.)
- Search (935): on each input, `q` = trimmed, lower case. A row is a hit if `q` is empty or its lower-case NAME contains `q` (name
  only; not group, source or description). A row that stops matching gets `hidden` at once (no motion). A row that matches again is
  un-hidden and animates opacity 0 -> 1, translateY -4px -> 0, 240 CALM. Group captions never hide, even if all their rows are
  hidden. The pill choice is ignored.

## 3. A click on a row (`preview`, 940-951)

- Click handler (934): ignored while `this.dragged`; ignored on `.off`; otherwise `preview(id, row)`.
- If the server is already a preview: the click TAKES IT OUT (`tray.remove('add~<id>')`). So a second click on an "In preview" row
  undoes the first. If it is already in the gateway (not preview): nothing.
- If another server is open (tools unfolded) it closes (`.open` removed).
- Adds a server object with `preview:true`, all tools `on:false`, `signin` flag, kind per tool name (`KIND`: names starting List, Get,
  Search, Read, Describe, Explain, Take, Wait, Open, Go = "Read", else "Write"). Appended at the END of `GW.servers`; the layout puts
  it last in its group (Remote or Local) because the layout filters by group.
- The row at once: class `on`; status text becomes **"In preview"**.
- Map (Calm click, no drop spot): `relayout()` only. The new block starts at the gateway's right side (`origin`: x = gateway x +
  width - 85, y = gateway middle - 30, scale .4, opacity 0) and grows to its slot in the group, 260 CALM-timed `relayout` move (spec:
  "scale .4, opacity 0 to its place, 260 OUT3"); blocks below make room in the same move (260). Its link (gateway right port ->
  block left port, class `preview`) is created with the block and is drawn as part of the move. Rich only: a flier copy of the row.
- Block look in preview: 170 x 60, class `blk srv preview`: fill `--preview-fill`, 1px DASHED `--preview-line`; icon tile 15, name,
  small line = dashed lamp `.lamp.pv` + accent text. Mockup text: **"Preview · N tools"**. Badge circle with the tool count (`.badge`).
  Title attribute: "In preview. Click to take it out." On hover/focus the `.unx` `x` badge shows (18px circle, top -8 right -8).
  Link: accent dashes 4/4 at .65 opacity. Clicking the block (or its ×) takes it out of the preview (wire 705).
- Tray row (`tray.add`, key `add~<id>`, icon `plus`):
  - Title: **"Add <Name> to the gateway"**
  - Detail: **"<Remote|Local> · <n> tools, all off until you turn them on."** plus **" Sign in after Apply."** if sign-in is needed.
  - `who` (used only in the failure text): **"Claude Code's settings"** (hard-coded; wrong for other clients).
  - Toast on success: **"Added <Name> to the gateway"**. One row: bar shows title, detail, `Cancel`, `Apply`. Several rows: "N changes
    in preview", list, `Cancel all`, `Apply all`. Bar in 220 (first), new row 200 with 80 delay.
- Taking it out (second click on the row, click on the block or its ×, the tray ×, or Cancel): `unpreviewAdd` (968-970): server removed
  from the list; row loses `on`, status back to "Sign-in" (with icon) or empty; link unlinks (fade 240); block moves back to the
  gateway origin and fades, 180 IN3 (Rich 380) while the blocks below move up 260; then the node is removed.

## 4. Dragging a row (`resDrag`, 953-967)

- Start: pointer down, left button, on a row that is not `.off` and not `.on` (so a row already in preview or in the gateway cannot
  be dragged). Pointer capture on the row.
- Threshold: 5 px (`Math.hypot(dx, dy) < 5` means still a click). Past it: `this.drag = true`; row gets `.dragging` (opacity .4);
  a ghost = clone of the row (`.flier.ghost`) is appended to `body` at the row's rectangle (fixed, z-index 60, `pointer-events:none`,
  `overflow:hidden`, `--shadow`, `cursor:grabbing`) and moved with `transform: translate(dx, dy)`. The ghost keeps the row's own size,
  grip, icon, name, small line and status ("In preview" is not shown; it is not a preview yet).
- Zone (want the slot): pointer not over the panel, and in map space (pointer minus map host origin) x between 180 and 760 (exclusive),
  y greater than -20 and less than the Outside caption's y minus 4. In zone: ghost gets `.over` (border `--accent`, fill `--select`,
  180 ms) and the slot opens in the server's own group (`it.group`: Remote or Local). Out of zone: both undone. The zone is the
  same for both groups; the slot goes where the server's group is, not where the pointer is.
- Slot: a 170 x 60 box (`.slot`: 1px dashed `--preview-line`, radius 8, fill `--preview-fill`) placed after the last server of that
  group, with a preview-style link from the gateway. It appears and the blocks below move down in `relayout({dur:220})` (Rich 420).
  Leaving the zone: the slot closes the same way.
- Gateway lights (`lightGw`, 981): `.blk.drop` on the gateway = border accent, fill `--select`, scale 1.05 (transition on border,
  fill 180; scale 260 with the spring var). Rich: ripple .45 once on entering.
- No drag tip text for this drag (only the other drags show `.dragtip`).
- Drop in the zone: the ghost flies from its place to the slot and resizes to 170 x 60, 200 CALM (Rich 380 SPRING), then is removed;
  row loses `.dragging`; the slot is removed; `preview(id, row, {x, y})` runs with the slot's position: the block appears there at once
  (170 x 60), its link fades in 300, the layout re-settles, then the same row, tray row and words as a click (section 3).
- Drop outside the zone, or over the panel, or anywhere else: the ghost flies back onto its row (translate to none, original size),
  180 CALM (Rich 320), then is removed; row back to full opacity. Nothing is added. A drop over the panel is the same as a miss.
- `pointercancel` is treated like `pointerup`. `Escape` does not cancel a drag.
- After a drag, the click is swallowed (`this.dragged` stays true for one tick) so a drop does not also count as a click.
- Keyboard: none for the drag.

## 5. Apply and Undo for an added server

- Apply (`tray.apply`): the same tray flow as every change. Steps = rows + 1; each row shows a spinner, then a check (D20 in the
  plan: checks together at verified). Fail: "Nothing was changed" with "<who> changed while Kitden was writing. Kitden put the files
  back." and `Try again`. Success: button reads "Applied" (or "All applied") with check; 200 ms pause; then each row's `onCommit` in
  turn, 60 ms apart (Calm).
- `commitAdd(s)` (971-976), in this order, at the same time:
  - Block: preview class and title removed; `.unx` removed; its small line is replaced by the normal meta; scale 1.06 -> 1 (Calm: 1 ms,
    i.e. none; Rich 520).
  - Meta after Apply: lamp + "**0 of N on**" (all tools off). Mockup also shows "Sign in needed" with an amber lamp for sign-in
    servers (D23 removes it).
  - Link: class `lk` (solid) and it draws in 280 (Rich 560 + a beam).
  - "servers" number on the gateway rolls (140 ease-in + 200 CALM) to the new count of non-preview servers.
  - Row in the open Add panel (if open): loses `.on`, gets `.off` (opacity .55), status becomes **"Added"** in `--ok`, slides in
    from translateX 6px, opacity 0, 280 CALM.
  - If the panel is closed, none of the row lines run (they only touch rows that exist).
- Toast (`dock.toast`): "Added <Name> to the gateway" with check icon, button "Undo" (`undo-2` 13). For several rows: "Applied N changes"
  and "Undo all". The toast lives 9000 ms (bar shrinks on its bottom edge).
- Undo (`removeServer`, 977-980): server removed from the list; the link retracts (undraw 380), the block shrinks back into the gateway
  (180 IN3; Rich 360) while the blocks below move up (260); the "servers" number rolls back; open Add-panel row loses `.off`; status
  becomes plain "Sign-in" (no icon) or empty. Undo-all runs the rows in reverse, 120 ms apart.

## 6. Empty states, no-results and the sample rows

- No-results: NONE in the mockup. With a query that matches nothing, every row hides and only the two group captions and the footer
  stay. There is no "No matches" line, no empty text, no loading, no error state, no "offline" state.
- No empty marketplace state either (the list is fixed).
- Data (`GWD.market`, 586-587; `TOOLNAMES`, 578). Fields per item: `id`, `name`, `icon` (Lucide name), `group` (`remote`/`local`),
  `signin` (bool), `inGw` (bool).

| Source | id | Name | icon | group | signin | inGw | Tools in `TOOLNAMES` | Row small line | Status |
|---|---|---|---|---|---|---|---|---|---|
| Community marketplace | sentry | Sentry | bug | remote | yes | | 8 | Remote · 8 tools | key + Sign-in |
| Community marketplace | postgres | Postgres | database | local | | | 4 | Local · 4 tools | (empty) |
| Community marketplace | playwright | Playwright | monitor-play | local | | | 12 | Local · 12 tools | (empty) |
| Team marketplace | jira | Jira | square-kanban | remote | yes | | 9 | Remote · 9 tools | key + Sign-in |
| Team marketplace | github | GitHub | git-branch | remote | | yes | none (falls back to 4) | Remote · 4 tools | In the gateway |

- Tools: sentry = List issues, Get issue, Search events, Get event, List projects, Resolve issue, Assign issue, Add comment;
  postgres = Run query, List tables, Describe table, Explain query; playwright = Open page, Read page, Take screenshot, Wait for text,
  Go back, Click, Type text, Fill form, Select option, Upload file, Press key, Close page; jira = Search issues, Get issue, List
  projects, Create issue, Update issue, Add comment, Move issue, Assign issue, Log work. A server with no list gets "Tool one … four".
- Note: GitHub is also a built-in gateway server in the map (`GWD.servers`), so the Team row greys as "In the gateway". The
  gateway's own servers (GitHub, Linear, Filesystem) are not marketplace rows except GitHub.
- The top-bar "Search your setup and marketplaces…" (line 428) only dims map blocks (`filter`, 1055); it does not list marketplace
  results. Gateway-notes 7.3 marks that as Phase 5 work.

## 7. OAuth, SSE / WebSocket, `${...}` values, tool counts

- OAuth, SSE, WebSocket, `${...}` / environment values, URLs, commands, tokens: NOT in the mockup anywhere in the Add flow. No form
  asks for a URL, command, header or key. A row is added with one click and nothing to fill in.
- Sign-in: rows show `key-round` + "Sign-in"; the tray detail says " Sign in after Apply."; a "Sign in…" button is on the Server panel
  of such a server (886). Plan decision D23 removes all of this in Kitden.
- Tool counts: row small line "Remote · 8 tools"; block meta "Preview · 8 tools"; badge number; tray detail "· 8 tools, all off until
  you turn them on." Plan decision D24 removes the counts for marketplace servers. After Apply the meta is "0 of 8 on".
- "all off until you turn them on" is the mockup's rule: a newly added server starts with every tool off.

## 8. Keyboard and accessibility

- Rows: `role="button"` and `tabindex="0"`, but NO keydown handler on rows. Enter and Space do nothing in the Add panel (the map's
  Enter/Space handler, 707, only works for `.blk`). Build: add Enter/Space on a row = the click.
- × has `aria-label="Close"`; search input has `aria-label="Search the marketplaces"`. Pill buttons use `aria-pressed`. The pill has
  no `role` or arrow keys.
- No Escape, no focus move into the panel on open, no focus return on close, no live region for "In preview" / "Added". The toast has
  `role="status"`. Reduced motion: every `D()` becomes 0 and CSS transitions are off.
- Ghost and drag are pointer-only; the click path is the keyboard path.

## 9. Differences to note (clashes with Kitden's rules)

1. Only a preview, write on Apply: the mockup matches. Click and drop both add a preview plus a tray row and nothing else; the
   write happens only in `commitAdd` after Apply. No clash. One small gap: the mockup keeps the row's status in sync by direct
   DOM edits, not by state; Kitden should rebuild the row from the preview list.
2. Main pages show no paths / addresses / commands: the Add panel shows none (no URL, no command, no env). Clash only on the
   tray: `who` = "Claude Code's settings" is shown on failure; it names a client, not a path, so it is fine, but it is hard-coded.
3. Tool counts and sign-in words (rows, block meta, tray detail, badge) clash with plan decisions D23 and D24. Kitden shows
   "Remote" / "Local" without a count and no "Sign-in"/"Sign in after Apply".
4. Block meta "Preview · N tools" and "0 of N on" after Apply: with no count, show just "Preview" and a plain "Added"/"On" state.
5. Panel `.primary` state on "+ Add" is not cleared on every close (only on ×). Fix in Kitden.
6. No refusal reasons, no no-results text, no error/loading for marketplace data: Kitden must add these (plain words, short).
   The Library's `dropWhy` (1193-1206) is the pattern for a refusal; D14 says a refused drop says why.
7. The filter pill does nothing in the mockup; Kitden needs a real rule (All / Community / Team by source).
8. Search matches the name only and never hides captions; Kitden should also hide an empty group's caption and show the empty text.
9. The mockup never says where a marketplace server's launch details come from (a real server has a command or URL). If Kitden
   writes one on Apply, the tray row must say what is written ("Details" for the command/URL), not the main row.
10. Added servers use the group (Remote/Local) from the sample data; a real entry needs a rule for it (URL = Remote, command = Local).
