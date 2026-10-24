# Part 4: The Gateway map and list — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Gateway page becomes one tree (clients → gateway → servers → tools) with a List view, Details in a column beside it, find, a project menu, and a preview on the map; the shared pieces S.1–S.8 that Parts 5 and 6 reuse are built on the way.

**Architecture:** A probe first: the map core `map.js` (pure layout, lighting and find, tested in node, plus one renderer of HTML blocks over one SVG) draws today's data, and the controller measures it before anything else is built. Then the shared pieces: the words pass, tokens and docked Details, the project menu. Then the Gateway: more data in `/api/gateway-view` (no new request at start), the List with Details for every block, the map, find, and the review bar with drag. Every write still goes through the change engine.

**Tech Stack:** Python 3.13, Starlette; plain ES modules and one CSS file; pytest on sandbox homes and the Part 1 samples; node's test runner. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-10-23-map-pages-design.md`, "Shared pieces" S.1–S.8 and "Part 4" (4.1–4.6), with its Owner decisions, Anti-goals, Constraints and Calls. Master plan: `docs/superpowers/plans/2026-10-22-visual-management.md`; its Rules and "Names that cross part boundaries" bind this plan. Frames: D1–D5, G1, P1, F1, R1, N1, T1, A1–A3 (`design/kitden.pen`, text in the owner's design doc).

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments, UI and docs; tests on sandbox homes only (`make_home`, `write_cursor_fixture_state`, `build_demo_home`, Part 1's `demo_page`); conftest guards stay on; dated facts about other tools; no real client command, server, Keychain or network.
- Every change to a client's settings: preview → Apply with a backup → verify → Undo, through `src/kitden/changes/engine.py`. A drag or a map preview only starts a preview request.
- The Move preview stays as it is, also when it reads a Codex server's tools because its entry has `enabled_tools` (owner ruling 2026-10-24: the spec's anti-goal about asking a server for its tools covers marketplace servers only). A drop uses that same preview.
- Main pages show a name, the client and an action. Paths, addresses and commands stay under Technical details.
- Stack unchanged; strict CSP; no library; the map is plain SVG under HTML blocks; system fonts stay.
- `docs/design.md` changes in the same commit as the page change it describes; every new page word is pinned in `tests/unit/test_page_words.py` in that commit; `tests/unit/test_contrast.py` keeps 4.5:1.
- `explain()` and `project_views()` feed the read-only MCP server: a task that touches them runs `tests/unit/test_mcp_server.py`.
- Owner words (2026-10-23), exactly: "On", "Off", "N of M on", "On in this project", "Turn on for all projects…", "Turn off for all projects…", "Turn on in one project…", "Turn off in one project…", "Use the shared rule…", "Use <folder>'s rule…", "This project", "Only this project", "Via Claude Code". No sign-in words: no "Sign in needed", "Sign in…", "Signed in there", "Sign in after Apply". No tool count for a server outside the gateway.
- Spec copy, exactly: "Shared setup · project overrides stay separate"; "Project <name> · N rules differ from the shared setup"; "Find a project…"; "What applies in every project"; "1 own rule"; "N matches"; "Connected", "Not connected", "Found · <version>"; "No gateway yet", "Set up…"; "Drop to add"; "Outside the gateway · calls skip Kitden's rules"; "Move in…"; "Applying 2 of 3"; "Writing Claude Code's settings. A backup is kept."; "Nothing was changed."; "Try again"; "Show changes"; "Server off"; "12 calls · last today 14:02"; facts "Read only", "May write", "Not reported".
- Numbers from the spec: blocks 150–200 px wide and 34–54 px high; an unfold at most 300 ms, children 15 ms apart, no extra delay after the sixth; Details 320 px, docked at 1024 px and wider; narrow under 1024 px, or with Details open under 1280 px; List first past 15 servers (`MAP_AT = 15`); a group over 6 shows 5 and "N more"; find dims to 35%; probe: drawing under 50 ms on 20 servers, layout of the large sample under 16 ms.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`. Stage files by name; a short plain subject, one to three lines, ending with the session's co-author line.
- `ROADMAP.md`, `design/`, `docs/research/visual-redesign-final-2026-10-23.md` and `docs/research/visual-management-ux-concept-2026-10-22.md` are never edited or staged.
- `tests/unit/test_page_words.py::test_gateway_wires_do_not_fake_traffic` bans the letters `flow` in `gateway.js`; from Task 1 it bans them in `map.js` too ("overflow" included, even in comments).

## Review Focus

1. **The large sample** (12 held servers, 157 outside rows, names over 40 characters): the Gateway opens in List, the map layout stays under 16 ms, and every long name is cut with "…" with the whole name in its label. Task 1 `the layout of 20 servers and of the large sample stays under 16 ms`, `a long name is cut and keeps its whole name in its label`; Task 6 `the large sample opens in List`.
2. **A server off in the picked project by a parent project's rule:** its tools are off with "Server off", `on_count` is 0, Details says "Off · server off" and offers no tool action. Task 4 `test_a_tool_of_a_server_that_is_off_is_off`; Task 7 `a tool of a server that is off says so and offers nothing`.
3. **A settings file that breaks while the page runs:** its outside rows are kept from the last good read, and get no grip and no "Move in…". Task 4 `test_a_row_kept_from_the_last_good_read_stays`; Task 8 `no grip where the row stays`.
4. **One name in two outside groups** (the medium sample's `docs`: Claude Code remote, Codex local): two blocks with their own ids, each with its own amber line, find lights both, and a drag of one moves only its own entries. Task 6 `one name in two groups is two rows`; Task 9 `find lights both docs`; Task 10 `a drag takes only its own row's entries`.
5. **Keyboard only, a narrow window, reduced motion:** every block is a button in reading order; the List moves with the arrows, Right and Left fold, Enter opens Details; tools unfold down under 1024 px or with Details docked under 1280 px; "Move in…" is the drag's keyboard path; with reduced motion nothing waits. Task 1 `narrow: tools unfold down…`, `unfold: … reduced motion …`; Task 6 `the list moves by keys`; Task 8 `every block is a button in reading order`.

## Names this part shares with other parts

- Consumes (Part 1): `build_demo_home(root, size)`, `demo_build(home)`, `create_app(..., demo=True)`, `demo_page(root, size="medium")` and `POST` from `tests/unit/test_demo_mode.py`; the medium sample contract (`~/work/atlas`, `~/work/atlas/web`, held `files` and `tracker`, `files.write_file` off in atlas, `files.search_files` off in atlas/web, `tracker.export_report` waiting, Cursor's direct `files`, `docs` in two clients).
- Consumes (Part 2): `ALL_PROJECTS`, `STATE_WORDS`, `ORIGIN_WORDS`, `Cell.origin`, `Cell.route`, `ROUTE_WORDS`, hash `sel`, `parseSel`, `selFor`, `goTo`, `takeArrival`, `Item.stale_at`.
- Consumes (Part 3): `panel.js` shell, `details.js` (`moveInto`, `moveTargets`, `heldActions`, `heldButtons`, `contextLinks`, `linksRow`, `techRows`, `technical`, `keepFrom`, `DETAILS_ORDER`), `review.js` (`review`, `changeWords`, `changeOutcome`, `undoChange`, `reviewLede`, `PLACE_IN_TITLE`), `tools.js`, `/api/explain` → `{definitions, inherits}`.
- Produces, with the master plan's names: CSS tokens `--dim`, `--preview-fill`, `--preview-line` (Task 3); `openPanel(content, { instant, dock })`, `DOCK_MIN = 1024` (Task 3); `factsBlock(rows)` (Task 3); `map.js` `layoutTree`, `litPath`, `findIn`, `drawMap` (with `onAdd(columnId)`) and the tree model, whose columns carry their block sizes and whose group blocks may have `details` (Task 1); `cutName(name, max = 24)` in `dom.js` (Task 1); hash `view=map|list`, `MAP_AT`, `viewMode(state, count)` (Task 1); `projectMenu(projects, picked, onPick)`, `/api/projects` items with `own_rules` (Tasks 4–5); `reviewBar(change, { onApply, onCancel, onShow, body })` (Task 10); `held_servers()` rows with `tool_list` and `on_count` (Task 4); `sel=tool:<server>/<tool>`, `sel=client:<id>`, `sel=group:<id>` and `goTo(view, selected, { project, mode })` (Tasks 1, 5); the words of S.1 (Task 2).
- Produces, new for Parts 5 and 6 (in the master plan's names table): the `ORIGIN_WORDS` twin in `parts.js` (Task 2); `docksAt`, `detailsCard` with its action shape `{ label, run?, body?, primary? }`, `more` and `after` (Task 3); `toggleOpen`, `unfoldDelays`, `isNarrow`, `litFrom` (Task 1); `override` on outside rows (Task 4); `menuItems`, `scopeText`, `switchProject`, `setSwitcher` (Task 5); `gridKey`, `arrivalServer` (Task 6); `projectChoice` (Task 7); `findChip`, `MAP_PAGES` (Task 9); `dropAt`, `gatewayTree`'s `preview`, `mapPreview`, `previewOnMap`, `applyOnMap`, `cancelOnMap`, `showMapReview`, `barWords`, `appliedToast`, `moveBody` (Task 10). Each one's module and signature are stated once, in that task's Interfaces.

---

### Task 1: The probe — map core and its numbers (4.1, S.4 core, S.5 address)

**Files:**
- Create: `src/kitden/web/static/js/map.js`, `tests/frontend/map.test.mjs`
- Modify: `src/kitden/web/static/js/dom.js` (`cutName`), `src/kitden/web/static/js/store.js` (mode, `view` in the hash, `MAP_AT`, `viewMode`, `followHash`, `go`/`goTo`, the `tool`, `client` and `group` selections), `src/kitden/web/static/js/gateway.js` (`GATEWAY_COLUMNS`, `gatewayTree`; the map with `view=map`; performance marks), `src/kitden/web/static/style.css` (a `/* Map */` block), `scripts/measure-start.py`
- Test: `tests/frontend/map.test.mjs`, `tests/frontend/store.test.mjs`, `tests/frontend/gateway.test.mjs`, `tests/unit/test_measure_start.py`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces in `map.js`:
  - The tree model (master name): `{ columns: [{id, caption, add, w, h, narrowW, narrowH}], blocks: [{id, column, parent, kind, name, meta, state, tag, count, grip, details}], links: [{from, to, kind}] }`. Each column carries its blocks' size, wide and narrow (`narrowW`/`narrowH` default to `w`/`h`). Block `kind` on the Gateway: `"client" | "gateway" | "group" | "held" | "outside" | "tool" | "slot" | "preview"`; `state` `"on" | "off" | "unk" | "preview"`; link `kind` `"on" | "faint" | "direct" | "preview"`. A `group` block is a caption; with `details: true` it is a button that opens its Details. Its children are the blocks whose `parent` is it.
  - `GAP = 46`, `NARROW_GAP = 28`, `GROUP_H = 22`, `GROUP_MAX = 6`.
  - `layoutTree(model, { open, width, narrow }) -> { columns: [{id, x, w}], blocks: [{id, x, y, w, h}], links: [{from, to, kind, d}], height }`, the same for every map page: column x from the widths and `GAP`; a block takes its column's size; only shown blocks; a group with more than `GROUP_MAX` children shows the first 5 and a block `more:<group id>` (kind `more`, name `` `${n} more` ``); children of a block not in `open` are not shown; wide: children to the right in their own column; narrow (one rule): the narrow sizes, and the open block's children unfold down inside it on a rail. `d` is an SVG path: a cubic for `on`, `faint`, `preview`; an orthogonal elbow with 6 px rounded corners, trunk at x 170, for `direct`.
  - `toggleOpen(model, open, id) -> Set<string>`: opens `id` and closes any other open block of its column and their open children; `id` open → closed.
  - `litPath(model, id) -> Set<string>`: the block, every block on a path to it from each client that reaches it through `on`, `direct` or `faint` links, and those links as `` `${from}>${to}` ``.
  - `litFrom(model, id) -> Set<string>`: what a block (a client) reaches, following those links outward, with the links.
  - `findIn(model, text) -> { matches: Set<string>, open: Set<string> }`: names containing `text`, any case, trimmed; `open` holds every ancestor of a match. Empty text: both empty.
  - `isNarrow(width, detailsOpen) -> boolean`: `width < 1024 || (detailsOpen && width < 1280)`.
  - `unfoldDelays(count, reduced = false) -> number[]`: per child, `LINK_MS + min(i, 5) * 15` with `LINK_MS = 150` (children fade in 60 ms); all 0 when reduced.
  - `drawMap(box, model, layout, { onSelect, onOpen, onAdd, selected = null, lit = new Set(), found = null, drawn = new Set(), reduced = false })`: one `svg.map-links` (`aria-hidden`) of `path.link.<kind>` under absolutely placed `button.block.<kind>` (`group` is a `div.caption`, or a button when `details`; a column with `add` gets a "+ Add" button beside its caption that calls `onAdd(columnId)`); DOM order = reading order, column by column, top to bottom; each button's `aria-label` is the whole name and its state words, `title` the whole name; `data-focus` = `block:<id>`. A link draws (`.draw`, `pathLength="1"`) only when its key is not in `drawn`; `drawn` then holds it. It marks `kitden:map-start` and `kitden:map-drawn` and measures `kitden:map-draw` between them.
- Produces in `dom.js`: `cutName(name, max = 24) -> string`.
- Produces in `store.js`: `state.mode: "" | "map" | "list"` read from and written to the hash key `view` (on `gateway` and `library` only; `""` writes nothing); `followHash` counts `mode` in its same-state keys, so Back switches Map and List; `go(view, params)` and `goTo(view, selected, { mode } = {})` to another place clear it unless a `mode` is passed, which wins; `MAP_AT = 15`; `viewMode(state, count) -> "map" | "list"`: `state.mode` when set, else `"list"` when `count > MAP_AT`; `SEL_KINDS` gains `"tool"` (`sel=tool:<server>/<tool>`), `"client"` (`sel=client:<id>`) and `"group"` (`sel=group:<id>`, the group block's id without `group:`, as `group:outside`); `toolSel(name) -> { server, tool } | null`, split at the first "/".
- Produces in `gateway.js`: `GATEWAY_COLUMNS` (clients 150×54, narrow 132; gateway 150×124, narrow a 56×56 tile; servers 170×54, narrow 220; tools 190×34, narrow rows 30 high); `gatewayTree(view, { setup, clients, open, tools, picked }) -> model`, first version: three client blocks (`client:<id>`, `on` link to `gateway:kitden` when `kitdenClients(setup).linked` has it), the Kitden gateway block, groups `group:kitden:remote` / `group:kitden:local` of held blocks `held:kitden:<name>` (`on` link from the gateway unless the server is off), group `group:outside` of `outside:<move|local|plugin>:<name>` blocks with a `direct` link from each client in `row.clients`, and, for an open held server, its tools `tool:<server>/<tool>` from `tools[server]` (the `/api/gateway/tools` answer in this task; Task 6 switches to `tool_list`); a tool block's `state` and its `on` link come from the tool's `effective` state (Task 4 adds it; until then the probe uses `state`).
- Produces in `scripts/measure-start.py`: `PROBE_SERVERS = 20`; `build_probe(root: Path) -> Path` (the medium sample plus direct servers `probe-01` … in `~/.claude.json` and `~/.codex/config.toml` until held plus outside rows make 20); `measure()` also returns `gateway_view` (seconds to the first answer of `/api/gateway-view`, timed after first usable) and `main()` prints `gateway view: N ms`; `--probe` builds the probe sample, starts the demo page on it, prints the page link and waits for Ctrl-C.

- [ ] **Step 1: Write the failing tests** (`tests/frontend/map.test.mjs`; helpers build models)

```js
const { GAP, layoutTree, toggleOpen, litPath, litFrom, findIn, isNarrow, unfoldDelays } = await import('../../src/kitden/web/static/js/map.js');
const { cutName } = await import('../../src/kitden/web/static/js/dom.js');
// model(held, outside, { tools }) : 3 clients (claude_code, codex linked), the gateway, `held` servers in remote/local groups, `outside` rows

test('columns sit at fixed x and blocks take their column size', () => {
  const l = layoutTree(model(3, 2), { open: new Set(), width: 1248, narrow: false });
  const at = (id) => l.blocks.find((b) => b.id === id);
  assert.deepEqual([at('client:codex').x, at('gateway:kitden').x], [0, 150 + GAP]);
  assert.deepEqual([at('held:kitden:github').w, at('held:kitden:github').h], [170, 54]);
  assert.ok(l.blocks.every((b) => b.w >= 132 && b.w <= 220 && (b.h <= 54 || b.id === 'gateway:kitden')));
});
test('any tree lays out by its own columns, wide and narrow', () => {
  // two columns, not the Gateway's: sources 180×54 and items 200×34
  const m = { columns: [{ id: 'a', w: 180, h: 54 }, { id: 'b', w: 200, h: 34 }], blocks: [{ id: 'p', column: 'a' }, { id: 'i1', column: 'b', parent: 'p' }, { id: 'i2', column: 'b', parent: 'p' }], links: [{ from: 'p', to: 'i1', kind: 'on' }] };
  const wide = layoutTree(m, { open: new Set(['p']), width: 900, narrow: false });
  assert.equal(wide.blocks.find((b) => b.id === 'i1').x, 180 + GAP);
  const narrow = layoutTree(m, { open: new Set(['p']), width: 600, narrow: true });
  const [p, i1] = ['p', 'i1'].map((id) => narrow.blocks.find((b) => b.id === id));
  assert.ok(i1.y > p.y && i1.x >= p.x && i1.x + i1.w <= p.x + p.w);
});
test('a folded server shows its count; opening it shows its tools and links', () => { /* tools absent, then 4 tool blocks in the tools column */ });
test('the link is the state: an off tool has no link', () => { /* push_files off → no 'held:kitden:github>tool:github/push_files' link */ });
test('one block per column is open', () => {
  const m = model(3, 0);
  const open = toggleOpen(m, toggleOpen(m, new Set(), 'held:kitden:github'), 'held:kitden:linear');
  assert.deepEqual([...open], ['held:kitden:linear']);
});
test('a group with more than six servers shows five and N more', () => {
  const l = layoutTree(model(0, 9), { open: new Set(), width: 1248, narrow: false });
  assert.equal(l.blocks.filter((b) => b.id.startsWith('outside:')).length, 5);
  assert.ok(l.blocks.some((b) => b.id === 'more:group:outside'));
});
test('selecting a tool lights the path from every client that reaches it', () => {
  const lit = litPath(model(3, 0, { open: 'github' }), 'tool:github/read_repo');
  for (const id of ['client:claude_code', 'client:codex', 'gateway:kitden', 'held:kitden:github', 'client:claude_code>gateway:kitden', 'client:codex>gateway:kitden']) assert.ok(lit.has(id), id);
  assert.ok(!lit.has('client:cursor'));
  assert.ok(litPath(model(0, 2), 'outside:move:docs').has('client:claude_code>outside:move:docs'));  // direct
  assert.ok(litPath(FAINT_MODEL, 'item:x').has('client:cursor>item:x'));  // faint
});
test('a client lights what it reaches', () => {
  const lit = litFrom(model(3, 1, { open: 'github' }), 'client:codex');
  for (const id of ['gateway:kitden', 'held:kitden:github', 'tool:github/read_repo', 'client:codex>gateway:kitden']) assert.ok(lit.has(id), id);
  assert.ok(!lit.has('tool:github/push_files'));  // off: no link
});
test('find lights matches and opens the folded parent', () => {
  assert.deepEqual(findIn(model(3, 0, { tools: true }), ' PUSH '), { matches: new Set(['tool:github/push_files']), open: new Set(['held:kitden:github', 'group:kitden:remote']) });
});
test('narrow: tools unfold down inside the server; the gateway is a small tile', () => {
  assert.equal(isNarrow(1023, false), true); assert.equal(isNarrow(1279, true), true); assert.equal(isNarrow(1280, true), false);
  const l = layoutTree(model(3, 0, { open: 'github' }), { open: new Set(['held:kitden:github']), width: 900, narrow: true });
  const server = l.blocks.find((b) => b.id === 'held:kitden:github');
  const tool = l.blocks.find((b) => b.id === 'tool:github/read_repo');
  assert.ok(tool.x >= server.x && tool.y > server.y && tool.x + tool.w <= server.x + server.w);
  assert.deepEqual([l.blocks.find((b) => b.id === 'gateway:kitden').w, l.blocks.find((b) => b.id === 'gateway:kitden').h], [56, 56]);
});
test('unfold: links first, children 15 ms apart, nothing past 300 ms; reduced motion shows the end at once', () => {
  const d = unfoldDelays(12);
  assert.equal(d[1] - d[0], 15); assert.equal(d[11], d[5]); assert.ok(d.every((t) => t + 60 <= 300));
  assert.ok(unfoldDelays(12, true).every((t) => t === 0));
});
test('the layout of 20 servers and of the large sample stays under 16 ms', () => {
  for (const m of [model(2, 18, { open: 'files' }), model(12, 157, { open: 'held-0', long: true })]) {
    const times = Array.from({ length: 20 }, () => { const t = performance.now(); layoutTree(m, { open: new Set(['held:kitden:held-0', 'held:kitden:files']), width: 1248, narrow: false }); return performance.now() - t; }).sort((a, b) => a - b);
    assert.ok(times[10] < 16, `median ${times[10]} ms`);
  }
});
test('a long name is cut and keeps its whole name in its label', () => {
  const name = 'a-very-long-server-name-from-the-large-sample-0001';
  assert.equal(cutName(name).length, 24); assert.ok(cutName(name).endsWith('…')); assert.equal(cutName('files'), 'files');
});
```

```js
// store.test.mjs
test('the view choice stays in the address, and List opens first past 15 servers', () => {
  assert.equal(parseHash('#gateway?view=list').mode, 'list');
  assert.equal(parseHash('#gateway?view=nope').mode, '');
  assert.equal(hashFor({ ...state, view: 'gateway', mode: 'map', project: '', q: '', selected: null }), '#gateway?view=map');
  assert.equal(viewMode({ mode: '' }, 15), 'map'); assert.equal(viewMode({ mode: '' }, 16), 'list'); assert.equal(viewMode({ mode: 'map' }, 157), 'map');
  assert.deepEqual(toolSel('github/push/files'), { server: 'github', tool: 'push/files' });
  assert.deepEqual(parseSel('tool:github/push_files'), { kind: 'tool', name: 'github/push_files' });
  assert.deepEqual(parseSel('group:outside'), { kind: 'group', name: 'outside' });
  assert.deepEqual(parseSel('client:codex'), { kind: 'client', name: 'codex' });
});
test('Back switches Map and List, and a mode passed to go wins over the clear', () => {
  /* state on #gateway?view=map; followHash('#gateway?view=list') → { same: false } and state.mode 'list'; go('overview') → mode ''; go('gateway', { mode: 'list' }) from Overview → mode 'list' */
});
// gateway.test.mjs
test('the probe tree joins linked clients to the gateway and each outside row to its clients', () => { /* gatewayTree on a medium-shaped view: links client:codex>gateway:kitden only when linked; outside:local:docs has a direct link from client:codex */ });
```

```python
# test_measure_start.py
def test_the_probe_sample_has_twenty_servers(tmp_path):
    home = measure_start.build_probe(tmp_path)
    with demo_page_on(home) as page:  # create_app(demo_build(home), ..., demo=True) as Part 1's demo_page does
        view = page.get("/api/gateway-view").json()
    held = len(view["gateways"][0]["servers"])
    outside = sum(len(rows) for rows in view["groups"].values())
    assert held + outside == measure_start.PROBE_SERVERS
```

```python
# test_page_words.py
def test_gateway_wires_do_not_fake_traffic():
    css = (STATIC / "style.css").read_text()
    assert not any(("map" in line or ".routes" in line) and "infinite" in line for line in css.splitlines())
    for name in ("gateway.js", "map.js"):
        assert "flow" not in script(name), name


def test_the_map_marks_when_it_is_drawn():
    assert '"kitden:map-drawn"' in script("map.js") and '"kitden:gateway-drawn"' in script("gateway.js")
```

  In `test_library_replaces_load_map_and_discover` the `map.js` half goes; `assert not (STATIC / "js" / "discover.js").exists()` stays.

- [ ] **Step 2: Run them to see them fail:** `node --test tests/frontend/map.test.mjs tests/frontend/store.test.mjs tests/frontend/gateway.test.mjs`; `uv run pytest tests/unit/test_measure_start.py tests/unit/test_page_words.py -q`.
- [ ] **Step 3: Implement** the interfaces above. On the Gateway page, `state.mode === "map"` draws the map in place of today's cards (the probe only; Task 6 adds the switch); clicking a held block toggles it open and reads its tools from `/api/gateway/tools`. Today's page and the map both mark `kitden:gateway-drawn` the first time they draw with data, and `kitden:gateway-data` once `/api/gateway-view` and `/api/setup-server` have both answered. CSS: blocks on `--panel` with a `--wire` border, radius 8 (tool 7), the gateway on `--panel-raised` with a `--route` border; links `--wire-strong` 1.3 px; `.link.direct` `--lamp-warn` 1.2 px at 0.55 opacity; `.link.draw` uses the existing `wire-draw` keyframes; the reduced-motion rule at the end of `style.css` covers them.
  Builder call: the hash's `view` lives in `state.mode`, because `state.view` already names the place.
  Builder call: the probe sample is `build_probe` in `scripts/measure-start.py`, not a fourth `SIZES` entry.
  Builder call: a group over `GROUP_MAX` folds in `layoutTree` for every map page, so Part 5 gets the same rule.
- [ ] **Step 4: Run** the tests of Step 1 and the four checks → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/map.js src/kitden/web/static/js/dom.js src/kitden/web/static/js/store.js src/kitden/web/static/js/gateway.js src/kitden/web/static/style.css scripts/measure-start.py tests/frontend/map.test.mjs tests/frontend/store.test.mjs tests/frontend/gateway.test.mjs tests/unit/test_measure_start.py tests/unit/test_page_words.py
git commit -m "Map: the core layout and a probe on the Gateway"
```

- [ ] **Step 6: Run the probe (controller).** `uv run python scripts/measure-start.py` (note `gateway view`), then `uv run python scripts/measure-start.py --probe`. In a browser at the printed link, load `#gateway` five times and `#gateway?view=map` five times and read `performance.getEntriesByName(...)` for `kitden:gateway-drawn` (first usable view, from navigation start), `kitden:gateway-data` (complete data) and `kitden:map-draw`. Run the same on `main` for today's page (`kitden:gateway-drawn` only; add the mark there in a scratch copy, never committed). Note the medians and the machine.
- [ ] **Step 7: The pass rule.** The probe passes when the median `kitden:map-draw` is under 50 ms on the probe sample and `the layout of 20 servers and of the large sample stays under 16 ms` passes. **If either fails, the controller stops this part here and reports the numbers to the owner; no later task starts.**

---

### Task 2: Words — "On", "This project" and "Only this project" (S.1)

**Files:**
- Modify: `src/kitden/views/words.py` (`STATE_WORDS["on"]`, `ORIGIN_WORDS`), `src/kitden/views/load_map.py` (`_cell` `where`, the docstrings that say "available"), `src/kitden/views/library.py` (`_skill_rows` `where`), `src/kitden/web/static/js/parts.js` (`STATE_WORDS.on`, new `ORIGIN_WORDS`, `socket` draws `where` as a tag), `src/kitden/web/static/js/details.js` (`loadsLede`), `src/kitden/web/static/js/overview.js` (`loadsLine`), `src/kitden/web/static/style.css` (`.socket .where`), `docs/design.md` (Library rows "Cell state", "Scope word", "Instruction file Details"), `README.md` (the project view and cell paragraphs)
- Test: `tests/unit/test_page_words.py`, `tests/unit/test_docs_words.py`, `tests/unit/test_load_map.py`, `tests/unit/test_library.py`, `tests/unit/test_project_add.py`, `tests/unit/test_after.py`, `tests/unit/test_add_server.py`, `tests/unit/test_api_skill_install.py`, `tests/unit/test_api_plugin_install.py`, `tests/unit/test_gateway_remove.py`, `tests/unit/test_align.py`, `tests/frontend/parts.test.mjs`, `tests/frontend/library.test.mjs`, `tests/frontend/panel.test.mjs`

**Interfaces:**
- Produces: Python `STATE_WORDS["on"] = "On"` (After chips follow through `AFTER_WORDS`); `ORIGIN_WORDS: dict[str, str] = {"override": "This project", "project": "Only this project"}`; a cell's `where` in a project is `ORIGIN_WORDS.get(origin)` (None for a cell that follows the shared setup), and None with All projects. JS twin in `parts.js`: `export const ORIGIN_WORDS = { override: "This project", project: "Only this project" };`, `STATE_WORDS.on: "On"`. `socket({ where })` draws `where` as `span.tag` (accent, no "· " before it).
- Words: `loadsLede` → `` `On in ${joinWords(on)}.` `` and, with none, `"Not on here."`; Overview's empty client line → `"Nothing on here."`.

- [ ] **Step 1: Rename through the tables, not by find-and-replace.** Change the two tables and the code that reads them, then update the pins in the listed tests by meaning: a state word "Available" → "On"; a cell `where` of "project override" → "This project"; a cell `where` of "this project" → "Only this project"; a cell `where` of "all projects" → None (the cell carries nothing). Sentences that say "this project" in lowercase (`review.js` `PLACE_WORDS`, `changes.js` `SCOPE_WORDS`, Affects "In this project.", the Why lines) keep their words; so does `scopeWords` in `details.js` ("This project" for a definition in the picked project: its state comes from the project's own settings, which is the new meaning). `tests/unit/test_docs_words.py`'s historical pin on `walkthrough-script-1.md` stays.
- [ ] **Step 2: Write the new tests**

```python
# test_page_words.py
def test_python_and_page_origin_words_agree():
    from kitden.views.words import ORIGIN_WORDS
    parts = script("parts.js")
    assert ORIGIN_WORDS == {"override": "This project", "project": "Only this project"}
    for origin, word in ORIGIN_WORDS.items():
        assert f'{origin}: "{word}"' in parts, origin
    assert "project override" not in parts + script("library.js") + panel()


def test_after_words_come_from_the_one_table():  # was "Available"
    from kitden.views import after
    assert AFTER_WORDS["plugin.enable"] == ("on", "On")
    assert after.CURSOR_IMPORT["word"] == "On"
```

```python
# test_load_map.py
def test_a_cell_says_this_project_only_where_the_project_decides(medium_home):
    rows = load_map(build_inventory(medium_home), str(medium_home / "work/atlas"))
    docs = rows_by(rows, "mcp_server", "docs").cells["claude_code"]
    assert (docs.origin, docs.where) == ("override", "This project")
    shared = rows_by(rows, "mcp_server", "github").cells["claude_code"]
    assert (shared.origin, shared.where) == (None, None)
```

```js
// library.test.mjs (edited where it is)
assert.equal(cellHint({ where: 'This project', route: "through Codex's folder", reason: 'Could not read Codex.' }), "This project. Through Codex's folder. Could not read Codex.");
// panel.test.mjs: 'the Details lede says where it loads, and where it may' expects 'On in Claude Code and Codex.' and 'Not on here.'
```

- [ ] **Step 3: Run them to see them fail**, then **implement** the table change.
- [ ] **Step 4: Update `docs/design.md`:** "Cell state": "like Available" → "like On"; Instructions cells say "On". "Scope word" row becomes "Tag": in a project, a cell whose state comes from the project's own settings carries the short accent tag "This project"; an item only that project has carries "Only this project" (Part 5 moves such items under a group of that name); cells that follow the shared setup carry nothing, and the scope bar says so; the hover text still names the tag, the route and the reason. "Instruction file Details": the badge says "On". **README:** the project view paragraph says a cell in a project carries "This project" when the project's own settings decide it, and "Only this project" for an item only that project has; a cell says "On" when the client has the item. Update `test_readme_says_what_a_project_view_adds` to `'"This project" when the project\'s own settings decide it'` and `'"Only this project"'`.
  Builder call: until Part 5 groups them, a Library cell of an item only the project has shows "Only this project" as its tag.
- [ ] **Step 5: Run** the four checks and `uv run pytest tests/unit/test_mcp_server.py -q` → PASS.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/views/words.py src/kitden/views/load_map.py src/kitden/views/library.py src/kitden/web/static/js/parts.js src/kitden/web/static/js/details.js src/kitden/web/static/js/overview.js src/kitden/web/static/style.css docs/design.md README.md tests/unit/test_page_words.py tests/unit/test_docs_words.py tests/unit/test_load_map.py tests/unit/test_library.py tests/unit/test_project_add.py tests/unit/test_after.py tests/unit/test_add_server.py tests/unit/test_api_skill_install.py tests/unit/test_api_plugin_install.py tests/unit/test_gateway_remove.py tests/unit/test_align.py tests/frontend/parts.test.mjs tests/frontend/library.test.mjs tests/frontend/panel.test.mjs
git commit -m "Words: On, This project and Only this project"
```

---

### Task 3: Tokens and Details beside the page (S.2, S.3)

**Files:**
- Modify: `src/kitden/web/static/style.css` (tokens; `.shell.docked`, `#drawer.docked`, stacked footer, `.facts`), `src/kitden/web/static/js/panel.js` (`openPanel`, `closePanel`, `restoreFocus`, `trapFocus`, `initPanel`), `src/kitden/web/static/js/details.js` (`factsBlock`, `detailsCard`), `docs/design.md` (Color roles; Components: Details beside the page; Motion "A drawer has one motion")
- Test: `tests/unit/test_contrast.py`, `tests/frontend/panel.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces in `style.css`: light `--dim: #eef0f3; --preview-fill: #a4422612; --preview-line: #a4422680;` and dark (both dark blocks) `--dim: #1b1f26; --preview-fill: #f09a7c10; --preview-line: #f09a7c80;`. `kd-faint` gets no token: icons, grips and hollow marks use `--lamp-off`; text a frame paints `kd-faint` uses `--ink-3`; text a frame paints `kd-ok` uses `--diff-add`.
- Produces in `panel.js`: `DOCK_MIN = 1024`; `DOCKS = ["gateway", "library", "changes"]`; `docksAt(view, width) -> boolean` (`DOCKS.includes(view) && width >= DOCK_MIN`); `openPanel(content, { instant = false, dock = DOCKS.includes(state.view) })`. Docked: `#drawer.docked` and `.shell.docked`, no scrim, `role="region"` with `aria-label="Details"` and no `aria-modal`, no focus trap; the page stays usable. Not docked: today's drawer (dialog, `aria-modal`, scrim, trap). A `matchMedia("(min-width: 1024px)")` change while open switches between the two. Escape closes both; `restoreFocus` finds the opener by its `focusKey` (`data-focus` or a row key) after a redraw.
- Produces in `details.js`: `factsBlock(rows: {label: string, value: string | Node, accent?: boolean}[]) -> HTMLElement` (`dl.facts`, label column 86 px); `detailsCard({ kind, title, id = null, facts = [], why = null, actions = [], more = [], after = null, technical = null }) -> Node[]` for `openPanel`: header (kind and Close; the title, the id quiet under it), the facts, one explanation paragraph, `footer.stack` with the actions in order, then `more` behind one "More" button, then `after` (a quiet node under the actions), and `technical` (from `technical(rows)`) folded last as "Technical details". An action is `{ label, run?, body?, primary? }`: `run()` is called on press, else `review(body)`; `primary` draws the action fill (at most one). Card builders return this plain object, so node tests read its fields.

- [ ] **Step 1: Write the failing tests**

```python
# test_contrast.py
def test_text_on_the_dim_fill_is_readable_in_both_themes():
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        for ink in ("--ink-2", "--ink-3"):
            assert contrast(theme[ink], theme["--dim"]) >= 4.5, ink


def test_the_preview_tokens_are_the_frames_values():
    assert (LIGHT["--preview-fill"], LIGHT["--preview-line"]) == ("#a4422612", "#a4422680")
    assert (DARK["--preview-fill"], DARK["--preview-line"]) == ("#f09a7c10", "#f09a7c80")
```

```js
// panel.test.mjs
test('Details dock beside the page from 1024 px on Gateway, Library and Changes', () => {
  assert.equal(docksAt('gateway', 1024), true); assert.equal(docksAt('library', 1023), false);
  assert.equal(docksAt('changes', 1440), true); assert.equal(docksAt('overview', 1440), false);
  assert.equal(DOCK_MIN, 1024);
});
```

```python
# test_page_words.py
def test_details_sit_beside_the_page_without_a_scrim():
    shell = script("panel.js")
    assert "export const DOCK_MIN = 1024;" in shell and 'removeAttribute("aria-modal")' in shell
    assert "export function factsBlock(" in script("details.js") and "export function detailsCard(" in script("details.js")
    assert "#drawer.docked" in CSS and ".shell.docked" in CSS and ".facts" in CSS
```

  Edit `test_focus_returns_to_the_control_and_the_review_reaches_its_summary` only if `trapFocus` moves; its assertions stay.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** The docked column is 320 px, fixed at the right under the top bar, full height; `.shell.docked #content` gets `padding-right: 336px`; the column keeps the drawer's one motion (it slides in; keyboard opens are instant). In the column the footer stacks its buttons full width. Reviews open in the same column (they call `openPanel`).
  Builder call: Library Details keep their content in this part and only dock; Part 5 moves them to `detailsCard`.
- [ ] **Step 4: Update `docs/design.md`:** Color roles: three rows for `--dim` (outside blocks, off tools), `--preview-fill` and `--preview-line` (a preview block), and the line "The frames' `kd-faint` is for icons, grips and hollow marks only (`--lamp-off`); text uses `--ink-3`." Components: "Details beside the page": on Gateway, Library and Changes at 1024 px and wider, a 320 px column with no scrim; Escape closes it and focus goes back to what opened it; narrower, and on Overview, the drawer; the order kind and Close, title and id, Facts, one sentence, stacked actions, "Technical details" folded.
- [ ] **Step 5: Run** the four checks → PASS. Look at it in `uv run kitden demo --size medium` at 1440 and 900 px, both themes: the Library's Details docks and drawers; Tab leaves the docked column; Escape returns focus to the row.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/style.css src/kitden/web/static/js/panel.js src/kitden/web/static/js/details.js docs/design.md tests/unit/test_contrast.py tests/frontend/panel.test.mjs tests/unit/test_page_words.py
git commit -m "Details: a column beside the page from 1024 px, and the map tokens"
```

---

### Task 4: Gateway data (4.2)

**Files:**
- Create: `src/kitden/clients/entries.py`, `tests/unit/test_gateway_access.py`
- Modify: `src/kitden/model.py` (`Item.stays_direct`), `src/kitden/clients/base.py` (`mcp_item`), `src/kitden/changes/actions.py` (`_movable` uses `entry_refusal`), `src/kitden/local_gateway/views.py` (`_states`, `held_servers`, `tools_view`, `own_rules`), `src/kitden/views/gateway_view.py` (`columns`, `stays`, `override`), `src/kitden/web/app.py` (`_kitden`, `_gateway_view`, `projects`)
- Test: `tests/unit/test_gateway_access.py`, `tests/unit/test_local_gateway_views.py`, `tests/unit/test_gateway_view.py`, `tests/unit/test_api_views.py`, `tests/unit/test_local_gateway_move.py` (refusal words unchanged), `tests/unit/test_mcp_server.py`

**Interfaces:**
- Produces:
  - `_states(settings, server, tool, chain) -> dict`: today's `state`, `differs`, `follows` plus `origin: "project" | "parent" | "global" | "default" | "strict"` and `origin_from: str | None` (old Part 5 Task 1): the picked project has its own state → `"project"`; else `deciding_project(settings, chain[1:], …)` → `"parent"` with its folder name; else a global state → `"global"`; else a tool of a strict server → `"strict"`; else `"default"`.
  - `held_servers(settings, chain, tools=None, chains: dict[str, list[str]] | None = None) -> list[dict]`: each row gains `origin`, `origin_from`, `tool_list: [{name, title, state, effective, hint, origin, origin_from}]` (cache order; `state` is the tool's own rule state, `effective` that state with the server's switch applied, and a tool whose `effective` is off because its server is off also has `"why": "server_off"`), `on_count: int` (tools whose `effective` is on), `on_in: int` (with an empty `chain` and the server off: how many known projects of `chains` turn it on; else 0) and `projects: int` (known projects whose own rules set the server or one of its tools). `chains` maps every known project to its chain.
  - `tools_view(...)`: the server and each tool gain `origin`, `origin_from`; each tool gains `title`, `effective: "on" | "off"` and, when the server is off, `"why": "server_off"`, with the same meanings as in `tool_list`: one meaning of a tool's fields everywhere (owner ruling 2026-10-24). `state` stays the rule's own state, which the Library's tool switches in `tools.js` read until Part 5.
  - `own_rules(settings: dict, chain: list[str]) -> int` in `local_gateway/views.py`: the states the project `chain[0]` sets (the server switch and each tool, over all servers) whose `_states(...)["differs"]` is true. A rule equal to the one it would otherwise follow is not counted, though it still gets "Use the shared rule…".
  - `/api/projects` items gain `own_rules` (from the gateway settings; Part 5 adds the Library's). `/api/gateway-view` gains `own_rules` for the picked project (0 for All projects).
  - Rows of `groups.move`, `groups.local` and `groups.plugin` gain `columns: list[str]` (client columns in `COLUMNS` order, the Desktop Code tab counted as `claude_code`) `override: bool` (in a project view, a loaded entry of the row is the project's own definition that replaces a shared one, from `effective_view(...).shadowed`) and `stays: str | None`, the first reason a move would refuse that Kitden knows without the network: a plugin row → `"{name} comes with a plugin; it stays with the plugin."`; an entry in a project's own file (`Scope.PROJECT`) → `_movable`'s `"{name} is in the project's own files; it stays there."`; an item's `stays_direct`; an item kept from the last good read → `KEPT_UNREAD.format(<file name>)`.
  - `src/kitden/clients/entries.py`: `gateway_entry(entry)` and `reads_elsewhere(entry, server)` (moved from `actions.py` with their bodies), and `entry_refusal(name: str, entry: dict) -> str | None`: the entry checks of `_movable` with its exact sentences (values from the shell or `${…}`, `cwd`, SSE or WebSocket, an entry that cannot be read as a server). `_movable` calls it; `mcp_item` sets `Item.stays_direct: str | None = None` from it.

- [ ] **Step 1: Write the failing tests** (`tests/unit/test_gateway_access.py`; its own `home` fixture and helpers as `test_local_gateway_views.py` builds them)

```python
SITE, WEB = "/w/site", "/w/site/web"
ECHO_TOOLS = {"echo": [tool(n) for n in ("echo", "slow", "clash", "where")]}

def settings_with(global_rules, projects):
    return {"servers": {"echo": {"command": "echo"}}, "rules": {"global": global_rules, "projects": projects}}

def test_each_tool_says_where_its_state_comes_from():
    settings = settings_with({"echo": {"tools": {"slow": "off"}}},
                             {SITE: {"echo": {"tools": {"clash": "off"}}}, WEB: {"echo": {"tools": {"where": "on"}}}})
    web = tools_view(settings, ECHO_TOOLS, "echo", [WEB, SITE])
    assert [(t["origin"], t["origin_from"]) for t in web["tools"]] == [
        ("default", None), ("global", None), ("parent", "site"), ("project", None)]

def test_a_tool_of_a_server_that_is_off_is_off():
    settings = settings_with({}, {SITE: {"echo": {"server": "off"}}})
    row = held_servers(settings, [WEB, SITE], ECHO_TOOLS)[0]
    assert (row["state"], row["origin"], row["origin_from"], row["on_count"]) == ("off", "parent", "site", 0)
    assert {(t["effective"], t.get("why")) for t in row["tool_list"]} == {("off", "server_off")}
    assert [t["state"] for t in row["tool_list"]] == ["on", "on", "on", "on"]  # their own rules are untouched
    view = tools_view(settings, ECHO_TOOLS, "echo", [WEB, SITE])
    assert {(t["state"], t["effective"], t["why"]) for t in view["tools"]} == {("on", "off", "server_off")}

def test_all_projects_counts_the_projects_that_turn_a_server_on():
    settings = settings_with({"echo": {"server": "off"}}, {SITE: {"echo": {"server": "on"}}})
    row = held_servers(settings, [], ECHO_TOOLS, {SITE: [SITE], WEB: [WEB, SITE], "/w/other": []})[0]
    assert (row["state"], row["on_in"], row["projects"]) == ("off", 2, 1)

def test_the_medium_sample_counts_tools_and_own_rules(tmp_path):
    home = build_demo_home(tmp_path, "medium")
    settings, tools = load_settings(home), load_tools(home)
    files = next(r for r in held_servers(settings, [], tools) if r["name"] == "files")
    assert files["on_count"] == len(files["tool_list"]) - 1  # delete_file is off for all projects
    tracker = next(r for r in held_servers(settings, [], tools) if r["name"] == "tracker")
    assert next(t for t in tracker["tool_list"] if t["name"] == "export_report")["origin"] == "strict"
    atlas, web = str(home / "work/atlas"), str(home / "work/atlas/web")
    assert (own_rules(settings, [atlas]), own_rules(settings, [web, atlas]), own_rules(settings, [str(home / "work/website")])) == (1, 1, 0)

def test_a_rule_equal_to_the_shared_one_is_not_counted():
    settings = settings_with({"echo": {"tools": {"slow": "off"}}}, {WEB: {"echo": {"tools": {"slow": "off"}}}})
    assert own_rules(settings, [WEB]) == 0
    assert tools_view(settings, ECHO_TOOLS, "echo", [WEB])["tools"][1]["origin"] == "project"

def test_outside_rows_name_their_columns_and_why_they_stay(tmp_path):
    with demo_page(tmp_path) as page:  # medium
        groups = page.get("/api/gateway-view").json()["groups"]
    assert {r["name"]: r["columns"] for r in groups["local"]}["docs"] == ["codex"]
    assert all(r["stays"] is None for r in groups["move"] + groups["local"])
    # an entry that reads a header from the shell stays
    ...  # add {"headers": {"Authorization": "Bearer ${TOKEN}"}} to a Claude Code entry, read again
    assert row["stays"] == "github reads values from your shell; it stays direct for now."

def test_a_row_kept_from_the_last_good_read_stays(tmp_path):
    ...  # demo_page(medium); break ~/.cursor/mcp.json; rescan; the Cursor `files` row
    assert row["stays"] == "Kitden can't change this until it reads mcp.json again."

def test_the_page_gets_own_rules_per_project_and_the_mcp_server_does_not(tmp_path):
    with demo_page(tmp_path) as page:
        projects = {Path(p["path"]).name: p["own_rules"] for p in page.get("/api/projects").json()}
    assert (projects["atlas"], projects["web"], projects["website"]) == (1, 1, 0)

def test_a_project_definition_that_replaces_a_shared_one_is_an_override(tmp_path):
    with demo_page(tmp_path) as page:
        atlas = next(p["id"] for p in page.get("/api/projects").json() if p["path"].endswith("/work/atlas"))
        groups = page.get(f"/api/gateway-view?project={atlas}").json()["groups"]
        everywhere = page.get("/api/gateway-view").json()["groups"]
    assert next(r for r in groups["move"] if r["name"] == "docs")["override"] is True
    assert not any(r["override"] for g in everywhere.values() for r in g)
```

  In `test_mcp_server.py`, assert the projects answer has no `own_rules`. Update the exact dicts in `test_local_gateway_views.py` (`test_tools_api_marks_project_differences` and the held-server cards) with the new keys.
- [ ] **Step 2: Run them to see them fail:** `uv run pytest tests/unit/test_gateway_access.py tests/unit/test_local_gateway_views.py tests/unit/test_gateway_view.py -q`.
- [ ] **Step 3: Implement.** `app.py`: `_kitden(path)` passes `chains = {p.path: _chain(p.path) for p in state.inventory.projects}`; `_gateway_view` adds `own_rules`; `projects` answers `[{**p, "own_rules": own_rules(settings, _chain(p["path"]))} …]`. `entries.py` imports nothing from `kitden.changes.actions` (no import cycle: `uv run python -c "import kitden.clients.base, kitden.changes.actions"`).
  Builder call: a move's offline refusal is read with the entry, at scan time (`Item.stays_direct`): `_movable` per row re-reads each file and took 256 ms on the large sample (157 rows, measured 2026-10-24).
  Builder call: Codex's project layers (`_codex_layers`) are not part of `stays`; the preview still refuses them.
- [ ] **Step 4: Run** Step 2's tests, `tests/unit/test_mcp_server.py`, `tests/security` and the four checks → PASS. Run `uv run python scripts/measure-start.py`; `gateway view` stays within 5 ms of Task 1's number.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/clients/entries.py src/kitden/model.py src/kitden/clients/base.py src/kitden/changes/actions.py src/kitden/local_gateway/views.py src/kitden/views/gateway_view.py src/kitden/web/app.py tests/unit/test_gateway_access.py tests/unit/test_local_gateway_views.py tests/unit/test_gateway_view.py tests/unit/test_api_views.py tests/unit/test_mcp_server.py
git commit -m "Gateway data: tool lists, origins, on counts and why a row stays direct"
```

---

### Task 5: The project menu and the scope bar (S.7)

**Files:**
- Modify: `src/kitden/web/static/index.html` (the picker becomes a button and a menu), `src/kitden/web/static/js/app.js` (`renderShell`, `refreshForProject`), `src/kitden/web/static/js/store.js` (`switchProject`, `setSwitcher`, `goTo`'s `project`), `src/kitden/web/static/js/parts.js` (`menuItems`, `projectMenu`, `scopeText`, `scopeBar`), `src/kitden/web/static/js/gateway.js` (the scope bar under the head), `src/kitden/web/static/style.css`, `docs/design.md` (the picker sentence in Components; a "Scope bar" sentence)
- Test: `tests/frontend/parts.test.mjs`, `tests/frontend/store.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `/api/projects` `own_rules`, `/api/gateway-view` `own_rules` (Task 4); `GONE_PROJECT`, `folderName`.
- Produces in `parts.js` (all exported):
  - `menuItems(projects, picked, text = "") -> [{ id, name, sub, count, picked }]`: first `{ id: "", name: "All projects", sub: "What applies in every project" }` (always shown); then each project by folder name, case-insensitive, filtered by `text` on the name; `count` is `plural(own_rules, "own rule", "own rules")` or null; `sub` is "Folder missing" for a project whose folder is gone; a picked project no longer on the list stays as `{ id: picked, name: "No longer on the list" }`. No paths.
  - `projectMenu(projects, picked, onPick) -> HTMLElement`: the button (`#where`, `aria-label="Project"`, text the picked name, `aria-haspopup="listbox"`) and a menu with a "Find a project…" input and `role="listbox"` options; Down, Up, Home, End move; Enter picks; Escape closes and gives focus back to the button; typing filters.
  - `scopeText(folder, count) -> string` (`library.js` keeps its own `scopeLine`): no folder → "Shared setup · project overrides stay separate"; `count` > 0 → `` `Project ${folder} · ${plural(count, "rule differs", "rules differ")} from the shared setup` ``; 0 → `` `Project ${folder} · follows the shared setup` ``. `scopeBar(folder, count)` draws it (accent with a project).
- Produces in `store.js`: `switchProject(id: string) -> Promise<void>`: sets `state.project`, clears the selection, writes the address as a new entry, then runs the switcher registered with `setSwitcher(fn)` (as `setRenderer`); `goTo(view, selected, { project, mode } = {})`: with a `project` other than the picked one it awaits `switchProject(project)` first. `app.js` registers `refreshForProject()`, today's `change` handler body after the state change (`closeForProject()`, the Library morph, the waiting page, the refresh); the menu's `onPick` calls `switchProject(id)`.

- [ ] **Step 1: Write the failing tests**

```js
test('the project menu lists All projects first, then projects by name with their own rules', () => {
  const projects = [{ id: 'w', path: '/u/work/website', exists: true, own_rules: 3 }, { id: 'a', path: '/u/work/api', exists: false, own_rules: 0 }, { id: 'm', path: '/u/mcp-gateway', exists: true, own_rules: 1 }];
  assert.deepEqual(menuItems(projects, 'm').map((i) => [i.name, i.count, i.sub, i.picked]), [
    ['All projects', null, 'What applies in every project', false], ['api', null, 'Folder missing', false],
    ['mcp-gateway', '1 own rule', null, true], ['website', '3 own rules', null, false]]);
  assert.deepEqual(menuItems(projects, '', 'WEB').map((i) => i.name), ['All projects', 'website']);
  assert.deepEqual(menuItems([], 'gone').map((i) => i.name), ['All projects', 'No longer on the list']);
});
test('the scope bar says what the page shows', () => {
  assert.equal(scopeText('', 0), 'Shared setup · project overrides stay separate');
  assert.equal(scopeText('mcp-gateway', 1), 'Project mcp-gateway · 1 rule differs from the shared setup');
  assert.equal(scopeText('api', 0), 'Project api · follows the shared setup');
});
// store.test.mjs
test('switching a project writes a new address entry and runs the switcher once', async () => {
  /* setSwitcher(spy); await switchProject('a') → state.project 'a', selected null, one pushState, spy called once; goTo('gateway', sel, { project: 'b' }) switches first, then keeps sel */
});
```

```python
def test_project_picker_says_project_not_where():  # replaces the select pins
    assert 'aria-label="Project"' in INDEX and "Where:" not in INDEX and "<select" not in INDEX
    app, parts = script("app.js"), script("parts.js")
    assert "projectMenu(" in app and "No project" not in app and "Global" not in app
    for words in ('"Find a project…"', '"What applies in every project"', '"own rule", "own rules"', '"No longer on the list"'):
        assert words in parts, words
    assert 'export const ALL_PROJECTS = "All projects";' in parts
```

  `test_another_project_closes_the_panel` splits on `function refreshForProject(` instead of the `change` listener (`closeForProject();` there and in `fromAddress`). `test_a_project_no_longer_on_the_list_is_said_not_swapped`: `"No longer on the list"` is now in `parts.js` (`menuItems`); `projectGone()` stays in `app.js`. `test_scope_switch_marks_the_project_picker_and_the_lede`: `classList.toggle("project"` stays in `app.js` on the menu's box, `.where-box.project` stays in CSS, and `scopeBar(` is in `gateway.js`.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** The Gateway shows `scopeBar(folderName(projectPath()), model.own_rules)` under its head; `scopeBar` draws `scopeText`.
  Builder call: All projects stays first while filtering, so the way back is always one key away.
  Builder call: with no own rules the bar says "follows the shared setup", not "0 rules differ".
- [ ] **Step 4: Update `docs/design.md`:** the picker is a menu ("Find a project…", "All projects" with "What applies in every project", each project with "N own rules", no paths; keys); the scope bar under a page head says "Shared setup · …" or "Project <name> · N rules differ …".
- [ ] **Step 5: Run** the four checks → PASS. Pick a project by keyboard only in the demo.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/index.html src/kitden/web/static/js/app.js src/kitden/web/static/js/store.js src/kitden/web/static/js/parts.js src/kitden/web/static/js/gateway.js src/kitden/web/static/style.css docs/design.md tests/frontend/parts.test.mjs tests/frontend/store.test.mjs tests/unit/test_page_words.py
git commit -m "Project menu with own rules, and a scope bar on the Gateway"
```

---

### Task 6: The Gateway List, and Details for clients, gateways and outside servers (4.3, 4.4, S.5)

**Files:**
- Create: `src/kitden/web/static/js/gateway-details.js`, `tests/frontend/gateway-details.test.mjs`
- Modify: `src/kitden/web/static/js/gateway.js` (rewrite: head with Map | List, scope bar, List, arrival; `gatewayTree` full; the cards, `routes`, `focusRoutes`, `showDirect`, `GROUPS`, `LOCAL_WORDS`, `visibleRows`, `FOLD_AT`, `serverFor`, `showServer` go; `addForm` and `connectForm` move to `gateway-details.js`; `SETUP_NOTE` stays exported from `gateway.js`, which `overview.js` imports), `src/kitden/web/static/js/dom.js` (`gridKey`), `src/kitden/web/static/js/panel.js` (re-exports unchanged), `src/kitden/web/static/style.css` (`.routes` rules go; `.treegrid`), `docs/design.md` (Gateway section: intro and List rows; Client marks; Motion principle 2 and the "Route focus" row)
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/focus.test.mjs`, `tests/frontend/context.test.mjs`, `tests/frontend/gateway-details.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Tasks 1–5; `kitdenClients`, `moveTargets`, `moveInto`, `heldActions`, `offerLabel`, `techRows`, `technical`, `detailsCard`, `factsBlock`, `versionWords`, `/api/explain`.
- Produces:
  - `gatewayTree(view, { setup, clients, open, held, picked })`, full (the `tools` option goes: tools come from `tool_list`): also each registered gateway as `gateway:<id>` under the Kitden one, linked from each client it connects, with its servers from the live read (`held` map) as `held:<id>:<name>` without tools; tools from `tool_list`; held `meta` `` `${on_count} of ${tools} on` `` (or Remote/Local when tools are unknown), with All projects and `on_in` `` `On in ${plural(on_in, "project", "projects")}` ``; outside `meta` `` `In ${joinWords(columns names)}` ``; `tag`: a tool with `origin === "project"` → "This project"; a held server with `origin === "project"` → "Only this project" when it is on and `differs`, else "This project".
  - `listRows(model, open) -> [{ id, parent, depth, kind, name, usedBy, tools, action, tag, expanded, group }]`: a "Clients" group of client rows ("Connected" / "Not connected"); per gateway its own row, then its "Remote" and "Local" group rows with held rows and, under an open one, its tool rows (a mark filled when `effective` is on, the name, tag "Read", "Write" or "May write"); then "Outside the gateway · calls skip Kitden's rules". `usedBy`: a held server's linked clients while it is on, an outside row's `columns`; `tools`: "N of M on" for held; `action`: `"move"` ("Move in…") on an outside row with `items`, a target and no `stays`, else `"open"` (›).
  - `gridKey(rows, at, key) -> { at, toggle?: string, details?: string } | null` in `dom.js`: Down, Up, Home, End move; Right on a closed row that folds → `toggle`, on an open one → its first child; Left on an open row → `toggle`, else → its parent; Enter on a row that is not a group → `details`; any other key → null.
  - `gateway-details.js`, each a pure card builder plus a `show…` that opens it docked (`detailsCard`):
    - `clientCard(client, { setup, clients, view }) -> card`: kind "Client"; facts Version (`versionWords`), "Kitden entry" ("On", "Off", "Old", "Not set up"), Gateway ("Connected" / "Not connected"); why: "<Client> reaches the Kitden gateway through its kitden entry." / "<Client> has the kitden entry turned off, so it does not reach the gateway." / "<Client> does not use the Kitden gateway yet."; actions "Set up in <client>…" (from `kitdenClients`), `` `Open ${CLIENT_APPS[id]}` `` when the app's `app_url` is known.
    - `gatewayCard(gateway, { view, setup, projects }) -> card`: Kitden: kind "Gateway", title "Kitden gateway", id "On this Mac"; facts Clients (tiles, "N clients"), Servers ("N servers"), Rules (`` `${plural(n, "project has", "projects have")} its own rules` `` or "No project has its own rules"); why "The gateway controls only the servers in it. Direct entries and terminal tools are outside it."; actions `` `Move all ${n}…` `` (every outside row with items and no `stays`), "Add another gateway…" (the add form in the column), and "Kitden could not read which clients use it." or the settings problem as a callout. A registered gateway: kind "Gateway", title `gatewayName`; facts Clients, Servers (the live count or "Could not read what the gateway holds."), and with two of them "Used" / "Not used"; actions `` `Open ${name} ↗` ``, "Use this gateway…", "Connect clients" (`connectForm`); its address under Technical details.
    - `outsideCard(row, group, definitions, { view, clients }) -> card`: kind "MCP server", title the name; facts In (client tiles and names), Kind (Remote, Local, From a plugin), Gateway ("Outside · calls skip Kitden's rules"); why `` `${names} ${verb} it directly, so Kitden's tool rules do not reach it.` ``; actions: "Move into the gateway…" when `row.items`, a target and no `stays` (else the `stays` sentence as a quiet line), "Remove direct entry…" when no gateway can take a remote one, `` `+ Add to ${client}…` `` for each found client Kitden writes that lacks it while no client gets it through a gateway (`mcp.add` with the user-scope definition that has `mcp.remove_direct`), one Remove per definition with `mcp.remove_direct` (labels from `offerLabel`); `technical(techRows(definitions))`. Definitions come from `/api/explain?kind=mcp_server&name=` only; `/api/map` is never read for it.
  - Held and tool rows open today's held panel in this task (`showKitdenServer`, the tool list); Task 7 replaces it.
  - The page head: title "Gateway", lede "Connect your agents. Shape what they can use.", a Map | List switch (`button[aria-pressed]`, `data-focus` `view:map` / `view:list`, it calls `go("gateway", { mode })`), then the scope bar. The body draws `viewMode(state, serverCount)`; Map is Task 1's map until Task 8.
  - `arrivalServer(model) -> Promise<{ held } | { outside } | null>` stays exported and finds the row in the gateway model; it never reads `/api/map`. Arrival: a selected `mcp_server` opens its row's Details (held, or outside by name); `tool` opens its server and the tool row; `client` selects the client row; `group` opens that group and focuses it. Selecting a server, tool or client writes `sel`; a gateway row writes none.

- [ ] **Step 1: Write the failing tests**

```js
// gateway.test.mjs (old tests of serverFor, visibleRows go; offersSwitch, heldServer, kitdenLinks stay)
test('the list has clients, each gateway with Remote and Local, then the outside group', () => {
  const rows = listRows(gatewayTree(MEDIUM_VIEW, { setup: SETUP, clients: CLIENTS, open: new Set(), held: new Map() }), new Set());
  assert.deepEqual(rows.filter((r) => r.group).map((r) => r.name), ['Clients', 'Remote', 'Local', "Outside the gateway · calls skip Kitden's rules"]);
  assert.deepEqual(rows.find((r) => r.id === 'held:kitden:files').tools, '3 of 4 on');
  assert.equal(rows.find((r) => r.id === 'outside:move:github').action, 'move');
});
test('one name in two groups is two rows', () => {
  const ids = listRows(gatewayTree(MEDIUM_VIEW, OPTS), new Set()).map((r) => r.id);
  assert.ok(ids.includes('outside:move:docs') && ids.includes('outside:local:docs'));
});
test('a row that stays gets no Move in…', () => { /* row with stays → action 'open' */ });
// context.test.mjs: the fetch stub records every URL; arrivalServer finds github as `{ outside }` and no URL starts with '/api/map'
test('the large sample opens in List', () => assert.equal(viewMode({ mode: '' }, LARGE_SERVER_COUNT), 'list'));
test('tags say where a rule comes from', () => { /* tool origin project → 'This project'; held origin project, on, differs → 'Only this project' */ });
// focus.test.mjs
test('the list moves by keys', () => {
  const rows = [{ id: 'g', group: true, expanded: true }, { id: 's', parent: 'g', expanded: false }, { id: 't', parent: 's' }];
  assert.deepEqual(gridKey(rows, 1, 'ArrowRight'), { at: 1, toggle: 's' });
  assert.deepEqual(gridKey(rows, 1, 'ArrowLeft'), { at: 0 });
  assert.deepEqual(gridKey(rows, 1, 'Enter'), { at: 1, details: 's' });
  assert.equal(gridKey(rows, 1, 'x'), null);
});
// gateway-details.test.mjs
test('an outside server offers move, adds and removes, and never reads the map', () => { /* outsideCard on github (Claude Code user): actions ['Move into the gateway…', '+ Add to Codex…', '+ Add to Cursor…', 'Remove from Claude Code…'] */ });
test('a client without the entry offers set up; one with it off says so', () => { /* clientCard */ });
test('the Kitden gateway moves every outside server that can go, in one review', () => { /* gatewayCard: actions[0].label matches /^Move all \d+…$/ and its body takes the items of every row with no stays */ });
```

```python
def gw() -> str:
    """The Gateway page's modules as one text."""
    return script("gateway.js") + "\n" + script("gateway-details.js")

def test_the_gateway_lists_by_group_and_keeps_every_action():
    text = gw()
    for words in ('"Outside the gateway · calls skip Kitden\'s rules"', '"Move in…"', '"Move into the gateway…"', '"Remove direct entry…"',
                  "Move all ${", '"Add another gateway…"', '"Use this gateway…"', "Set up in", '"Connect your agents. Shape what they can use."',
                  "The gateway controls only the servers in it. Direct entries and terminal tools are outside it."):
        assert words in text, words
    assert '"/api/map"' not in text and "loadMap(" not in text
    assert 'role", "treegrid"' in script("gateway.js") and "gridKey(" in script("gateway.js")
```

  Replace `script("gateway.js")` with `gw()` in every gateway pin of `test_page_words.py`, then change each pin the deleted code holds, by name:
  - `test_gateway_says_its_lists_are_mcp_servers`: "MCP servers not in the gateway" → `"Outside the gateway · calls skip Kitden's rules"`.
  - `test_gateway_groups_fold`, `test_gateway_show_all_hands_focus_to_the_first_new_row`: go (the List folds by row, the map by "N more").
  - `test_gateway_routes_light_their_rows_and_take_keyboard_focus`: → `role", "treegrid"` and `gridKey(` in `gateway.js`; `fold(box)` and `fold(more)` stay in `gw()`.
  - `test_diagram_nodes_open_the_client_apps_and_the_gateway`: `found.app_url` and `window.open(page, "_blank", "noopener")` stay in `gw()`; `if (url) opens(group` goes.
  - `test_gateway_offers_move_and_keeps_the_side_door_small`: `"Move into the gateway…"`, `"Move all ${"` and `link.classList.add("small", "ghost")` in `gw()`; "In the gateway" goes.
  - `test_held_rows_say_remote_hosted_or_sse_and_keep_addresses_behind_details`: unchanged words in `gw()` (a registered gateway's server rows and Details keep `heldKind`).
  - `test_a_gateway_the_clients_do_not_use_offers_to_take_them_over`: "Use this gateway…" and `"gateway.switch"` stay; `model.used.includes(b.id)` stays as the order of registered gateway blocks in `gatewayTree`.
  - `test_gateway_connect_form_serves_its_own_card_only`: unchanged words, now in `gateway-details.js`.
  - `test_the_kitden_card_says_only_what_it_knows_about_clients`: "Kitden could not read which clients use it." and `if (gateway.problem)` stay; "has it turned off." / "have it turned off." → `"has the kitden entry turned off"`.
  - `test_the_kitden_gateway_card_comes_first_and_sets_up_missing_clients`: the `kitdenCard`/`gatewayCard` order → a node test that the Kitden block comes first in `gatewayTree`; "Nothing yet. Move a server from the lists below." → "Nothing yet. Move a server in from the outside group."; `"Run on this Mac"` and "Only the Kitden gateway can hold them" go; the `parts.js` pins, `kitdenClients(data.setupServer)` and no `server.command`/`server.env` stay.
  - `test_direct_servers_are_options_and_details_offers_move_first`: `GATEWAY_NOTE` in `gw()` (`outsideCard` says it when no gateway takes the server).
  - `test_client_checkboxes_come_from_one_named_part`: the loop reads `offer.js` and `gateway-details.js`.
  - `test_gateway_rows_keep_addresses_behind_a_details_button`: `opens()` in `gateway.js`, no `row.summary`.
  - `test_the_gateway_opens_and_keeps_the_selected_server`: the outside pin is `setState({ selected: { kind: "mcp_server", name: row.name } })`.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** The List is a `div[role=treegrid]` of `div[role=row]` with `aria-level`, `aria-expanded`, one row in the Tab order (roving `tabindex`), `data-focus` `row:<id>`; columns Name, Used by (18 px tiles), Tools, Action. A row's ›, or Enter, opens its Details docked; a gateway row and a client row open theirs.
  Builder call: the List starts with a Clients group and each gateway has its own row, so every Details the map opens has a keyboard path.
  Builder call: a tool row's tag says "Read" or "Write" only when the server says so; a guess from the name says "May write".
  Builder call: an outside row shows no tool count: Kitden does not know it.
- [ ] **Step 4: Update `docs/design.md`:** the Gateway section's intro and the "Kitden gateway card" row become a "Gateway List" row (groups, columns, keys, "Move in…") and an "Outside server, client and gateway Details" row; the Client marks sentence about the route diagram goes; Motion principle 2 says "A link on a map draws once when it appears, then rests."; the "Route focus" pattern row goes.
- [ ] **Step 5: Run** the four checks → PASS. In the demo (medium and large), with the keyboard only: open each kind of Details from the List, Move in…, Set up in Codex…, Add another gateway….
- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/js/gateway.js src/kitden/web/static/js/gateway-details.js src/kitden/web/static/js/dom.js src/kitden/web/static/js/panel.js src/kitden/web/static/style.css docs/design.md tests/frontend/gateway.test.mjs tests/frontend/focus.test.mjs tests/frontend/context.test.mjs tests/frontend/gateway-details.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: a List with Details for clients, gateways and outside servers"
```

---

### Task 7: Tool and server Details, strict words, and the kitden entry back on (4.4)

**Files:**
- Modify: `src/kitden/web/static/js/gateway-details.js` (`toolCard`, `heldCard`), `src/kitden/web/static/js/details.js` (`projectChoice`), `src/kitden/web/static/js/gateway.js` (held and tool rows open them; `showKitdenServer` goes), `src/kitden/web/static/js/parts.js` (`TOOL_ORIGIN_WORDS`, `originText`, `ACTION_WORDS`, `changeTitle`), `src/kitden/web/static/js/tools.js` (`callsText` words; the strict row's words), `src/kitden/web/static/js/review.js` (`changeWords` for `setup_server.enable`), `src/kitden/views/after.py` (`AT_ONCE`, `_strict_line`), `src/kitden/changes/actions.py` (`SETUP_SERVER_ENABLE`), `src/kitden/views/setup_server.py` (`enable_steps`), `src/kitden/local_gateway/views.py` (`shared` on each tool of `tools_view`), `src/kitden/web/app.py` (preview branch), `docs/design.md` (Gateway rows "Tool switches", "A switch changes" → "Tool Details", "Server Details"), `docs/development.md` (hand check step 5 words)
- Test: `tests/frontend/gateway-details.test.mjs`, `tests/frontend/parts.test.mjs`, `tests/frontend/panel.test.mjs`, `tests/unit/test_after.py`, `tests/unit/test_local_gateway_views.py`, `tests/unit/test_setup_server.py`, `tests/unit/test_page_words.py`, `tests/unit/test_docs_words.py`

**Interfaces:**
- Consumes: Task 4's rows and `tools_view`; `heldActions`, `writingToolsOn`, `menuItems`, `ruleText`, `detailsCard`.
- Produces in `details.js`: `projectChoice(projects, picked, onPick) -> HTMLElement`, the scope choice inside a Details column (also for Part 5's skill Details): a `role="listbox"` of `menuItems(projects, picked)` without All projects, starting on the picked project (or the first), with the menu's keys; Enter or a click calls `onPick(id)`; Escape gives focus back to the action that opened it.
- Produces:
  - `TOOL_ORIGIN_WORDS = { global: ALL_PROJECTS, default: "On by default", strict: "New · waits" }` and `originText({ origin, origin_from }, folder) -> string | null`: project → `` `This project · ${folder}` ``, parent → `` `From ${origin_from}` ``.
  - `toolState(tool, picked) -> string`, from `effective`: "Off · server off" (`why === "server_off"`); with a project picked and `origin === "project"`: "On in this project" / "Off in this project"; else "On" / "Off". "The state shown" below is `effective`.
  - `reported(hint, hintFrom) -> string`: server reads → "Read only"; server writes → "May write"; by name → "Not reported · its name suggests it writes"; else "Not reported".
  - `callsText(calls, now)` → `"12 calls · last today 14:02"`, `"1 call · last 20 Oct 09:15"`, null without calls.
  - `toolCard(tool, server, { linked, picked, folder, detail }) -> card` (`detail` is the `/api/gateway/tools` answer's entry for the tool): kind "Tool", title `title || name`, id the name; facts Server (`` `${server.name} · ${Remote|Local}` ``), State (`toolState`), Comes from (`originText`, accent for "project"), Reported, Clients (tiles, "N clients"), Calls (only with calls); why (place: "in any project" with All projects, else `` `in ${folder}` ``): on → `` `${clients} can call this tool through Kitden ${place}.` ``, off → `` `${clients} can't call this tool through Kitden ${place}.` ``, server off → `` `${server} is off ${place}, so none of its tools can be called.` ``; a rule of the project's own adds " Other projects follow the shared rule."; no linked client → "No client uses the Kitden gateway yet." Actions, in order: `origin === "project"` → "Use the shared rule…" (or `` `Use ${follows}'s rule…` `` when it falls back to a parent project) as `gateway.rule` with `state: null` for the picked project; "Turn on for all projects…" / "Turn off for all projects…" (the opposite of the shared state, `project: null`); "Turn on in one project…" / "Turn off in one project…" (the opposite of the state shown), which shows `projectChoice` under the actions (the card's `after`), then the review for the picked one. With the server off: no action, only a button `` `Open ${server}` `` that selects the server.
  - `heldCard(server, { linked, picked, folder, view }) -> card`: kind "MCP server", id "In the Kitden gateway"; facts Kind ("Remote" / "Local · runs on this Mac"), State (as `toolState` for the server, or `` `On in ${plural(on_in, "project", "projects")}` ``), Tools (`` `${on_count} of ${n} on` `` or "Not known yet"), Clients, Projects (`` `${plural(projects, "project has", "projects have")} its own rules` `` when > 0); why: `` `${clients} reach it through the Kitden gateway ${place}.` `` or `` `It is off ${place}, so no client can call its tools.` ``, then "These switches also apply in folders Kitden does not know." with All projects, then `GUARANTEE`-style "Strict: a new tool waits until you turn it on." when strict. Actions: "Use the shared rule…" (own server rule), "Turn off/on for all projects…", "Turn off/on in one project…", "Turn strict mode on…" / "Turn strict mode off…" (`gateway.strict`), "Turn off every writing tool…" (`writingToolsOn(tool_list)`, only while the server is on and one writing tool is on), "Refresh tools", then, in `more`, `heldActions` (Remove, Put back, Keychain) as `{ label, body }`. The first action is `primary`. Links: `kitdenLinks`.
  - `after.py`: `AT_ONCE = "A tool turned off is refused at once; a call already running is not stopped. The client shows the new list in a new session."`; strict on with a known tool list: `` f"Strict mode on for {server}: a new tool waits until you turn it on. Keeps on: {', '.join(kept)}. {GUARANTEE}" `` (`kept`: the cached tools whose global rule is not "off"; "Keeps on: …." left out when empty); unknown tools keep today's words; strict off unchanged.
  - `tools.js` (the Library's switch list until Part 5): the strict line "Only tools that are on are offered; a new tool waits." and `aria-label` "Strict: only tools that are on".
  - `SETUP_SERVER_ENABLE = "setup_server.enable"`; `enable_steps(adapters, client) -> list[Step]` turns the client's `kitden` entry back on, only where Step 1's docs check confirms the key; the client card then offers `` `Turn it on in ${client}…` ``; other clients get the sentence `` `Turn it on in ${client}'s own MCP settings.` ``. Review title `` `Turn on the kitden entry in ${client}` `` (in `PLACE_IN_TITLE`); Changes line "Turned on the kitden entry · <client>".

- [ ] **Step 1: Check the client docs** for turning an MCP entry back on: Codex's `[mcp_servers.<name>] enabled` (developers.openai.com/codex, MCP and config reference), Cursor's MCP settings, Claude Code's settings for a user entry. Write the check date in a comment beside `enable_steps`. Build the step only for what the docs confirm and Kitden already reads as "off" (`codex.py` reads `enabled`); anything else is "not checked" and gets the sentence.
- [ ] **Step 2: Write the failing tests**

```js
// gateway-details.test.mjs
const tool = (fields) => ({ name: 'push_files', title: 'Push files', state: 'off', effective: 'off', hint: 'writes', origin: 'global', origin_from: null, ...fields });
test('a tool off for all projects offers to turn it on, for all or in one project', () => {
  const card = toolCard(tool(), { name: 'github', kind: 'remote', state: 'on' }, { linked: ['claude_code', 'codex'], picked: '', folder: '', detail: { shared: 'off', calls: { count: 12, last: TODAY_1402 } } });
  assert.deepEqual(card.facts.map((f) => [f.label, typeof f.value === 'string' ? f.value : f.text]), [
    ['Server', 'github · Remote'], ['State', 'Off'], ['Comes from', 'All projects'], ['Reported', 'May write'], ['Clients', '2 clients'], ['Calls', '12 calls · last today 14:02']]);
  assert.equal(card.why, "Claude Code and Codex can't call this tool through Kitden in any project.");
  assert.deepEqual(card.actions.map((a) => a.label), ['Turn on for all projects…', 'Turn on in one project…']);
});
test("a project's own rule leads with the shared rule, or its parent's", () => {
  const own = toolCard(tool({ state: 'on', effective: 'on', origin: 'project' }), GITHUB, { linked: LINKED, picked: 'm', folder: 'mcp-gateway', detail: { shared: 'off', follows: null } });
  assert.deepEqual([own.facts[1].value, own.facts[2].value], ['On in this project', 'This project · mcp-gateway']);
  assert.deepEqual(own.actions.map((a) => a.label), ['Use the shared rule…', 'Turn on for all projects…', 'Turn off in one project…']);
  assert.deepEqual(own.actions.map((a) => Boolean(a.primary)), [true, false, false]);
  assert.deepEqual(own.actions[0].body, { action: 'gateway.rule', targets: [], params: { server: 'github', tool: 'push_files', state: null, project: 'm' } });
  const nested = toolCard(tool({ state: 'on', effective: 'on', origin: 'project' }), GITHUB, { linked: LINKED, picked: 'w', folder: 'web', detail: { shared: 'off', follows: 'atlas' } });
  assert.equal(nested.actions[0].label, "Use atlas's rule…");
});
test('a tool of a server that is off says so and offers nothing', () => {
  const card = toolCard(tool({ state: 'on', effective: 'off', why: 'server_off' }), { name: 'files', kind: 'local', state: 'off' }, { linked: LINKED, picked: 'w', folder: 'web', detail: {} });
  assert.equal(card.facts[1].value, 'Off · server off');
  assert.deepEqual(card.actions.map((a) => a.label), ['Open files']);
});
test('a held server holds every server action', () => { /* heldCard medium files, All projects: actions labels incl. 'Turn off for all projects…', 'Turn off in one project…', 'Turn strict mode on…', 'Turn off every writing tool…', 'Refresh tools'; more labels 'Remove from the Kitden gateway…', 'Put back in Codex…' */ });
test('the project choice starts on the picked project', () => { /* projectChoice(PROJECTS, 'm', spy): the selected option is mcp-gateway, no All projects; Enter calls spy('m') */ });
// parts.test.mjs
test('a rule says where its state comes from', () => {
  assert.equal(originText({ origin: 'project' }, 'website'), 'This project · website');
  assert.equal(originText({ origin: 'parent', origin_from: 'atlas' }, 'web'), 'From atlas');
  assert.equal(originText({ origin: 'strict' }), 'New · waits');
});
// panel.test.mjs, edited where it is: 'calls text says how many and when' → '12 calls · last today 14:02', '1 call · last 20 Oct 09:15'
```

```python
# test_after.py
def test_strict_on_names_the_tools_it_keeps_on(tmp_path, monkeypatch):
    note = _strict_note(tmp_path, monkeypatch, True, ["list_issues", "search"])
    assert note.startswith("Strict mode on for github: a new tool waits until you turn it on. Keeps on: list_issues, search.")
    assert note.endswith("a call already running is not stopped. The client shows the new list in a new session.")
# test_setup_server.py
def test_a_codex_kitden_entry_turned_off_can_be_turned_on_and_undone(tmp_path): ...  # preview, apply, verified, undo restores the bytes
# test_page_words.py
def test_tool_and_server_details_use_the_owner_words():
    text = gw() + script("parts.js")
    for words in ('"Use the shared rule…"', "'s rule…", '"Turn on for all projects…"', '"Turn off in one project…"', '"On in this project"',
                  '"Off · server off"', '"Read only"', '"May write"', '"Not reported"', '"New · waits"', '"On by default"', "of ${", " on`"):
        assert words in text, words
    assert "Allowed" not in text and "Blocked" not in text and "Sign in" not in text
```

  Update `test_the_tool_list_has_a_strict_switch` to `"Strict: only tools that are on"`; `AT_ONCE` copies in `test_after.py` and `test_local_gateway_views.py`; `test_cancel_and_a_refused_preview_go_back_to_details` to `keepFrom(() => showHeld(`; `test_readme_names_the_management_actions` keeps passing.
- [ ] **Step 3: Run them to see them fail.**
- [ ] **Step 4: Implement.** The tool card reads `/api/gateway/tools?server=&project=` for `detail` (description, calls, `follows`, and `shared`: add `shared` to each tool in `tools_view`, its state with an empty chain). A review opened from these cards comes back to them (`keepFrom`). In `docs/development.md` step 5 reads: 'Turn strict mode on in the server's Details ("Turn strict mode on…") and turn one tool off.'
  Builder call: with its server off a tool offers no action, only a way to its server: a tool rule there would change nothing anyone can call.
  Builder call: "for all projects" flips the shared state; "in one project" flips the state shown.
  Builder call: the Library's Details of a held server keep `tools.js`'s switch list until Part 5 moves servers to the Gateway.
- [ ] **Step 5: Update `docs/design.md`:** "Tool switches" and "A switch changes" become "Tool Details" (facts, the sentence, actions in order, the project choice in the column, "Server off") and "Server Details" (facts, every server action, strict words); a switch no longer flips in place on the Gateway: the block's mark and link change after `verified`.
- [ ] **Step 6: Run** the four checks and `tests/unit/test_mcp_server.py` → PASS.
- [ ] **Step 7: Commit**

```bash
git add src/kitden/web/static/js/gateway-details.js src/kitden/web/static/js/details.js src/kitden/web/static/js/gateway.js src/kitden/web/static/js/parts.js src/kitden/web/static/js/tools.js src/kitden/web/static/js/review.js src/kitden/views/after.py src/kitden/changes/actions.py src/kitden/views/setup_server.py src/kitden/local_gateway/views.py src/kitden/web/app.py docs/design.md docs/development.md tests/frontend/gateway-details.test.mjs tests/frontend/parts.test.mjs tests/frontend/panel.test.mjs tests/unit/test_after.py tests/unit/test_local_gateway_views.py tests/unit/test_setup_server.py tests/unit/test_page_words.py tests/unit/test_docs_words.py
git commit -m "Gateway Details for tools and servers in the owner's words"
```

---

### Task 8: The Gateway map (4.5: D1–D4, R1, N1)

**Files:**
- Modify: `src/kitden/web/static/js/gateway.js` (map view: selection, lit path, Details, narrow, `drawn`; grips; first run; "N more" opens List), `src/kitden/web/static/js/map.js` (block contents, handles, tags, grip, unfold motion), `src/kitden/web/static/style.css`, `docs/design.md` (Color roles: the direct line; Gateway section: "Gateway map" rows; Motion rows "Unfold" and "Link")
- Test: `tests/frontend/gateway.test.mjs`, `tests/frontend/map.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Produces in `gatewayTree`: `GATEWAY_COLUMNS` captioned "Clients", "Gateway", "Servers", "Tools"; in a project view an outside block whose row has `override` carries the tag "This project" (the List shows block tags too); client `meta` "Connected" / "Not connected", on a first run `` `Found · ${version}` ``; the Kitden gateway `meta` `` `${plural(linked, "client", "clients")} · ${plural(n, "server", "servers")}` ``; on a first run the gateway is a `slot` block "No gateway yet" with "One place for servers, rules and logins." and the action "Set up…" (one `setup_server.register` review for every client in `kitdenClients(setup).setup` with that action); outside blocks join the group captioned "Outside the gateway · calls skip Kitden's rules"; `grip: true` only on an outside block whose row has items, a target, no `stays`, and not on a first run. A first run: `kitdenClients(setup)` has no linked and no off client and the gateway holds nothing.
- Selection: a click or Enter on a block selects it, lights `litPath` (a client lights `litFrom`), opens its Details docked (Task 6–7 cards), and writes `sel` for servers, tools (`tool:`) and clients (`client:`); Enter on a held block also toggles it open (`toggleOpen`); Escape clears the selection, then closes Details. A `more:<group>` block, and an address with `sel=group:<id>` on the map, go to `go("gateway", { mode: "list", selected: { kind: "group", name: id } })`: the List opens that group and focuses it.
- Width: `isNarrow(box width, isPanelOpen() && docked)` picks the narrow layout; a `ResizeObserver` on the map box redraws without drawing links again.
- Links: on the first draw of the page every link is put in `drawn` (they show at once); a link that appears later (an unfold, or after Task 10's `verified`) draws once; nothing moves while idle. An unfold uses `unfoldDelays`.

- [ ] **Step 1: Write the failing tests**

```js
// gateway.test.mjs
test('a first run shows the gateway as a slot to set up and no grips', () => {
  const m = gatewayTree(FIRST_RUN_VIEW, { setup: NO_ENTRIES, clients: FOUND, open: new Set(), held: new Map() });
  const slot = m.blocks.find((b) => b.column === 'gateway');
  assert.deepEqual([slot.kind, slot.name], ['slot', 'No gateway yet']);
  assert.ok(m.blocks.filter((b) => b.kind === 'outside').every((b) => !b.grip));
  assert.equal(m.blocks.find((b) => b.id === 'client:codex').meta, 'Found · 0.48');
});
test('no grip where the row stays', () => { /* rows with stays (plugin, project file, ${…}, last good read) → grip false; a plain remote row → true */ });
test('a Desktop Code tab entry draws its line from Claude Code', () => { /* row.columns ['claude_code'] → link client:claude_code>outside:move:desk, kind 'direct' */ });
test('With All projects a server only some projects turn on says so', () => { /* meta 'On in 2 projects', no link from the gateway */ });
test('in atlas the docs block says This project', () => { /* gatewayTree on the medium atlas view: outside:move:docs tag 'This project'; with All projects none */ });
test('N more and a group address open the List at that group', () => { /* the more block's target: { mode: 'list', selected: { kind: 'group', name: 'outside' } } */ });
// map.test.mjs
test('every block is a button in reading order', () => { /* blockOrder(layout) = column by column, top to bottom; groups are not in it */ });
```

```python
def test_the_map_says_the_link_is_the_state():
    text = gw() + script("map.js")
    for words in ('"Clients"', '"Gateway"', '"Servers"', '"Tools"', '"Connected"', '"Not connected"', "Found · ${", '"No gateway yet"',
                  '"One place for servers, rules and logins."', '"Set up…"', "more`", "In ${"):
        assert words in text, words
    assert "ResizeObserver" in script("gateway.js") and "unfoldDelays(" in script("map.js")
    assert ".link.direct" in CSS and "var(--lamp-warn)" in CSS.split(".link.direct")[1].split("}")[0]
```

- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** Blocks (Components frame): client 150×54 with its 28 px tile, name 12/600 and a 6 px dot (`--lamp-on` / `--lamp-off`) before its state; held 170 wide with a 28 px icon tile, name, meta and a fold count pill on the right edge; open: `--route` border and handle; tool 190×34 with an 8 px square mark, filled `--route` when its `effective` state is on, hollow (`--lamp-off` border) on `--dim` when off; outside on `--dim` with the grip (`--lamp-off`) and a `--lamp-warn` in-handle; the tag "This project" / "Only this project" in `--route` 11 px; selected: `--route-soft` fill and `--route` border; lit links `--route` 1.6 px; a cut name keeps the whole name in `title` and `aria-label`.
  Builder call: direct lines are always elbows; R1's curves are not drawn, so one look means one thing.
  Builder call: links shown on the page's first draw do not draw; only links that appear later do.
- [ ] **Step 4: Update `docs/design.md`:** Color roles: "A server a client sets up on its own is joined to that client by a faint amber elbow (`--lamp-warn` at 55%): its calls skip Kitden's rules. Amber here marks a route outside the rules, not a fault." (the old "Gateway routes use the accent family" sentence goes). Gateway section rows: "Gateway map" (columns, blocks, the link is the state, groups and "N more", outside and grips, tags, selection lights every client's path, narrow N1, first run R1). Motion: an "Unfold" row (links draw, then children fade 15 ms apart, at most 300 ms; reduced motion shows the end) and "Link" (draws once when it appears).
- [ ] **Step 5: Run** the four checks → PASS. Look at it: demo medium at 1440 px with Details open and closed, 1100 px, 900 px; both themes (T1); reduced motion; Tab through every block; nothing moves while idle.
- [ ] **Step 6: Commit**

```bash
git add src/kitden/web/static/js/gateway.js src/kitden/web/static/js/map.js src/kitden/web/static/style.css docs/design.md tests/frontend/gateway.test.mjs tests/frontend/map.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: the map with lit paths, grips, tags and a first run"
```

---

### Task 9: Find on the Gateway (S.6)

**Files:**
- Modify: `src/kitden/web/static/js/app.js` (`#q` input and Escape), `src/kitden/web/static/js/gateway.js` (find on map and List, the chip), `src/kitden/web/static/js/map.js` (`findChip`; `found` dims), `src/kitden/web/static/style.css`, `docs/design.md` (the search sentence in Components)
- Test: `tests/frontend/map.test.mjs`, `tests/frontend/gateway.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `findIn` (Task 1), `toggleOpen`.
- Produces: `const MAP_PAGES = ["gateway"]` in `app.js`, not exported (`app.js` runs `start()` on import; Part 5 adds `"library"` there): on such a page typing in `#q` calls `go(state.view, { q })` and stays; elsewhere today's behaviour stays (`go("library", { q })`). The Gateway runs `findIn(model, state.q)`: matches lit, every other block at opacity 0.35 and links at 0.25 (`.map.finding`), the `open` set added to the open blocks (a match behind "N more" shows its group whole), the same rows lit and parents opened in the List, and a chip `plural(n, "match", "matches")` beside the search (`role="status"`). Escape in `#q` on a map page clears `q`.
- Produces in `map.js` (exported, for every map page): `findChip(found) -> string | null`: null for no search, "No matches" for none, else `plural(n, "match", "matches")`.

- [ ] **Step 1: Write the failing tests**

```js
test('find lights both docs and opens what hides them', () => {
  const found = findIn(gatewayTree(MEDIUM_VIEW, OPTS), 'docs');
  assert.deepEqual([...found.matches].sort(), ['outside:local:docs', 'outside:move:docs']);
  assert.equal(findChip(found), '2 matches');  // findChip from map.js; map.test.mjs also checks null and 'No matches'
  assert.equal(findChip(findIn(gatewayTree(MEDIUM_VIEW, OPTS), 'export')), '1 match');
  assert.ok(findIn(gatewayTree(MEDIUM_VIEW, OPTS), 'export').open.has('held:kitden:tracker'));
});
```

```python
def test_search_on_a_map_page_finds_on_that_page():
    app = script("app.js")
    assert 'MAP_PAGES = ["gateway"]' in app and 'go("library", { q })' in app
    assert '"match", "matches"' in gw() and '"No matches"' in gw()
    assert ".map.finding" in CSS
```

- [ ] **Step 2: Run them to see them fail.** Then **implement**.
- [ ] **Step 3: Update `docs/design.md`:** on the Gateway the search finds on the page: matches light up, the rest dims to 35%, a folded server opens to show a matching tool, a chip says "N matches", Escape clears; Overview and Changes still send a search to the Library.
- [ ] **Step 4: Run** the four checks → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/app.js src/kitden/web/static/js/gateway.js src/kitden/web/static/js/map.js src/kitden/web/static/style.css docs/design.md tests/frontend/gateway.test.mjs tests/unit/test_page_words.py
git commit -m "Gateway: the search finds on the page"
```

---

### Task 10: Apply on the map and drag a server in (S.8, 4.6)

**Files:**
- Modify: `src/kitden/web/static/js/review.js` (the map review), `src/kitden/web/static/js/details.js` (`moveBody`; `moveInto` uses it), `src/kitden/web/static/js/gateway.js` (drag, the drop slot, the preview block and link, the bar), `src/kitden/web/static/js/map.js` (`dropAt`), `src/kitden/web/static/style.css`, `docs/design.md` (Components: "Review bar"; Gateway: "Drag a server in"; Motion: "Map preview")
- Test: `tests/frontend/review.test.mjs`, `tests/frontend/gateway.test.mjs`, `tests/frontend/map.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `changeWords`, `changeOutcome`, `reviewLede`, `stepText`, `undoChange`, `showReview` (export it), `toast`.
- Produces in `review.js`:
  - `mapPreview = { body: null, change: null, phase: "idle", done: 0, total: 0, failure: null, refused: null }` (`phase`: `"idle" | "loading" | "ready" | "applying" | "failed"`).
  - `previewOnMap(body, redraw) -> Promise<void>`: posts the preview with `picked`; a refusal sets `phase "failed"` and `refused` (the server's words); otherwise `phase "ready"`. Another project picked meanwhile cancels it, as `review` does.
  - `barWords(preview) -> { title, outcome, apply, cancelWaits, retry }` (pure): ready → title `changeWords(change, body).title`, outcome `outcomeLine(change)`, apply "Apply"; applying → apply `stepText("Applying", done, total)`, outcome `writingLine(change.steps)`, `cancelWaits: true`; failed → outcome `` `${reason} Nothing was changed.` `` for a refusal or the states `stale` and `restored`, `LOST` alone when the result is unknown, and `retry: true` ("Try again") except for a refusal.
  - `outcomeLine(change) -> string`: the After chips by word, `` `${joinWords(names)}: ${word}.` `` per word; with no chip, the first sentence of the first note.
  - `writingLine(steps) -> string`: one client → `` `Writing ${name}'s settings. A backup is kept.` ``; several → `` `Writing the settings of ${joinWords(names)}. A backup is kept.` ``; the `kitden` client is "the Kitden gateway".
  - `reviewBar(change, { onApply, onCancel, onShow, body }) -> HTMLElement` (`body` is the preview request, for the words): `section.review-bar` (`role="region"`, `aria-label` the title): the title with its scope, the outcome line (`role="status"`), Cancel (disabled while applying, still shown), Apply (or "Try again"), and "Show changes". Errors stay until the next action.
  - `applyOnMap(redraw) -> Promise<void>`, `cancelOnMap(redraw) -> Promise<void>`, `showMapReview(redraw) -> void`: Apply runs `changeOutcome` with the `kitden:progress` counts; `verified` → `reloadAll()`, `mapPreview` back to idle, `redraw()` (the block turns solid and its new link draws once), then the one toast helper both reviews use, `appliedToast(after, body) -> void` in `review.js` (`showApplied` calls it too, so `test_apply_turns_green_only_after_verified_and_only_ok_toasts_get_a_check` keeps its count of 2 `{ ok: true }`); any other end → `phase "failed"`, focus on "Try again" (a new preview, focus to its Apply). Cancel cancels on the server. "Show changes" opens `showReview(change, body, null, back)` in the docked column and hides the bar; that review's Cancel ends the preview, its verified Apply ends as the bar's does.
- Produces in `details.js`: `moveBody(gateway, items) -> { action: "gateway.move", targets: items.map((item) => ({ item })), params: { gateway: gateway.id } }`; `moveInto` previews `moveBody(...)`.
- Produces in `gateway.js`: `dropBody(row, model) -> previewBody` = `moveBody(kitden gateway, row.items)`. A drag starts on a grip (pointer down, 4 px move): the block follows the pointer, its amber line hides, a `slot` block "Drop to add" opens in the row's group of the Kitden gateway (Remote for `move` rows, Local for `local`); dropping on the Servers column calls `previewOnMap(dropBody(row, model))`; Escape or a drop elsewhere puts it back. While a preview is open the map shows a `preview` block (`--preview-fill`, `--preview-line` border) in that group and a `preview` link from the gateway, and the bar at the canvas's bottom left.
- Produces in `map.js`: `dropAt(layout, x, y) -> string | null`: the id of the column whose box (`layout.columns`, full height) holds the point; the Gateway drops only on `"servers"`.
- Moved since (Task 12): the map review now lives in `map-review.js` and the drag (with `dropBody`) in `gateway-drag.js`; `appliedToast` stays in `review.js`.
- Produces in `gatewayTree`: option `preview: { name, kind } | null` (`kind` `"remote"` or `"local"`): a block `preview:<name>` (kind and state `"preview"`) in `group:kitden:<kind>`, with a `preview` link from `gateway:kitden`; the outside row being moved hides its `direct` links while it is there.

- [ ] **Step 1: Write the failing tests**

```js
// review.test.mjs
const change = { id: 'c1', action: 'gateway.move', steps: [{ client: 'kitden', name: 'github' }, { client: 'claude_code', name: 'github' }], after: [{ client: 'claude_code', state: 'gw', word: 'Via gateway' }], target: { scope: 'all' } };
test('the bar says what will happen, then what is being written', () => {
  const body = moveBody({ id: 'kitden', kind: 'kitden' }, ['i1']);
  assert.deepEqual(barWords({ ...IDLE, phase: 'ready', change, body }).outcome, 'Claude Code: Via gateway.');
  const applying = barWords({ ...IDLE, phase: 'applying', change, body, done: 1, total: 3 });
  assert.deepEqual([applying.apply, applying.outcome, applying.cancelWaits], ['Applying 1 of 3', 'Writing the settings of the Kitden gateway and Claude Code. A backup is kept.', true]);
  assert.equal(writingLine([{ client: 'claude_code' }]), "Writing Claude Code's settings. A backup is kept.");
});
test('an error stays and says nothing changed when nothing was written', () => {
  const stale = barWords({ ...IDLE, phase: 'failed', change, body: {}, failure: { state: 'stale' } });
  assert.ok(stale.outcome.endsWith('Nothing was changed.')); assert.equal(stale.retry, true);
  const refused = barWords({ ...IDLE, phase: 'failed', refused: 'github signs in with OAuth; it stays direct for now.' });
  assert.equal(refused.outcome, 'github signs in with OAuth; it stays direct for now. Nothing was changed.'); assert.equal(refused.retry, false);
});
// gateway.test.mjs
test("a drag's preview equals the Move preview", () => {
  const row = MEDIUM_VIEW.groups.move.find((r) => r.name === 'github');
  assert.deepEqual(dropBody(row, MEDIUM_VIEW), moveBody(moveTargets(MEDIUM_VIEW, 'move')[0], row.items));
});
test('a drag takes only its own row\'s entries', () => {
  const docs = MEDIUM_VIEW.groups.local.find((r) => r.name === 'docs');
  assert.deepEqual(dropBody(docs, MEDIUM_VIEW).targets, docs.items.map((item) => ({ item })));
});
test('a preview shows a preview block and link in the right group', () => { /* gatewayTree with preview → preview block parent group:kitden:remote, link kind 'preview' */ });
// map.test.mjs
test('a drop names the column under the point', () => { /* dropAt inside the servers column → 'servers'; over clients → 'clients'; outside every column → null */ });
```

```python
def test_the_map_review_bar_waits_for_verified():
    review = script("review.js")
    for words in ('"Show changes"', '"Try again"', "Nothing was changed.", "A backup is kept.", "export function reviewBar(", "previewOnMap("):
        assert words in review, words
    assert '"Drop to add"' in gw() and "dropBody(" in gw() and "moveBody(" in script("details.js")
    assert "Sign in after Apply" not in review
```

- [ ] **Step 2: Run them to see them fail.** Then **implement.**
  Builder call: the bar names every client the steps write, not the one being written: the engine's progress event names no step, and it writes copies, removals, files and then gateway steps, not in the preview's order.
  Builder call: "Show changes" moves the same preview into the docked column; Cancel there ends it, so one change never has two Apply buttons.
  Builder call: a refused map preview keeps only Cancel: trying again would be refused for the same reason.
  Builder call: a drop always previews a move into the Kitden gateway; a registered gateway stays reachable through "Move into the gateway…".
- [ ] **Step 3: Update `docs/design.md`:** Components "Review bar" (A1–A3: what it says, Apply counts steps, Cancel waits, an error stays and says "Nothing was changed.", "Try again", "Show changes"); Gateway "Drag a server in" (grip, "Drop to add", the preview, the keyboard path "Move in…"); Motion "Map preview" (the preview block turns solid and its link draws once only after `verified`; the toast offers Undo).
- [ ] **Step 4: Run** the four checks → PASS. In the demo: drag `github` in, Apply, see the block turn solid and its link draw once, Undo from the toast; a drag cancelled with Escape; the same by "Move in…" in the List.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/review.js src/kitden/web/static/js/details.js src/kitden/web/static/js/gateway.js src/kitden/web/static/js/map.js src/kitden/web/static/style.css docs/design.md tests/frontend/review.test.mjs tests/frontend/gateway.test.mjs tests/frontend/map.test.mjs tests/unit/test_page_words.py
git commit -m "Map: a review bar on the canvas, and drag a server in"
```

---

### Task 11: Docs, the probe numbers and the roadmap lines

**Files:**
- Modify: `README.md` ("Use one gateway for every client", "The Kitden gateway: tools per project"), `docs/development.md` ("Speed": the gateway view number; "Check before a release": a drag step), `docs/design.md` (one read-through), `tests/unit/test_docs_words.py`
- `ROADMAP.md` only under the master plan's rule.

- [ ] **Step 1: Write the failing test**

```python
def test_readme_shows_the_gateway_as_a_tree_with_a_list():
    readme = " ".join((ROOT / "README.md").read_text().split())
    for words in ("Map | List", '"Use the shared rule…"', '"Turn off in one project…"', "a call already running is not stopped",
                  "Outside the gateway", "Drop to add", "Show changes"):
        assert words in readme, words
    for gone in ("route diagram", "Click a client in the diagram", "tools you turned on"):
        assert gone not in readme, gone
```

- [ ] **Step 2: Run it to see it fail.**
- [ ] **Step 3: Write the README paragraphs,** short and plain: the Gateway is a tree (clients, the gateway, its servers, their tools) or a List; a link is the state; a server a client sets up on its own sits under "Outside the gateway", joined by a faint amber line; click a server to see its tools and a tool to see its path and Details; Details sit beside the page and hold every action ("Turn off for all projects…", "Turn off in one project…", "Use the shared rule…", strict mode, Remove, Put back, the Keychain); drag an outside server onto the servers to see the Move preview on the map, or use "Move in…"; nothing changes until Apply, and a call already running is not stopped. Keep every pinned README sentence.
- [ ] **Step 4: docs/development.md:** "Speed" names the `gateway view` number and `--probe`, and records the probe's numbers with the date and machine; "Check before a release" gains one step numbered after the last existing one (24 today; check the file first): "Drag a server onto the servers on the Gateway map, Apply, and check a new session reaches it through the gateway; Undo from the toast." and "Not run yet for step <N>: Part 4 was tested with sandbox files only."
- [ ] **Step 5: Read `docs/design.md` once** for this part's rows (Color roles, Details beside the page, picker and scope bar, Gateway List, Details, map, find, review bar, drag, Motion): one voice, no repeats, every new word pinned.
- [ ] **Step 6: Run** all four checks and `uv run python scripts/measure-start.py` → PASS.
- [ ] **Step 7: Commit**

```bash
git add README.md docs/development.md docs/design.md tests/unit/test_docs_words.py
git commit -m "Docs: the Gateway map and list"
```

- [ ] **Step 8: Report.** The probe's numbers (Task 1, both versions, and `gateway view` before and after Task 4). If `git status` still shows `ROADMAP.md` modified by the owner, give this line for "### Not released yet" instead of editing it: "**The Gateway is a map and a list:** clients, the gateway, its servers and their tools in one tree, or a List past 15 servers; a link is the state; Details sit beside the page with every action in the owner's words ("On", "Off", "Use the shared rule…"); servers outside the gateway are joined by a faint amber line and can be dragged in, with the preview on the map; the project menu counts each project's own rules; the search finds on the page." Once the owner has committed it, move Part 4's line from "## Planned" to "### Not released yet" with these words, and stage `ROADMAP.md` too.

---

## Builder calls (one line each; they are also beside the step that needs them)

- The hash's `view` lives in `state.mode`; only servers and tools go into the address (`sel`), not client or gateway blocks.
- The probe sample is `build_probe` in `scripts/measure-start.py`; `gateway view` is printed with no budget of its own.
- A group over six folds in `layoutTree` for every map page; unfold timing is 150 ms of links, then children 15 ms apart with a 60 ms fade.
- A Library cell of an item only the project has shows "Only this project" as its tag until Part 5 groups it; `scopeWords` and lowercase "this project" sentences keep their words.
- "Not on here." and "Nothing on here." replace "Not available here." and "Nothing available here.".
- Details dock on Gateway, Library and Changes as a `region`, not a modal dialog; Library Details keep their content until Part 5.
- Text that frames paint `kd-faint` uses `--ink-3`, `kd-ok` text uses `--diff-add`; icons and hollow marks use `--lamp-off`.
- A move's offline refusal is read with the entry at scan time (`Item.stays_direct`), not by re-reading files per row; Codex project layers are left to the preview.
- `own_rules` counts only rules that differ from what the project would otherwise follow (cross-check 24); the scope bar says "follows the shared setup" at 0; All projects stays first while filtering.
- The List starts with a Clients group and each gateway has a row, so every Details has a keyboard path.
- Tool tags: "Read" and "Write" only from the server, "May write" from the name; "Reported" says "Not reported · its name suggests it writes" for a name guess; State adds "Off in this project"; the Calls row shows only with calls.
- A tool's `state` is its own rule's state everywhere; `effective` applies the server's switch and `why: "server_off"` says why; the map and List draw from `effective` (owner ruling 2026-10-24).
- A tool of a server that is off offers only a way to its server; "for all projects" flips the shared state, "in one project" the state shown.
- The Library's held-server Details keep `tools.js`'s switch list until Part 5.
- "Turn it on in <client>…" for the kitden entry is built only where the docs confirm the key (expected: Codex); other clients get a sentence.
- A first run is no client with the kitden entry and an empty gateway; it shows no grips; direct lines are always elbows.
- Links on the page's first draw show at once; later links draw once.
- `reviewBar(change, { onApply, onCancel, onShow, body })` takes the preview request as `body` (owner ruling 2026-10-24); the bar names every client the steps write; "Show changes" moves the preview to Details; a refused map preview keeps only Cancel; a drop always moves into the Kitden gateway.

## Self-review

| Spec | Where |
| --- | --- |
| S.1 words, both tables, one commit; scope words go; "This project" tag | Task 2 |
| S.1 tool words | Task 7 |
| S.2 tokens, kd-faint, kd-ok, contrast | Task 3 |
| S.3 Details beside the page, Escape and focus, drawer below 1024 px and on Overview, layout, `DETAILS_ORDER` kept | Task 3 (shell, `factsBlock`, `detailsCard`); Tasks 6–7 (cards) |
| S.4 layout, renderer, columns, sizes, unfold, link is the state, selection lights every client, keyboard, width, rest, `cutName` | Task 1 (core), Task 8 (page) |
| S.5 Map \| List, address, List past 15, tree grid keys | Task 1 (address, `viewMode`), Task 6 (switch, List) |
| S.6 find | Task 1 (`findIn`), Task 9 |
| S.7 picker, own rules, scope bar | Tasks 4–5 |
| S.8 review bar, steps, writing line, verified then solid and link once, toast Undo, error stays, Try again, Show changes | Task 10 |
| 4.1 probe and its stop rule; measure-start times gateway-view; performance mark | Task 1 |
| 4.2 tool list, on counts, server off, origins, `columns`, own rules, "On in N projects", registered gateway block | Task 4; Task 6 (registered gateway) |
| 4.3 List groups, columns, tools under a server, no Differences, Add missing stays in the Library | Task 6 |
| 4.4 tool, held, outside, client, gateway Details; nothing lost | Tasks 6–7 |
| 4.5 map columns, clients, gateway node, groups and "N more", outside with amber, grips, tags | Task 8 |
| 4.6 drag, slot, same preview as Move, keyboard path | Task 10 |
| Done: node tests (20 and 157 servers, lighting, folding, narrow), List keys, Details facts, drag = Move, probe numbers, words, design.md | Tasks 1, 6, 7, 10, 11 |
