# Part 8: Documentation you can try — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `kitden demo` has a "Tour" button that walks seven short stops over the real map pages on
the sample (one sentence and one lit place each, with a real Apply and Undo inside the demo); the
README answers the owner's three questions with pictures from the demo; `docs/guide.md` is a set
of "I want to…" tasks with small diagrams; the pictures have a written recipe; the notes for
0.3.0 are ready.

**Architecture:** One new module, `tour.js`, holds the stop table (pure data, one stop per line)
and the box that shows it. It is loaded with `import()` the first time Tour is pressed, and Tour
exists only when `/api/about` says `demo`. A stop moves the page by writing its address (Part 2's
`sel=` and `project=`, Part 4's `view=map|list`, Part 5's `show=diff`), then lights the element
that carries `data-tour="<stop id>"`; the page modules draw those anchors. The tour reads only
what the page already has (`data` in `store.js`); it fetches, stores and presses nothing. The docs
are plain Markdown; the diagrams are Mermaid blocks that GitHub draws.

**Tech Stack:** plain ES modules and one CSS file; Python 3.13 (Starlette test client); pytest on
the Part 1 samples; node's test runner. No new dependency.

**Specs:** `docs/superpowers/specs/2026-10-22-visual-management-design.md`, Part 8 (8.1–8.6) and
its Done line, plus Constraints, Anti-goals and Acceptance; and
`docs/superpowers/specs/2026-10-23-map-pages-design.md`, "Order" (the stops on the map pages) with
S.1 (the words "On", "This project", "Only this project"), S.3 (Details beside the page), S.5 (Map
or List) and Parts 4–6. Concept `docs/research/visual-management-ux-concept-2026-10-22.md` §12
(scenes and the seven tasks) and §10 (keyboard, narrow, motion). Master plan:
`docs/superpowers/plans/2026-10-22-visual-management.md` (Rules; names: `data-tour="<stop id>"`
defined here; `GET /api/about`, `create_app(..., demo)`, `kitden demo`, `build_demo_home`, `SIZES`
from Part 1; `parseSel`, `selFor`, `goTo` in `store.js` from Part 2 — `goTo` lives in `store.js`,
not `app.js`; the Details module `details.js` from Part 3). The map plans, by their names:
- Part 4 (`2026-10-23-map-part4-gateway.md`): hash `view=map|list` (`state.mode`), `viewMode`,
  `sel=tool:<server>/<tool>`, `drawMap` (each block is a button with
  `data-focus="block:<id>"`; the map box has the class `map`), block ids `outside:<group>:<name>`
  and `tool:<server>/<tool>`, `gatewayTree`, tool row `origin`/`origin_from`, `/api/gateway-view`
  rows with `columns` and `stays`.
- Part 5 (`2026-10-23-map-part5-library.md`): the Library tab `kind=plugin`, `show=diff`, block ids
  `row:<key>`, the List toolbar button `data-focus="add:missing"`, the align groups `will_add`,
  `already`, `decide`, `cannot` and the `what: "kit"` choice of `project.align`.
- Part 6 (`2026-10-23-map-part6-overview.md`): Overview's "Your setup" tree, `/api/overview`, the
  Changes timeline and its Undo.

The medium sample's names are Part 1's "Sample contract".

## Global Constraints

- `AGENTS.md` in full: code, comments, UI text and docs in simple English, short and plain.
- Every change of a client's settings goes through preview → Apply with a backup → verify → Undo.
  The tour never presses Apply or Undo: the person does, inside the demo.
- The tour runs only in demo mode: `tour.js` is never imported statically and is loaded only after
  `/api/about` answered `"demo": true`.
- Strict CSP stays (`default-src 'self'`, no inline script or style). `tour.js` contains no
  `http`, `fetch(`, `getJson`, `postJson`, `.click()`, `innerHTML` or `localStorage`.
- Main pages keep name, client, state, action. The tour adds one small box and one light; paths
  never show in it.
- Motion (`docs/design.md`): the light is an outline plus the existing `.arrive` glow once;
  nothing loops; reduced motion keeps only the outline; colours come from the theme tokens, so
  both themes work.
- Spec copy, exactly: the button "Tour"; the box title "Tour · 2 of 7"; buttons "Back", "Next",
  "Done", "Close" (its name "Close the tour"); the small-sample sentence "The tour needs the
  medium or large sample: run kitden demo --size medium."; the CLI line "Press Tour on the page
  for a short guided walk."; the stop sentences in Task 1.
- `docs/design.md` changes in the same commit as the page change it describes; new page words are
  pinned in `tests/unit/test_page_words.py` in that commit (master Rules win over "docs last").
- `README.md` is the PyPI page: every image and link is a full `https://` address
  (`tests/unit/test_release_files.py::test_the_readme_works_on_pypi`). Pictures are light/dark JPG
  pairs from `kitden demo --size medium`, never from a real home.
- No version bump and no tag: the release is the owner's step. `docs/releases/v0.3.0.md` is
  written, `pyproject.toml` stays `0.2.0`.
- Tests use `build_demo_home` / Part 1's `demo_page` helper or `make_home`; the conftest guards
  stay on. No real client command, MCP server, Keychain or network.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src
  tests`, `node --test tests/frontend/*.test.mjs`. Stage files by name only. Messages: a short
  plain subject without a prefix, one to three lines, ending with the co-author line the session
  gives.
- `ROADMAP.md`: while `git status` shows it modified by the owner, no task edits or stages it;
  Task 9 writes the lines into the part's report instead.
- Line numbers are hints; find code by name. Parts 1–7 change most files touched here: build on
  what is there.

## Review Focus

1. **The tour on the small sample** (one client, only `atlas`), or a sample whose projects are
   gone: Tour shows one sentence, "The tour needs the medium or large sample: run kitden demo
   --size medium.", and Close; no stop shows a fact that is false there (Task 1 node test 'the
   tour fits only a sample with every project it visits'; Task 4
   `test_demo_names_the_tour_only_for_the_samples_it_fits`).
2. **A stop whose place is not on the page** (Undo before any Apply; an item the person removed
   or hid during the walk): the sentence stays, or Undo's own "Nothing to undo yet…" sentence
   shows; nothing is lit and nothing throws (Task 1 node test 'a stop whose place is not there
   keeps its sentence or says what to do').
3. **Details open while the tour runs** (beside the page from 1024 px, a drawer under it): Tab
   reaches the tour's buttons (the drawer's focus loop includes them), and Esc inside the tour
   closes only the tour, never the Details behind it (Task 1 node test 'keys: arrows move, Escape
   closes, the rest is left alone'; Task 3 `test_the_drawer_lets_tab_reach_the_tour`).
4. **A page that opens in the other view** (the large sample opens in List, and Part 7 may make
   List a page's first view): every stop that draws a map or a List names its view in the
   address, so no stop lands in the wrong one (Task 1 node test 'each stop has its own address
   with the view, the project and the selection').
5. **The real Apply inside the demo:** Add missing's default choice in `atlas` applies, verifies
   and undoes to the same bytes, and the tour itself presses, fetches and stores nothing (Task 2
   `test_add_missing_in_atlas_applies_and_undoes_inside_the_demo`; Task 3
   `test_the_tour_reads_only_the_page_and_presses_nothing`).

---

### Task 1: The stop table and its pure helpers (8.1)

**Files:**
- Create: `src/kitden/web/static/js/tour.js` (this task: the table and the helpers; Task 3 adds
  the box)
- Test: `tests/frontend/tour.test.mjs`

**Interfaces:**
- Consumes (Part 2, `store.js`): `hashFor(state) -> string` (writes `sel` last on every view),
  `parseSel(text) -> {kind, name} | null`, `VIEWS`. (Part 4): `state.mode`, the hash key
  `view=map|list`, and `tool` in the selection kinds (`sel=tool:<server>/<tool>`). (Part 5):
  `"diff"` in `SHOWS`, and the Library tab `kind=plugin`. The medium sample's names (Part 1
  contract): projects `~/work/atlas` and `~/work/atlas/web`; skill `code-review` read by Codex
  and Cursor from one folder; skill `api-style` in `atlas/.agents/skills`, which Claude Code does
  not read; `docs` overridden in `atlas`; held `files` and `tracker`; Cursor's direct `files`;
  `atlas/web` taking `files.write_file` from `atlas`; `tracker.export_report` waiting.
- Produces (`tour.js`):
  - `export const STOPS` — seven objects, **one per line, each line starting `{ id: "`, string
    values in double quotes, no double quote inside a value** (Task 2's Python test reads this
    table). Fields: `id` (also the `data-tour` value), `name`, `view`, optional `kind`, `mode`
    (`"map"` or `"list"`; absent where the place has no choice), `show`, `project` (a folder as
    the end of its path, `""` or absent for All projects), `sel` (`"kind:name"`), `text`,
    optional `ifMissing`.
  - `export const NOT_FIT = "The tour needs the medium or large sample: run kitden demo --size medium."`
  - `export const FIND_MS = 1500` (how long a stop waits for its place)
  - `projectFor(projects: {id, path}[] | null, folder: string) -> string | null` — `""` for `""`;
    the id of the first project whose `path` ends with `"/" + folder`; `null` when none or no list.
  - `tourFits(stops, projects) -> boolean` — every stop's `project` resolves (`projectFor` is not
    `null`).
  - `stopAddress(stop, projects) -> string` — `hashFor({ view, kind: stop.kind || "plugin",
    mode: stop.mode || "", show: stop.show || "mine", category: "", attention: false,
    project: projectFor(...) || "", q: "", selected: stop.sel ? parseSel(stop.sel) : null })`.
  - `stopText(stop, found: boolean) -> string` — `stop.text`, or `stop.ifMissing` when not found
    and the stop has one.
  - `tourTitle(at: number, count: number) -> string` — `` `Tour · ${at + 1} of ${count}` ``.
  - `tourKey(key: string) -> "next" | "back" | "close" | null` — ArrowRight, ArrowLeft, Escape;
    Enter is left to the focused button.
  - `scrollFor(reduced: boolean) -> { block: "center", behavior: "auto" | "smooth" }`.

The table, exactly (map spec "Order", spec 8.1, concept §12):

| id | name | place | text |
| --- | --- | --- | --- |
| `setup` | Your setup | `view "overview"` | Your setup joins each client to the Kitden gateway and the Library; a block opens its page. |
| `shared` | Shared skill | `view "library"`, `kind "plugin"`, `mode "map"`, `sel "skill:code-review"` | Codex and Cursor read code-review from one shared folder, so it is one copy and a change reaches both. |
| `override` | Project override | `view "gateway"`, `mode "map"`, `project "atlas"` | In atlas, the project's own docs entry replaces the one for all projects, and its block carries the tag This project. |
| `differences` | Differences | `view "library"`, `kind "plugin"`, `mode "list"`, `show "diff"`, `project "atlas"` | Differences keeps only the rows where your clients do not match, such as api-style, which Claude Code lacks in atlas. |
| `add-missing` | Add missing | `view "library"`, `kind "plugin"`, `mode "list"`, `project "atlas"` | Press Add missing plugins and skills… to see what each client lacks in atlas, then Apply: it changes the sample files, with a backup. |
| `gateway` | Gateway | `view "gateway"`, `mode "map"`, `project "atlas/web"`, `sel "tool:files/write_file"` | Cursor's amber line skips the gateway; web gets write_file off from atlas; open tracker to see a new tool that waits. |
| `undo` | Undo | `view "changes"`; `ifMissing` "Nothing to undo yet: go Back, press Add missing plugins and skills… and Apply, then come back here." | Undo puts back the files this change wrote, from the backup Kitden kept. |

Builder call: stop `override` shows the `docs` server in `atlas` on the Gateway, because servers
live there now (map spec 5.2), not "the same skill in a project": Claude Code ranks a user skill
above a project one (`views/effective.py RANKS`), so a project skill never overrides, and Part
1's sample override is `docs`. Its place is the outside `docs` block in `atlas` (Claude Code's own
entry, from `atlas/.mcp.json`); Part 4 gives that row the flag `override` and its block the tag
"This project" in a project view, and the stop only reads them.
Builder call: stop `shared` uses `code-review` (Codex and Cursor, one folder), the skill of Part
1's walkthrough task 1; selecting it lights both clients on the Library map. Stop `differences`
uses `api-style`, which `atlas` reads for Codex and Cursor but not Claude Code.
Builder call: stop `add-missing` invites the press of Add missing plugins and skills… and Apply;
stop `gateway` selects `files.write_file` in `web`, whose Details name `atlas` as the rule's
source, and invites opening `tracker`; the tour never presses for the person (spec "one
highlighted place" per stop; the direct route is the amber line on the map).
Builder call: every stop that draws a map or a List writes `view=map` or `view=list` into its
address, so Part 7 or a large sample changing a page's first view never moves a stop.
Builder call: stop names show as the box heading, so the guide can name a stop.

- [ ] **Step 1: Write the failing tests** (`tests/frontend/tour.test.mjs`; stubs as in
  `panel.test.mjs`: `globalThis.matchMedia = () => ({ matches: false })`, `delete
  globalThis.navigator`)

```js
const { STOPS, NOT_FIT, projectFor, scrollFor, stopAddress, stopText, tourFits, tourKey, tourTitle } = await import('../../src/kitden/web/static/js/tour.js');
const { VIEWS, parseSel } = await import('../../src/kitden/web/static/js/store.js');
const PROJECTS = [
  { id: 'p-atlas', path: '/tmp/d/home/work/atlas' },
  { id: 'p-web', path: '/tmp/d/home/work/atlas/web' },
  { id: 'p-site', path: '/tmp/d/home/work/website' },
];
// An address as its place and its fields: the order of the fields is hashFor's, not the tour's.
const parts = (address) => [address.split('?')[0], Object.fromEntries(new URLSearchParams(address.split('?')[1] || ''))];

test('seven stops in the order of the walk, each one short sentence', () => {
  assert.deepEqual(STOPS.map((s) => s.id), ['setup', 'shared', 'override', 'differences', 'add-missing', 'gateway', 'undo']);
  assert.deepEqual(STOPS.map((s) => s.name), ['Your setup', 'Shared skill', 'Project override', 'Differences', 'Add missing', 'Gateway', 'Undo']);
  for (const stop of STOPS) {
    assert.ok(VIEWS.includes(stop.view), stop.id);
    if (stop.sel) assert.ok(parseSel(stop.sel), stop.sel);
    if (stop.mode) assert.ok(['map', 'list'].includes(stop.mode), stop.id);
    for (const text of [stop.text, stop.ifMissing].filter(Boolean)) {
      assert.ok(text.endsWith('.') && !text.slice(0, -1).includes('. '), text);
      assert.ok(text.split(/\s+/).length <= 25 && !text.includes('"'), text);
    }
  }
});

test('each stop has its own address with the view, the project and the selection', () => {
  const at = Object.fromEntries(STOPS.map((s) => [s.id, parts(stopAddress(s, PROJECTS))]));
  assert.deepEqual(at, {
    setup: ['#overview', {}],
    shared: ['#library', { kind: 'plugin', view: 'map', sel: 'skill:code-review' }],
    override: ['#gateway', { view: 'map', project: 'p-atlas' }],
    differences: ['#library', { kind: 'plugin', view: 'list', show: 'diff', project: 'p-atlas' }],
    'add-missing': ['#library', { kind: 'plugin', view: 'list', project: 'p-atlas' }],
    gateway: ['#gateway', { view: 'map', project: 'p-web', sel: 'tool:files/write_file' }],
    undo: ['#changes', {}],
  });
  assert.ok(stopAddress(STOPS.find((s) => s.id === 'gateway'), PROJECTS).endsWith('sel=tool%3Afiles%2Fwrite_file'));
});

test('a project is found by the end of its path', () => {
  assert.equal(projectFor(PROJECTS, ''), '');
  assert.equal(projectFor(PROJECTS, 'atlas'), 'p-atlas');
  assert.equal(projectFor(PROJECTS, 'atlas/web'), 'p-web');
  assert.equal(projectFor(PROJECTS, 'site'), null);   // "website" does not end with "/site"
  assert.equal(projectFor(null, 'atlas'), null);
});

test('the tour fits only a sample with every project it visits', () => {
  assert.equal(tourFits(STOPS, PROJECTS), true);
  assert.equal(tourFits(STOPS, PROJECTS.slice(0, 1)), false);   // the small sample: only atlas
  assert.equal(tourFits(STOPS, null), false);
  assert.equal(NOT_FIT, 'The tour needs the medium or large sample: run kitden demo --size medium.');
});

test('the box counts its seven stops', () => {
  assert.equal(tourTitle(0, STOPS.length), 'Tour · 1 of 7');
  assert.equal(tourTitle(1, 7), 'Tour · 2 of 7');
});

test('a stop whose place is not there keeps its sentence or says what to do', () => {
  const undo = STOPS.find((s) => s.id === 'undo');
  assert.equal(stopText(undo, true), 'Undo puts back the files this change wrote, from the backup Kitden kept.');
  assert.equal(stopText(undo, false), 'Nothing to undo yet: go Back, press Add missing plugins and skills… and Apply, then come back here.');
  const shared = STOPS.find((s) => s.id === 'shared');
  assert.equal(stopText(shared, false), shared.text);
});

test('keys: arrows move, Escape closes, the rest is left alone', () => {
  assert.equal(tourKey('ArrowRight'), 'next');
  assert.equal(tourKey('ArrowLeft'), 'back');
  assert.equal(tourKey('Escape'), 'close');
  for (const key of ['Enter', ' ', 'Tab', 'ArrowUp', 'a']) assert.equal(tourKey(key), null);
});

test('reduced motion scrolls at once', () => {
  assert.deepEqual(scrollFor(true), { block: 'center', behavior: 'auto' });
  assert.deepEqual(scrollFor(false), { block: 'center', behavior: 'smooth' });
});
```

- [ ] **Step 2: Run them to see them fail**: `node --test tests/frontend/tour.test.mjs` → FAIL
  (`tour.js` does not exist).
- [ ] **Step 3: Implement** the table and the helpers in `tour.js`. Module comment: the tour of
  `kitden demo`; loaded only in demo mode; reads the page, never fetches, stores or presses.
  It imports `hashFor` and `parseSel` from `store.js` and nothing that draws.
- [ ] **Step 4: Run** `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/tour.js tests/frontend/tour.test.mjs
git commit -m "Tour: the seven stops and where each one goes"
```

---

### Task 2: Every stop finds its place on the demo (8.1 Done)

**Files:**
- Modify: `src/kitden/web/static/js/overview.js` (the box Overview hands to `drawMap` for "Your
  setup": `dataset.tour = "setup"`), `src/kitden/web/static/js/library.js` (the block `drawMap`
  draws for the selected item of the Library map, found by its `data-focus="block:<id>"`:
  `"shared"`; the `diff` choice of the show group, Installed | Differences: `"differences"`; the
  List toolbar button `data-focus="add:missing"`, "Add missing plugins and skills…":
  `"add-missing"`), `src/kitden/web/static/js/gateway.js` (the first outside block that carries
  the tag "This project", found by its `data-focus="block:<id>"`: `"override"`, and the Gateway
  map's own box, the `.map` box handed to `drawMap`: `"gateway"`),
  `src/kitden/web/static/js/changes.js` (the Undo button of the first verified change drawn in
  the timeline: `"undo"`)
- Create: `tests/unit/test_tour.py`

**Interfaces:**
- Consumes: Task 1 `STOPS` (read from `tour.js` text); Part 1 `demo_page(root, size="medium")`
  and `POST` from `tests/unit/test_demo_mode.py`; Part 4 `/api/gateway-view` group rows'
  `columns`, `override: bool` (Task 4) and `gatewayTree`'s outside blocks
  (`outside:<group>:<name>`) with the tag "This project" in a project view (Task 8),
  `/api/gateway/tools` rows' `origin` and `origin_from` (a folder name), `/api/projects`
  `own_rules`; Part 5
  `/api/library?kind=plugin` rows (`cells[client]["state"]`) with `show=diff`, the align preview's
  `align.will_add` (entries with `kind`, `name`, `to`, `chosen`) and the `what: "kit"` choice of
  `project.align`; Part 6 `/api/overview` and the Changes timeline rows.
- Produces: one `data-tour` anchor per stop id, each set as `node.dataset.tour = "<id>"` in
  exactly one module.

Builder call: there is no browser in the tests, so "each stop's target exists" is checked in two
halves: the anchor is drawn by that place's module, and the demo app answers with the data that
makes it drawn. Task 3 walks the real page by hand.
Builder call: the `shared` and `override` anchors sit on blocks, found with `data-focus`, so
`map.js` stays free of the tour; the box anchors (`setup`, `gateway`) are set where the page makes
the box.

- [ ] **Step 1: Write the failing tests** (`tests/unit/test_tour.py`)

```python
"""The tour's stops find their places on the medium demo (spec 8.1 Done)."""

import re
from pathlib import Path

from kitden.gateways import data_dir
from tests.unit.test_demo_mode import POST, demo_page

JS = Path(__file__).parents[2] / "src/kitden/web/static/js"
DRAWN_BY = {
    "setup": "overview.js", "shared": "library.js", "override": "gateway.js",
    "differences": "library.js", "add-missing": "library.js", "gateway": "gateway.js",
    "undo": "changes.js",
}


def tour_stops() -> list[dict]:
    """tour.js writes one stop per line; this reads the string fields of each."""
    lines = (JS / "tour.js").read_text().splitlines()
    return [dict(re.findall(r'(\w+): "([^"]*)"', line)) for line in lines
            if line.strip().startswith('{ id: "')]


def project_for(page, folder: str) -> str:
    if not folder:
        return ""
    return next(p["id"] for p in page.get("/api/projects").json()
                if p["path"].endswith("/" + folder))


def snapshot(home: Path) -> dict:
    data = data_dir(home)
    return {p: p.read_bytes() for p in home.rglob("*")
            if p.is_file() and data not in p.parents}


def test_each_stop_is_lit_by_the_one_module_that_draws_its_place():
    assert [s["id"] for s in tour_stops()] == list(DRAWN_BY)
    modules = {p.name: p.read_text() for p in JS.glob("*.js")}
    for stop, module in DRAWN_BY.items():
        anchor = f'dataset.tour = "{stop}"'
        assert [name for name, text in modules.items() if anchor in text] == [module], stop


def overrides(page, project: str) -> list[dict]:
    view = page.get("/api/gateway-view", params={"project": project} if project else {}).json()
    return [r for rows in view["groups"].values() for r in rows if r["override"]]


def test_every_stop_finds_its_place_on_the_medium_demo(tmp_path):
    stops = {s["id"]: s for s in tour_stops()}
    with demo_page(tmp_path / "demo") as page:
        at = {i: project_for(page, s.get("project", "")) for i, s in stops.items()}
        # setup: three clients, and atlas has rules of its own for the projects line
        found = [c for c in page.get("/api/clients").json() if c["status"] == "found"]
        assert len(found) == 3
        own = {Path(p["path"]).name: p["own_rules"] for p in page.get("/api/projects").json()}
        assert own["atlas"] > 0 and page.get("/api/overview").status_code == 200
        # shared: Codex and Cursor load code-review, Claude Code does not
        shared = stops["shared"]
        kind, name = shared["sel"].split(":", 1)
        rows = page.get("/api/library", params={"kind": shared["kind"]}).json()["rows"]
        skill = next(r for r in rows if (r["kind"], r["name"]) == (kind, name))
        assert {c for c, cell in skill["cells"].items() if cell["state"] == "on"} == {"codex", "cursor"}
        # override: Part 4's flag on atlas's own docs; All projects has none
        assert [r["name"] for r in overrides(page, at["override"])] == ["docs"]
        assert overrides(page, "") == []
        # differences: api-style is read by Codex and Cursor in atlas, not by Claude Code
        diff = stops["differences"]
        rows = page.get("/api/library", params={"kind": diff["kind"], "show": diff["show"],
                                                "project": at["differences"]}).json()["rows"]
        assert "api-style" in {r["name"] for r in rows}
        # gateway: Cursor's direct files, the parent's rule on write_file, the waiting tool
        server, tool = stops["gateway"]["sel"].split(":", 1)[1].split("/", 1)
        view = page.get("/api/gateway-view", params={"project": at["gateway"]}).json()
        assert {s["name"] for s in view["gateways"][0]["servers"]} >= {"files", "tracker"}
        assert any(r["name"] == server and "cursor" in r["columns"]
                   for rows in view["groups"].values() for r in rows)
        files = page.get("/api/gateway/tools",
                         params={"server": server, "project": at["gateway"]}).json()["tools"]
        assert {t["name"]: (t["origin"], t["origin_from"]) for t in files}[tool] == (
            "parent", "atlas")
        tracker = page.get("/api/gateway/tools",
                           params={"server": "tracker", "project": at["gateway"]}).json()["tools"]
        assert {t["name"]: t["origin"] for t in tracker}["export_report"] == "strict"


def test_add_missing_in_atlas_applies_and_undoes_inside_the_demo(tmp_path):
    stop = next(s for s in tour_stops() if s["id"] == "add-missing")
    with demo_page(tmp_path / "demo") as page:
        before = snapshot(page.home)
        body = {"action": "project.align", "targets": [],
                "params": {"project": project_for(page, stop["project"]), "what": "kit",
                           "chosen": None}}
        change = page.post("/api/changes/preview", json=body, headers=POST).json()
        assert any(e["chosen"] for e in change["align"]["will_add"])
        assert {e["kind"] for e in change["align"]["will_add"]} <= {"plugin", "skill"}
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert snapshot(page.home) != before
        entries = page.get("/api/changes").json()
        assert any(e["id"] == change["id"] and e["state"] == "verified" for e in entries)  # stop undo
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
        assert snapshot(page.home) == before
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_tour.py -v` → the
  anchor test FAILS (no `dataset.tour` yet); the demo tests should already pass on Parts 1–7. If
  `test_add_missing_in_atlas_applies_and_undoes_inside_the_demo` fails because a checked item
  needs a command the demo runner refuses ("Not part of the demo."), extend Part 1's `DemoRunner`
  for that command (it edits only the sample's files) with a test in
  `tests/unit/test_demo_stand_ins.py`, in this task.
- [ ] **Step 3: Implement** the seven anchors. `changes.js` anchors only the first verified
  row's Undo; `gateway.js` only the first tagged outside block;
  `library.js` only the selected item's block. No other change to how anything looks.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_tour.py tests/unit/test_page_words.py -v` and
  `node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/kitden/web/static/js/overview.js src/kitden/web/static/js/library.js \
  src/kitden/web/static/js/gateway.js src/kitden/web/static/js/changes.js tests/unit/test_tour.py
git commit -m "Tour: each page marks the place its stop lights"
```

(Add `src/kitden/demo/runner.py` and `tests/unit/test_demo_stand_ins.py` only if Step 2 needed them.)

---

### Task 3: The tour box: moving, the light, keys and focus (8.1)

**Files:**
- Modify: `src/kitden/web/static/js/tour.js` (`startTour` and its private parts)
- Modify: `src/kitden/web/static/js/panel.js` (`trapFocus`: the tour's buttons join the loop, as
  the toast's do)
- Modify: `src/kitden/web/static/style.css` (`.tour`, `.tour-on`, `.tour-glow`; the 900 px rule)
- Modify: `docs/design.md` (Components: a "Tour" table; Motion, Patterns: one row)
- Test: `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Task 1 helpers; `data`, `busy`, `loadShared` (still exported after Part 7, which
  only stopped `start()` from calling it), `render` (`store.js`); `closePanel`, `isPanelOpen`
  (`panel.js`); `reducedMotion` (`motion.js`); `el` (`dom.js`).
- Produces: `export async function startTour(opener: HTMLElement | null): Promise<void>` — the
  only entry Task 4 calls.

Behaviour (the parts a node test cannot reach; keep each short):
- Start: if `data.projects` is null, `await loadShared()`. Stops are `STOPS`. One box per page: a
  second press focuses the open box's Next. When `!tourFits(STOPS, data.projects)` the box shows
  `NOT_FIT` and Close only.
- The box: `section#tour.tour`, `role="dialog"`, `aria-modal="false"`,
  `aria-labelledby="tour-title"`, appended to `body` (outside `#main`, so redraws keep it):
  `p.kicker` `tourTitle(at, count)`, `h2#tour-title` the stop's `name`, `p.tour-text` with
  `aria-live="polite"`, then Back (`btn small`, disabled on the first stop), Next (`btn small
  primary`, "Done" on the last; Done closes), Close (`btn ghost small`, `aria-label` "Close the
  tour").
- Moving to a stop: while `busy.change` nothing moves (the review already says it is writing).
  Close an open Details with `closePanel({ focus: false })`. Then set `location.hash =
  stopAddress(stop, data.projects)` when it differs (the page follows the address as for Back;
  each stop is a history entry and a real link; its `view=` opens the map or the List, and its
  `sel=` opens that item's Details once, as any link does), else call `render()`. Update the
  title, heading and text at once.
- Finding the place: while the box is open one `MutationObserver` on `body` (`childList`,
  `subtree`) looks for `[data-tour="<id>"]` after each change. When found: add `tour-on`; on the
  first find for this stop also `tour-glow` and `scrollIntoView(scrollFor(reducedMotion.matches))`.
  A redraw that replaces the node lights the new one with `tour-on` only. After `FIND_MS` without
  it the text becomes `stopText(stop, false)`; a later find switches back to `stop.text`. Moving
  removes both classes from the old node.
- Focus: when the place is found or `FIND_MS` ends, focus goes to Next (Done) if focus is on the
  body, `#main`, `#drawer` itself or inside the box — not when the person moved to another
  control. Close (button, Done or Esc) removes the light, stops the observer, removes the box and
  focuses `opener` if it is still on the page, else `#main`.
- Keys on the box (`keydown` on `#tour`, no modifier): `tourKey(event.key)`; next and back act
  like their buttons when enabled; close closes; each calls `preventDefault()` and
  `stopPropagation()`, so the drawer's Escape does not also close Details.
- `trapFocus` (panel.js): when `#tour` is on the page, its enabled buttons are in the loop after
  the drawer's and the toast's, and focus inside `#tour` counts as inside.
- CSS, tokens only: `.tour { position: fixed; z-index: 25; left: 232px /* rail 216 + 16 */;
  bottom: 16px; width: min(340px, calc(100vw - 32px)); background: var(--panel-raised);
  box-shadow: var(--shadow-pop); border-radius: 10px; padding: 12px 14px; display: grid; gap:
  8px }`; under 900 px `top: 8px; bottom: auto; left: 16px; right: 16px; width: auto`.
  `.tour-on { outline: 2px solid var(--focus); outline-offset: 3px }`,
  `.map.tour-on, .treegrid .tour-on { outline-offset: -2px }` (the outline of a map box or a List
  row stays inside its scrolling box),
  `.tour-glow { animation: arrive 1200ms var(--ease-out) 1 }` (the existing keyframe). The
  reduced-motion rule at the end of the file already stops the glow.

Builder call: a stop moves by writing its address, not with `goTo`, because a stop may also change
the project, and the address is the one path that carries view, Map or List, project, tab and
selection together.
Builder call: the box sits above the drawer (21) and the scrim (20) and below the toast (30); at
the bottom left it never covers the Details column (beside the page from 1024 px) or the drawer's
Apply, and under 900 px it sits at the top for the same reason.
Builder call: the light is the focus-colour outline plus the `.arrive` glow once per stop; a
redraw (live rescan) re-lights without the glow, so nothing moves while idle.
Builder call: a stop waits 1.5 s for its place (Details read `/api/explain` first); after that
the "not there" sentence shows.

- [ ] **Step 1: Write the failing tests** (`tests/unit/test_page_words.py`)

```python
def test_the_tour_reads_only_the_page_and_presses_nothing():
    tour = script("tour.js")
    for banned in ("http", "fetch(", "getJson", "postJson", ".click()", "innerHTML", "localStorage"):
        assert banned not in tour, banned
    for words in ('"Back"', '"Next"', '"Done"', '"Close"', '"Close the tour"', 'aria-live'):
        assert words in tour, words


def test_the_tour_box_and_light_use_theme_colours_only():
    css = (STATIC / "style.css").read_text()
    rules = [line for line in css.splitlines() if ".tour" in line]
    assert any(".tour-on" in line for line in rules) and any(".tour-glow" in line for line in rules)
    assert not any(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", line) for line in rules)


def test_the_drawer_lets_tab_reach_the_tour():
    assert '"#tour"' in script("panel.js")
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_page_words.py -v` → FAIL.
- [ ] **Step 3: Implement** `startTour` and the CSS as above; `trapFocus` in `panel.js`.
- [ ] **Step 4: Update `docs/design.md`.** Under Components, after the Gateway tables:

```markdown
### Tour

Only in `kitden demo`. `tour.js` holds the seven stops and their words.

| Part | Look |
| --- | --- |
| Box | A raised card at the bottom left of the page, left of Details and the drawer (at the top under 900 px), above the drawer and below the toast: "Tour · 2 of 7", the stop's name, one sentence, then Back, Next ("Done" on the last stop) and Close. |
| Light | The stop's place gets a 2 px outline in the focus colour and the `.arrive` glow once. A redraw keeps the outline without the glow; reduced motion keeps only the outline. |
| Moving | Each stop opens its place by its address, so Back and a copied link work; the address also picks Map or List; an open Details closes first. A stop waits up to 1.5 s for its place; without it the sentence stays, unlit (Undo says what to do first). Nothing moves while a change is written. |
| Keys | Arrow keys move, Enter presses, Esc closes the tour (inside the box); Tab reaches the box while Details is open. Focus goes to Next at each stop and back to Tour at the end. |
| Never | Fetches, stores or presses anything, or runs outside the demo. Apply and Undo stay the person's. |
```

  Motion, Patterns table: `| Tour light | `.tour-on` outline + `.tour-glow` once | The tour's place, in `kitden demo` |`.
- [ ] **Step 5: Look at it.** `uv run kitden demo --size medium --no-browser` (background), open
  the printed link in the built-in browser (until Task 4, start the tour from the console:
  `import("/static/js/tour.js").then((t) => t.startTour(null))`). Walk all seven stops in light
  and dark (`resize_window` with `colorScheme`), at 1280 × 800 and at 700 × 800; the first stop
  lights "Your setup"; the second shows the Library map with `code-review` selected and both
  clients lit; the third shows the `docs` block in `atlas` with its tag; press Add missing
  plugins and skills… and Apply at the fifth, then Undo at the last stop; walk once by keyboard
  only, with Details open at the Shared skill stop (it docks beside the map at 1280 px and is the
  drawer at 700 px; Tab reaches Next; Esc in the box closes the tour and leaves Details).
  Note each stop's result in the task report.
- [ ] **Step 6: Run all checks**, then commit

```bash
git add src/kitden/web/static/js/tour.js src/kitden/web/static/js/panel.js \
  src/kitden/web/static/style.css docs/design.md tests/unit/test_page_words.py
git commit -m "Tour: a small box that lights one place per stop"
```

---

### Task 4: The Tour button, only in the demo (8.1)

**Files:**
- Modify: `src/kitden/web/static/js/parts.js` (`tourButton`), `src/kitden/web/static/js/app.js`
  (in `start()`, where Part 1 appends `demoTag(about)` to `.brand`)
- Modify: `src/kitden/cli.py` (`_demo`: one more printed line)
- Modify: `docs/design.md` (the Tour table gains its first row)
- Test: `tests/frontend/parts.test.mjs`, `tests/unit/test_page_words.py`, `tests/unit/test_cli.py`

**Interfaces:**
- Consumes: Part 1 `/api/about` read once in `start()`, `demoTag(about)`, `_demo(args)` and the
  test helper `_demo_run(monkeypatch, seen, server=None)` in `tests/unit/test_cli.py`; Task 3
  `startTour(opener)`.
- Produces: `tourButton(about, onPress: (node) => void) -> HTMLElement | null` (parts.js): for
  `about.demo`, `el("button", "btn small tour-start", "Tour")` with `type = "button"`,
  `dataset.focus = "tour"`, and a click listener calling `onPress(node)`; otherwise `null`.
  `app.js` appends it after the Demo flag with
  `(node) => import("./tour.js").then((tour) => tour.startTour(node)).catch(reportError)`.
  `_demo` prints `Press Tour on the page for a short guided walk.` after the Ctrl+C line, for
  `medium` and `large` only.

Builder call: `tour.js` loads on the first press, not at start, so the demo opens as fast as the
real page.
Builder call: the CLI names the tour only for the samples it fits; the button still shows on
`small` and says why it cannot walk there.

- [ ] **Step 1: Write the failing tests**

```js
// tests/frontend/parts.test.mjs (import tourButton with the others)
test('only a demo has a Tour button, and it hands itself to the tour', () => {
  let pressed = null;
  const node = tourButton({ version: '0.2.0', demo: true }, (n) => { pressed = n; });
  assert.equal(node.textContent, 'Tour');
  assert.equal(node.className, 'btn small tour-start');
  node.listeners.click();
  assert.equal(pressed, node);
  assert.equal(tourButton({ version: '0.2.0', demo: false }, () => {}), null);
  assert.equal(tourButton(null, () => {}), null);
});
```

```python
# tests/unit/test_page_words.py
def test_the_tour_loads_only_when_the_page_is_a_demo():
    assert 'import("./tour.js")' in script("app.js")
    for path in (STATIC / "js").glob("*.js"):
        assert 'from "./tour.js"' not in path.read_text(), path.name
    assert "tour.js" not in INDEX and '"Tour"' in script("parts.js")
```

```python
# tests/unit/test_cli.py
@pytest.mark.parametrize(("size", "named"), [("medium", True), ("small", False)])
def test_demo_names_the_tour_only_for_the_samples_it_fits(monkeypatch, capsys, size, named):
    _demo_run(monkeypatch, {})
    assert main(["demo", "--no-browser", "--size", size]) == 0
    out = capsys.readouterr().out
    assert ("Press Tour on the page for a short guided walk." in out) is named
```

- [ ] **Step 2: Run them to see them fail**: `node --test tests/frontend/parts.test.mjs`,
  `uv run pytest tests/unit/test_page_words.py tests/unit/test_cli.py -v` → FAIL.
- [ ] **Step 3: Implement** as the Interfaces say. In `docs/design.md`'s Tour table add first:
  `| Button | A small plain "Tour" after the Demo flag; `tour.js` loads the first time it is pressed. On the small sample the box says the tour needs the medium or large one. |`
- [ ] **Step 4: Run** the same commands → PASS. Then once by hand: `uv run kitden demo` prints the
  line; Tour opens the box at the Your setup stop; `uv run kitden demo --size small` → Tour says it needs
  the medium or large sample.
- [ ] **Step 5: Run all checks**, then commit

```bash
git add src/kitden/web/static/js/parts.js src/kitden/web/static/js/app.js src/kitden/cli.py \
  docs/design.md tests/frontend/parts.test.mjs tests/unit/test_page_words.py tests/unit/test_cli.py
git commit -m "Demo: a Tour button that loads the tour when pressed"
```

---

### Task 5: The picture recipe, and new pictures from the demo (8.4)

**Files:**
- Modify: `docs/development.md` (a new section `## Pictures`, before `## Release`)
- Replace: `docs/images/overview.jpg`, `library.jpg`, `review.jpg`, `gateway.jpg` and their
  `-dark.jpg` twins; Create: `docs/images/tour.jpg`, `docs/images/tour-dark.jpg`
- Test: `tests/unit/test_docs_words.py`

**Interfaces:**
- Consumes: Tasks 1–4 (the tour's addresses and stops); Part 1 `kitden demo --no-browser`.
- Produces: ten JPG files (Task 7's README uses them in this order: overview, tour, library,
  gateway, review).

The recipe, written into `docs/development.md` as a short intro, five rules and this table:

| Picture | Tour stop | Scene |
| --- | --- | --- |
| `overview.jpg` | Your setup | All projects; Overview with its cards and the "Your setup" tree; tour closed |
| `tour.jpg` | Shared skill | All projects; Library, Plugins and skills, Map; `code-review` selected, Codex and Cursor lit, its Details beside the map; the tour box at this stop |
| `library.jpg` | Differences | `atlas`; Library, Plugins and skills, List, Differences; no Details |
| `review.jpg` | Add missing | `atlas`; Library List; the Add missing plugins and skills… review open in the Details column before Apply; file changes folded |
| `gateway.jpg` | Gateway | `atlas/web`; Gateway map; `write_file` selected, its Details beside the map showing "From atlas"; Cursor's amber line in view |

Rules: run `uv run kitden demo --size medium --no-browser` and open the printed link in the
built-in browser (never a real home: the sample is synthetic, so no personal path can show);
window 1280 × 800 CSS pixels on a 2× screen, saved 2560 × 1600; each scene in light, then dark
(`-dark.jpg`): the page follows the system theme, and the theme button sets it when a saved choice
wins; Technical details folded, no hover text, no cursor; JPG quality 80, each file under 500 KB
(`sips -s format jpeg -s formatOptions 80 <shot>.png --out docs/images/<name>.jpg`).

Builder call: the agent sets each scene up and checks it with the built-in browser's screenshot,
then saves it with `screencapture -x -R<x>,<y>,1280,800 <shot>.png` of the browser pane's area
(found once from a full `screencapture -x`), because the browser tool shows screenshots to the
agent but writes no file. If the shell may not capture the screen (macOS asks for Screen
Recording), the agent stops and asks the owner to save the shown scene with Shift-Cmd-4, Space,
a click on the pane, to the named file.
Builder call: the four old names are reused, so no README link breaks before Task 7.

- [ ] **Step 1: Write the failing test**

```python
PICTURES = ("overview", "tour", "library", "review", "gateway")


def test_the_picture_recipe_names_the_sample_the_window_and_every_scene():
    text = (ROOT / "docs/development.md").read_text()
    assert "## Pictures" in text and "kitden demo --size medium" in text and "1280 × 800" in text
    for name in PICTURES:
        assert f"`{name}.jpg`" in text, name
        for file in (f"{name}.jpg", f"{name}-dark.jpg"):
            assert (ROOT / "docs/images" / file).stat().st_size < 500_000, file
```

- [ ] **Step 2: Run it to see it fail**: `uv run pytest tests/unit/test_docs_words.py -v` → FAIL.
- [ ] **Step 3: Write the recipe** into `docs/development.md`.
- [ ] **Step 4: Make the ten pictures** by following the recipe with the built-in browser on the
  demo page: `resize_window` to 1280 × 800 with `colorScheme: "light"`, then `"dark"`; reach each
  scene through the tour (Tour → the stop) or its address, open what the table says, close the
  tour box except for `tour.jpg`, check with a screenshot, save, convert. Look at every saved file:
  no path, no `DEMO_SECRET_`, nothing cut off, the right theme. Stop the demo (Ctrl+C); its folder
  is deleted.
- [ ] **Step 5: Run** `uv run pytest tests/unit/test_docs_words.py -v` → PASS; then all checks.
- [ ] **Step 6: Commit**

```bash
git add docs/development.md tests/unit/test_docs_words.py \
  docs/images/overview.jpg docs/images/overview-dark.jpg docs/images/tour.jpg docs/images/tour-dark.jpg \
  docs/images/library.jpg docs/images/library-dark.jpg docs/images/review.jpg docs/images/review-dark.jpg \
  docs/images/gateway.jpg docs/images/gateway-dark.jpg
git commit -m "Docs: pictures from the demo, and how to make them"
```

(The ten JPGs make a large push: `git -c http.postBuffer=524288000 push` if it fails with HTTP 400.)

---

### Task 6: A task guide, `docs/guide.md` (8.3)

**Files:**
- Create: `docs/guide.md`
- Test: `tests/unit/test_docs_words.py`

**Interfaces:**
- Consumes: the stop names (Task 1); the README's how-to sentences (they move here; Task 7 drops
  them from the README).
- Produces: six sections with these exact headings, in this order (Task 7 links the file).

The guide, in simple English, uses the demo's names so a reader can follow it in `uvx kitden
demo`. Intro (three lines): what the guide is, "Try each task on the sample: `uvx kitden demo`,
then Tour.", and that Kitden reads saved settings, not a running session. Each section: numbered
steps (3–6, page words in bold), one Mermaid block with no colours (no `style`, `classDef` or
`fill:`, so GitHub draws it in the reader's theme), then the line `In the tour: **<stop name>**.`

| Heading | Steps cover (and the README sentences that move here) | Diagram (`flowchart LR`) | Tour stop |
| --- | --- | --- | --- |
| `## I want to see what loads where` | Overview → "Your setup"; Library → Plugins and skills → Map: select an item to light the clients that load it; the List shows the same by keyboard; a project in the project menu at the top; Details' Facts and Why; "Remove from <client>…" with Undo; Unknown and Needs review; the Instructions tab | shared folder `~/.agents/skills` → `code-review` → Codex, Cursor | Your setup, Shared skill |
| `## I want to find what differs in a project` | pick `atlas` in the project menu (the scope bar counts the rules that differ); Library List → Differences; the tag "This project" and the group "Only this project"; the Gateway in `atlas`, where `docs` carries the tag; under All projects the menu counts each project's own rules | All projects `docs` ⇢ overridden in `atlas` by `atlas/.mcp.json docs` | Project override, Differences |
| `## I want to add what is missing` | "Add missing plugins and skills…" in the Library List and "Add missing servers…" on the Gateway List, and the four groups; "+ Add", "+ Add skills", "+ Add the plugin"; the add panel beside Plugins and skills (search the marketplaces, click to preview on the map); "Add to this project…" / "Add for all projects…"; '"+ Add" on an MCP server copies its entry to another client' and the `${VAR}` rule | Review → Apply (backup) → Checked → Undo | Add missing |
| `## I want to keep a server behind the gateway` | "Set up in <client>…"; "Move into the Kitden gateway…", "Move in…" in the List, or drag an outside server onto the servers and read the preview ("Show changes"); secrets go to the Keychain; "Put back in <client>…"; "Remove from the Kitden gateway…"; the group "Outside the gateway" and the servers that stay direct, and why | Claude Code, Codex → Kitden gateway → `files`; Cursor -- Direct --> `files` | Gateway |
| `## I want to block a tool for one project` | pick the project; Gateway → unfold the server → select the tool; in the tool's Details, "Turn off in one project…" with its own project choice, which starts at the picked project; the origin words ("This project", "From atlas", "All projects", "On by default", "New · waits"); "Use the shared rule…" or "Use atlas's rule…"; strict mode; "In a folder Kitden does not know as a project, the All projects switches apply."; a call already running is not stopped | All projects → `atlas` (`write_file` off) → `atlas/web` (follows `atlas`) | Gateway |
| `## I want to undo a change` | Changes → the day's row → Undo, or Undo in the toast; "See it on the map"; what Undo puts back and its limits (a plugin's saved options); backups kept 30 days, the newest 100 always; what to restart | Change → Backup; Undo → Backup → files as before | Undo |

- [ ] **Step 1: Write the failing test**

```python
GUIDE_SECTIONS = (
    "I want to see what loads where",
    "I want to find what differs in a project",
    "I want to add what is missing",
    "I want to keep a server behind the gateway",
    "I want to block a tool for one project",
    "I want to undo a change",
)
STOP_NAMES = "Your setup|Shared skill|Project override|Differences|Add missing|Gateway|Undo"


def test_the_guide_has_six_tasks_each_with_steps_a_diagram_and_a_tour_stop():
    text = (ROOT / "docs/guide.md").read_text()
    sections = re.split(r"(?m)^## ", text)[1:]
    assert [s.splitlines()[0] for s in sections] == list(GUIDE_SECTIONS)
    for section in sections:
        assert section.count("```mermaid") == 1, section[:40]
        assert re.search(r"(?m)^1\. ", section), section[:40]
        assert re.search(rf"(?m)^In the tour: \*\*({STOP_NAMES})\*\*", section), section[:40]
    diagrams = re.findall(r"```mermaid\n(.*?)```", text, re.S)
    assert not any(re.search(r"\bstyle\b|classDef|fill:", d) for d in diagrams)
    assert "uvx kitden demo" in text
```

- [ ] **Step 2: Run it to see it fail**: `uv run pytest tests/unit/test_docs_words.py -v`.
- [ ] **Step 3: Write `docs/guide.md`** as the table says. Every sentence a README pin holds today
  (run `grep -n "readme" tests/unit/test_docs_words.py` and read each pinned string) that belongs
  to one of these tasks is copied here word for word.
- [ ] **Step 4: Run it to see it pass**, then all checks. Open the file on GitHub's preview (or
  any Mermaid viewer) once: each diagram draws.
- [ ] **Step 5: Commit**

```bash
git add docs/guide.md tests/unit/test_docs_words.py
git commit -m "Docs: a guide of I want to… tasks"
```

---

### Task 7: README around the three questions (8.2)

**Files:**
- Modify: `README.md` (rewritten)
- Modify: `tests/unit/test_docs_words.py` (new pins; pins of moved sentences read the guide)

**Interfaces:**
- Consumes: Task 5's pictures, Task 6's guide.
- Produces: the README below; its links stay full `https://` addresses.

Outline (simple English, under 160 lines, each picture a `<picture>` pair as today with the
`https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/` base):
1. Logo, title, the tagline "See and safely change what your AI coding agents load.", one line
   naming the three questions; picture `overview` (alt: "Kitden Overview: cards for what needs
   attention, and the Your setup tree joining the clients to the Kitden gateway and the Library").
2. "Try it on a sample setup first, with nothing on your computer read or changed:" then
   `uvx kitden demo`, then "Press **Tour** for a short walk through it: seven stops, a real
   Apply and an Undo, all on the sample." Then "Your own setup: `uvx kitden`."
3. `## Three questions, one page`, with three sections:
   - `### What does each agent load, and from where?` — the Library as a map and a List, All
     projects and the tag "This project", Details beside the page; picture `tour` (alt: "The
     Library map with code-review selected: Codex and Cursor light up, and its Details sit beside
     the map, with the tour box at the Shared skill stop").
   - `### What differs between my agents in a project?` — Differences, the tag "This project",
     Needs review, Add missing in four groups; picture `library` (alt: "Library List in atlas
     showing only the rows where the clients differ").
   - `### Which tools go through the gateway, and which go around it?` — the Gateway as a map and
     a List, "Outside the gateway" with its amber lines, tools per project with their origin,
     strict mode, "a tool you turn off is refused at once"; picture `gateway` (alt: "Gateway map
     in atlas/web: write_file selected, off by the rule of its parent folder atlas, and Cursor's
     amber line around the gateway").
4. `## Simple, fast and local` — three bold lines: **Simple and visual.** every change opens a
   review (what, which clients and projects), Apply keeps a backup and checks it, Undo puts it
   back; picture `review` (alt: "The Add missing review for atlas: what each client lacks, with
   checkboxes, before Apply"). **Fast to open.** the measured numbers from `docs/development.md`.
   **Local and safe.** `127.0.0.1`, no account, no telemetry, the secrets sentence, the write
   boundary sentence.
5. `## Let your agents ask` (as today, its pinned sentence kept).
6. `## Install` (as today, with Part 1's demo line), `## How it works` (the SVG and three steps),
   `## Learn more`: the guide
   (`https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/guide.md`), design,
   development, release notes, roadmap, license.

Builder call: the README keeps the promises (local, secrets, the agents server, the write
boundary, Unknown is not missing, the demo); the how-to sentences live in the guide, and their
pins read the guide. No pinned sentence is dropped.

- [ ] **Step 1: Write the failing tests**

```python
IMAGES = "https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/"


def test_readme_answers_the_three_questions_and_points_to_the_tour():
    readme = (ROOT / "README.md").read_text()
    for heading in (
        "### What does each agent load, and from where?",
        "### What differs between my agents in a project?",
        "### Which tools go through the gateway, and which go around it?",
        "## Simple, fast and local",
    ):
        assert heading in readme, heading
    assert "uvx kitden demo" in readme and "Press **Tour**" in readme
    assert "https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/guide.md" in readme
    assert len(readme.splitlines()) < 160


def test_readme_pictures_come_in_both_themes():
    readme = (ROOT / "README.md").read_text()
    light = re.findall(rf'<img src="{re.escape(IMAGES)}([\w-]+)\.jpg"', readme)
    dark = re.findall(rf'srcset="{re.escape(IMAGES)}([\w-]+)-dark\.jpg"', readme)
    assert light == dark == ["overview", "tour", "library", "gateway", "review"]
```

  Retarget `test_readme_names_the_management_actions` (rename
  `test_the_guide_names_the_management_actions`) and `test_readme_says_what_an_unknown_folder_gets`
  (rename `test_the_guide_says_what_an_unknown_folder_gets`) to read `docs/guide.md`; the
  `docs/development.md` half stays. Any other README pin from Parts 1–7 whose sentence moved
  to the guide moves the same way; a pin whose sentence stays keeps reading the README.
- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_docs_words.py
  tests/unit/test_release_files.py -v`.
- [ ] **Step 3: Rewrite `README.md`** as the outline says.
- [ ] **Step 4: Run** the same command → PASS, then all checks.
- [ ] **Step 5: Commit**

```bash
git add README.md tests/unit/test_docs_words.py
git commit -m "README: three questions, pictures from the demo, and the tour"
```

---

### Task 8: Release notes for 0.3.0 (8.5)

**Files:**
- Create: `docs/releases/v0.3.0.md`
- Test: `tests/unit/test_docs_words.py`

**Interfaces:**
- Consumes: `ROADMAP.md` "### Not released yet"; `git log --oneline v0.2.0..HEAD`; the earlier
  design `docs/superpowers/specs/2026-10-21-review-follow-up-design.md` Parts 1–6 (5.3 OAuth did
  not ship; Part 7 Linux and Windows moved to Later); the 2026-10-22 spec's Parts 1–3, 7 and 8,
  the map spec's Parts 4–6 (the Gateway, Library, Instructions, Overview and Changes pages), and
  each part's report.

The format of `docs/releases/v0.2.0.md`: one opening paragraph that starts "Kitden 0.3.0", then
`## New`, `## Better`, `## Fixed`, each a list of **bold lead.** plus one or two plain
sentences, for users, no internal names or part numbers. New holds at least:
- `kitden demo` and its Tour;
- the Gateway as a map and a List (clients, the Kitden gateway, servers, tools), with the search
  that finds on the page, and dragging a server in from "Outside the gateway" to see its preview
  first;
- tools per project, strict mode, reads and writes, call counts, and "Turn off in one project…"
  in a tool's Details;
- the Library as a map and a List by source, with what each plugin holds, Differences and the tag
  "This project";
- Add missing in four groups; adding plugins, skills and gateway servers from the marketplaces on
  this computer, previewed on the map; turning a skill or plugin off for all projects or in one
  project where the client has a switch; removing and putting back items;
- secrets in the Keychain;
- the Instructions tab as a tree with Claude Code's `@` imports, and tool counts;
- Overview with one card per item and "Your setup"; the Changes timeline with Details and "See
  it on the map".

Better holds the start numbers, versions in the background, All projects and the words "On",
"This project" and "Only this project", Unknown and Needs review, Details beside the page and in
five parts, reviews that lead with the outcome, the project menu with each project's own rules,
the write boundary, the README and guide. Fixed holds Part 7's fixes, the reads that were wrong
(Claude Code's local settings and skill overrides, what an installed plugin holds) and the fixes
in the log.

- [ ] **Step 1: Write the failing test**

```python
def test_the_notes_for_0_3_0_are_ready():
    notes = (ROOT / "docs/releases/v0.3.0.md").read_text()
    assert notes.startswith("Kitden 0.3.0 ")
    assert [line for line in notes.splitlines() if line.startswith("## ")] == [
        "## New", "## Better", "## Fixed"]
    for words in ("kitden demo", "Tour", "map", "List", "Differences", "Add missing",
                  "Kitden gateway", "Strict", "Keychain", "Instructions", "Your setup",
                  "This project", "See it on the map", "All projects", "Undo"):
        assert words in notes, words
    assert "DEMO_SECRET" not in notes and "SENTINEL" not in notes and "Part " not in notes
```

- [ ] **Step 2: Run it to see it fail**: `uv run pytest tests/unit/test_docs_words.py -v`.
- [ ] **Step 3: Write the notes.** Do not change the version anywhere, do not tag, do not rename
  ROADMAP's "Not released yet": those are the owner's release steps (`docs/development.md`,
  Release).
- [ ] **Step 4: Run it to see it pass**, then all checks (`test_the_version_is_the_same_everywhere`
  still sees 0.2.0).
- [ ] **Step 5: Commit**

```bash
git add docs/releases/v0.3.0.md tests/unit/test_docs_words.py
git commit -m "Release notes for 0.3.0, ready for the owner"
```

---

### Task 9: Docs and roadmap for Part 8 (8.6)

**Files:**
- Modify: `docs/development.md` ("Check before a release": a demo walk), `docs/design.md` (only if
  a word below is missing), `tests/unit/test_docs_words.py`
- `ROADMAP.md` only by the rule in Step 4.

**Interfaces:**
- Consumes: Part 6's `docs/research/walkthrough-script-2.md` (the seven tasks on the new pages,
  the same seven as Part 1's script 1); the design words Parts 2 and 4–6 wrote.

- [ ] **Step 1: Write the failing tests**

```python
def test_design_names_the_map_the_origin_words_the_states_and_the_tour():
    design = (ROOT / "docs/design.md").read_text()
    for words in ("Map | List", "This project", "Only this project", "Unknown", "Needs review",
                  "On by default", "New · waits", "Outside the gateway", "Differences",
                  "Your setup", "### Tour", "Tour light"):
        assert words in design, words


def test_the_release_check_walks_the_demo():
    text = (ROOT / "docs/development.md").read_text()
    assert "Before every release, walk the demo" in text
    assert "uv run kitden demo --size medium" in text and "Take the tour to its end" in text
```

- [ ] **Step 2: Run them to see them fail**: `uv run pytest tests/unit/test_docs_words.py -v`.
- [ ] **Step 3: Write the docs.**
  - `docs/development.md`, "Check before a release", a last subsection: "Before every release,
    walk the demo (about 15 minutes, no real client):" then numbered steps continuing the list:
    run `uv run kitden demo --size medium`; "Take the tour to its end": press Add missing plugins
    and skills… and Apply at its stop, then Undo at the last stop; then the seven tasks of
    walkthrough script 2, one line
    each (why Codex and Cursor both have `code-review`; what differs in `atlas`; add the missing
    skill to `atlas` only; the two `docs` servers; turn off `read_file` of `files` for `atlas`; why
    Cursor reaches `files` around the gateway; Undo); once by keyboard only, once in a window
    under 900 px, once in the dark theme. Anything that goes wrong is a bug before the release.
  - `docs/design.md`: add one line for each word the first test finds missing, in the section it
    belongs to ("Your setup" in the Overview paragraph; the tags and "Outside the gateway" in the
    Gateway tables; "Differences" and the states in the Library table). Change nothing that is
    there.
- [ ] **Step 4: Roadmap.** Run `git status --short ROADMAP.md`. While it shows `M` from the
  owner's edit, do not touch it; put these lines in the part's report. Once the owner has
  committed it, add them under "### Not released yet" and move Part 8's line out of "## Planned":
  - **Try it with a tour:** in `kitden demo`, Tour walks seven stops: Your setup, a shared skill
    on the Library map, a project override, Differences, Add missing with a real Apply, the
    Gateway map's routes and rules, and Undo.
  - **Docs you can follow:** the README answers three questions with pictures from the sample; a
    guide of "I want to…" tasks, each with a small diagram and its tour stop; notes for 0.3.0.
- [ ] **Step 5: Run all checks**: `uv run pytest -q && uv run ruff check . && uv run ruff format
  --check src tests && node --test tests/frontend/*.test.mjs` → PASS.
- [ ] **Step 6: Commit**

```bash
git add docs/development.md docs/design.md tests/unit/test_docs_words.py
git commit -m "Docs: a demo walk before every release"
```

(Add `ROADMAP.md` only when Step 4 edited it; leave `docs/design.md` out if it did not change.)

---

## Self-review

- **Spec coverage.** 8.1 the tour: stops and words (Task 1), places on the demo and the real Apply
  (Task 2), box, light, keys, focus, reduced motion, both themes, no fetch (Task 3), button only
  in demo, `tour.js` loaded only then (Task 4). 8.2 README (Task 7). 8.3 guide (Task 6). 8.4
  recipe and pictures (Task 5). 8.5 notes (Task 8). 8.6 design.md: the tour (Tasks 3, 4), the
  map, origin words and states checked and filled (Task 9); development.md demo walk (Task 9).
  Done: the stops' places on the demo app (Task 2), docs words (Tasks 5–9), notes file (Task 8).
- **Map pages.** Each stop's address carries the new hash fields (`view=map|list`, `show=diff`,
  `sel=tool:…`) and its anchor is a block, a box or a button that Parts 4–6 draw (Task 2),
  including the tag "This project" that Part 4 gives the outside `docs` block in `atlas`.
- **Names.** `data-tour="<stop id>"` equals each `STOPS[i].id`; `startTour`, `tourButton`,
  `STOPS`, `NOT_FIT`, `FIND_MS` are the same in every task. Consumed names keep their parts'
  spelling (`hashFor`, `parseSel`, `view=map|list`, `show=diff`, `sel=tool:…`, `will_add`,
  `origin_from`, `data-focus="block:<id>"`, `data-focus="add:missing"`, `/api/overview`,
  `/api/about`, `demoTag`, `_demo_run`, `demo_page`).
- **Not here.** The map pages, origin words and states themselves (Parts 2 and 4–6 write their
  design.md lines with their page changes); the version bump and tag (the owner).
