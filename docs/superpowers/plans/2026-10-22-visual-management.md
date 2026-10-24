# Visual management: master plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One connected picture of the setup: shared context, true states, Details in five
questions; then the owner's map pages, with a tree and a List view on Gateway and Library,
attention cards and a small tree on Overview, and a Changes timeline; then the deferred
findings; then documentation a person can try (`kitden demo` with a tour).

**Architecture:** Eight parts. Each has its own plan file, tasks, tests and commits, and ships on
its own branch. Part 1 builds the sample setups and a safe demo mode, which every later part tests
on. This file fixes the order, the rules every part follows, and the names that cross part
boundaries.

**Tech Stack:** Python 3.13, Starlette, the official MCP SDK 2.3, tomlkit and watchfiles; plain
ES modules and one CSS file; pytest (with hypothesis and syrupy); and node's test runner for the
page's pure functions. No new runtime dependency.

**Specs:**

- Parts 1–3, 7 and 8: `docs/superpowers/specs/2026-10-22-visual-management-design.md`, cited as
  "spec N.M". It is built on `docs/research/visual-management-ux-concept-2026-10-22.md`, cited as
  "concept §N".
- Parts 4–6: `docs/superpowers/specs/2026-10-23-map-pages-design.md`, cited as "map spec S.N" or
  "map spec N.M". It is built on the owner's final design,
  `docs/research/visual-redesign-final-2026-10-23.md`, with its frames in `design/kitden.pen`.

The map spec replaces Parts 4–6 of the 2026-10-22 spec. Their old plans are in git at `d8c05cc`.

## Order

| Part | Plan file | Branch | Tasks | Ships |
| --- | --- | --- | --- | --- |
| 1 Sample setups and demo mode | `2026-10-22-visual-part1-demo.md` | `visual-part1-demo` | 9 | Done (merged). |
| — Walkthrough 1 | — | — | — | Done: `docs/research/walkthrough-2026-10-23.md` |
| 2 Shared words, scope and selection | `2026-10-22-visual-part2-words-scope.md` | `visual-part2-words` | 11 | Done (merged). |
| 3 One Details panel, one change flow | `2026-10-22-visual-part3-details.md` | `visual-part3-details` | 9 | Done (merged). |
| 4 The Gateway map and list | `2026-10-23-map-part4-gateway.md` | `map-part4-gateway` | see plan | The probe and its numbers; the words "On", "This project" and "Only this project"; the tokens; Details beside the page; the map core; Map or List; find; the project picker; Apply on the map; the Gateway list, Details and map; drag a server in. |
| 5 The Library map, list and marketplace adds | `2026-10-23-map-part5-library.md` | `map-part5-library` | see plan | Read fixes; two tabs; the Library tree and List with Differences and Add missing in four groups; skill and plugin switches; the add panel for plugins, skills and gateway servers (`gateway.add`). |
| 6 Instructions, Overview and Changes | `2026-10-23-map-part6-overview.md` | `map-part6-overview` | see plan | The Instructions tree with imports; Overview cards and "Your setup"; the Changes timeline; the walkthrough 2 script. |
| — Walkthrough 2 (owner, optional) | — | — | — | A results file; its fixes feed Part 7. |
| 7 Leftovers | `2026-10-22-visual-part7-leftovers.md` | `visual-part7-leftovers` | 10 | Walkthrough fixes, then the deferred findings of Parts 1–6. |
| 8 Documentation you can try | `2026-10-22-visual-part8-docs-tour.md` | `visual-part8-docs` | 9 | The tour, README, guide, pictures and their recipe, and the v0.3.0 notes. |

Run the parts in this order. Each branch starts from `main` after the previous part is merged. A
walkthrough the owner skips is recorded as "skipped" in the next part's ledger, and the spec's
words stand.

## Rules every part follows

- **`AGENTS.md` in full.**
  - Code, comments, UI text and docs are in simple English, short and plain.
  - Every change to a client's settings goes through preview → Apply with a backup → verify →
    Undo, in `src/kitden/changes/engine.py`, and never any other way.
  - Main pages show a name, the client, a state and an action. Paths, addresses and commands stay
    in Details.
- **`docs/design.md`** says how the page looks and moves.
  - A part that changes the page updates design.md in the same commit. This wins over any "docs
    last" line in a part plan; that docs task then only reads design.md through once.
  - New page text is pinned in `tests/unit/test_page_words.py`. A changed word changes its pin in
    the same commit.
  - Page helper logic is a pure function, exported from a module under
    `src/kitden/web/static/js/` and tested with `node --test tests/frontend/*.test.mjs`.
- **Tests use sandbox homes only.**
  - Build them with `make_home(...)` and `write_cursor_fixture_state(home)` from
    `tests/conftest.py`, or with `build_demo_home(root, size)` (below).
  - A test that needs a sample case uses the item Part 1 names for it (Part 1, Task 1, "Sample
    contract"). A case Part 1 does not build is added to the sample and to its contract test.
  - The conftest guards that refuse real `claude`, `codex`, `cursor` and `security` stay on.
  - Every fake secret is a `SENTINEL_SECRET_*` string (tests) or a `DEMO_SECRET_*` string
    (samples). `tests/security/test_no_secrets.py` fails if either shows on a page, in an API
    answer, in a log, or in an MCP tool answer.
- **Before each commit,** run `uv run pytest -q`, `uv run ruff check .`,
  `uv run ruff format --check src tests` and `node --test tests/frontend/*.test.mjs`. All of them
  pass, or the commit waits.
- **Commits.**
  - Stage files by name. Never `git add -A`, `git add .` or `git commit -a`.
  - Messages have a short plain subject and one to three simple lines, with no prefix such as
    `feat:`. They end with the co-author line the session gives.
- **`ROADMAP.md`.** The owner has an uncommitted edit there. While `git status` shows `ROADMAP.md`
  modified and not by this part, no task edits or stages it; the part's last task writes the
  roadmap lines into its report instead. Once the owner has committed it, the part's last task
  moves its line from "## Planned" to "### Not released yet", as AGENTS.md says.
- **The owner's files.** No task edits or stages `design/`,
  `docs/research/visual-redesign-final-2026-10-23.md` or
  `docs/research/visual-management-ux-concept-2026-10-22.md`.
- **Facts about other tools.** A client's file format, a CLI flag or an MCP rule is checked against
  that tool's current docs before it is relied on, with the check date next to the claim
  (`checked 2026-10-23`). If it cannot be checked, the comment says "not checked" and the report
  names it.
- **Line numbers** in plans and surveys are hints. Find code by name.
- **No real client command, real MCP server, real Keychain or network** in any test or demo run.
- **The read-only MCP server.** `explain()` and `project_views()` feed it too. A part that changes
  their output runs `tests/unit/test_mcp_server.py` and keeps file lines and imports out of agent
  answers.

## Names that cross part boundaries

A part that defines a name below uses it exactly, and a part that uses one does not rename it.

| Name | Defined in | Used in | What it is |
| --- | --- | --- | --- |
| `kitden.demo.build_demo_home(root: Path, size: str) -> Path` | 1 | 1–8, tests, `scripts/measure-start.py` | Writes a synthetic home under `root` and returns the home path. `size` is one of `SIZES`. The medium sample's named cases are Part 1's "Sample contract". |
| `kitden.demo.SIZES = ("small", "medium", "large")` | 1 | 1, 8 | The three sample sizes. |
| `DEMO_SECRET_` | 1 | 1, security tests | The prefix of every fake secret in a sample. |
| `create_app(..., demo: bool = False)` | 1 | 1, 4–6, 8 | Demo mode: a demo runner, no server start, no Keychain, no network. |
| Test helpers `demo_page(root, size="medium")` and `demo_build` in `tests/unit/test_demo_mode.py` | 1 | 1, 4–6, 8 | A demo app on a fresh sample. |
| `GET /api/about` → `{"version": str, "demo": bool}` | 1 | 1, 8 | Tells the page it runs a demo. |
| `writable_roots(home: Path, inventory) -> list[Path]`; the refusal "Kitden writes only in your home folder and your known projects." | 1 | 1, 2, 5 | The engine's write boundary. |
| `ALL_PROJECTS = "All projects"` (in `parts.js`) | 2 | 2, 4–6 | The picker's empty choice and the scope phrase. |
| `Cell.origin: str \| None` in `views/load_map.py`: `None`, `"project"` or `"override"` | 2 | 2, 5 | Where a cell's item comes from. From Part 4 on, `"override"` shows as the tag "This project", and `"project"` puts the item under "Only this project" (map spec S.1). |
| `Cell.route: str \| None`, with its words in `ROUTE_WORDS` | 2 | 2, 3, 5 | How a client gets an item. It goes in the hover text and Details, except the "via" state's own word, "Via Claude Code" (map spec S.1). |
| `Cell.state`: `"on"`, `"off"`, `"gw"`, `"via"`, `"unk"`, `"none"`, `"missing"` or `"review"` | 2 | 2, 4–6 | `"review"` means Needs review. |
| `STATE_WORDS`, in `parts.js` and in `views/words.py` | 2 | 2, 4–7 | The one table of state words per language. From Part 4, `"on"` is "On" (owner, 2026-10-23). |
| `ORIGIN_WORDS` (`views/words.py`; Part 4 adds its twin in `parts.js`) | 2, 4 | 4, 5 | From Part 4: `"override"` → "This project", `"project"` → "Only this project". Changed in one commit with both pins. |
| `kitden.views.match`: `source_keys(item)`, `catalog_keys(skill)`, `odd_ones(keys)` | 2 | 2, 5 | One test of "same item, same source". |
| `FindingType.SAME_NAME_OTHER_SOURCE`; `Finding.clients` | 2 | 2, 6, MCP server | A same name from another source is its own note, and every note names its clients. |
| `Item.stale_at: str \| None` | 2 | 2, 5 | The time of the last good read, when an item is kept from it. |
| Hash `sel=<kind>:<name>`; `parseSel`, `selFor`, `goTo(view, selected)`, `takeArrival()` in `store.js` | 2 | 2–8 | Selection in the address. Part 4 adds the kinds `tool` (`sel=tool:<server>/<tool>`, split at the first "/"), `client` (a client block; lights `litFrom`) and `group` (opens and focuses a List group; the map's "N more" opens List with it). |
| `/api/explain` → `{definitions, inherits}`; `definitions[i].affects` | 3 | 3–6, 8 | The Affects line. |
| `contextLinks(row, definitions, view)` and `followLink(link)` in `details.js` | 3 | 4–6 | Context links in Details. Part 6's "See it on the map" goes through `changePlace` and `followLink`. |
| `panel.js` (the shell and re-exports), `details.js`, `tools.js`, `review.js` | 3 | 3–8 | Later parts import a name from the module that defines it. |
| `PLACE_IN_TITLE` (in `parts.js`), `changeWords` and `reviewLede(change, picked)` (in `review.js`) | 3 | 4, 5 | Reviews name their scope in the title. |
| CSS tokens `--dim`, `--preview-fill`, `--preview-line` | 4 | 4–6 | Map spec S.2. |
| `openPanel(content, { instant, dock })` and `DOCK_MIN = 1024` in `panel.js` | 4 | 4–6 | Details beside the page (map spec S.3). With `dock`, at `DOCK_MIN` px and wider, there is no scrim and no `aria-modal`. |
| `factsBlock(rows: {label, value, accent?}[])` in `details.js` | 4 | 4–6 | The Facts block of Details. |
| `detailsCard` actions: `{label, run?, body?, primary?}`, an optional `more: [...]` group and an optional `after` node | 4 | 4–6 | One shape for Details actions. |
| `projectChoice(projects, picked, onPick)` in `details.js` | 4 | 4, 5 | The scope choice inside a Details column (walkthrough F10). |
| `switchProject(id)` in `store.js`; `goTo(view, selected, { project })` calls it | 4 | 4, 6 | Switches the project and reloads its data, from the picker or a link. |
| `map.js`: `layoutTree(model, { open, width, narrow }) -> { blocks, links, height }` (pure; block sizes per column; one narrow rule for every page), `litPath(model, id) -> Set<string>` (paths to a block, through `on`, `direct` and `faint` links), `litFrom(model, id) -> Set<string>` (what a block reaches), `findIn(model, text) -> { matches: Set<string>, open: Set<string> }`, `findChip`, `dropAt`, and `drawMap(box, model, layout, { onSelect, onAdd })` | 4 | 4–6 | The map core (map spec S.4). A caption with Details is a button; `onAdd(columnId)` is a column's "+ Add". |
| Tree model `{ columns: [{id, caption, add}], blocks: [{id, column, parent, kind, name, meta, state, tag, count, grip}], links: [{from, to, kind}] }`. Block `state` is `"on"`, `"off"`, `"unk"` or `"preview"`; `tag` is `"This project"`, `"Only this project"` or null; link `kind` is `"on"`, `"faint"`, `"direct"` or `"preview"`. | 4 | 4–6 | The one model every map page builds. |
| `cutName(name, max = 24)` in `dom.js` | 4 | 4–6 | Long names end in "…". |
| Hash `view=map\|list`; `MAP_AT = 15`; `viewMode(state, count) -> "map" \| "list"` in `store.js` | 4 | 4, 5 | Map or List (map spec S.5). |
| `projectMenu(projects, picked, onPick)` and `scopeText(folder, count)` in `parts.js`; `/api/projects` items gain `own_rules: int` | 4 | 4–6 | The project picker (P1) and the scope bar. `own_rules` counts only rules that differ from what the project would otherwise follow. Part 4 counts gateway rules; Part 5 adds the Library's. |
| `reviewBar(change, { onApply, onCancel, onShow, body })` in `map-review.js` | 4 | 4, 5 | The review bar on the map (map spec S.8). |
| `gateway_view` outside rows gain `override: bool` (the project's own definition replaces the shared one) | 4 | 4, 8 | The "This project" tag on an outside block. |
| `held_servers()` rows gain `tool_list: [{name, title, state, effective, why, hint, origin, origin_from}]` and `on_count: int`; `tools_view` rows gain `effective` and `why` too | 4 | 4, 6 | Map spec 4.2. `state` is the rule's own state; `effective` adds the server's switch, with `why: "server_off"`. The map and List draw from `effective`. `origin` is `"global"`, `"project"`, `"parent"`, `"default"` or `"strict"`. |
| Part 4 page helpers that Parts 5 and 6 reuse: `docksAt`, `detailsCard` (details/panel); `toggleOpen`, `unfoldDelays`, `isNarrow` (`map.js`); `gridKey` (List keys); `menuItems` (picker); Apply on the map: `mapPreview`, `previewOnMap`, `applyOnMap`, `cancelOnMap`, `showMapReview`, `barWords`, `previewBar(redraw)`, `redrawPreview(redraw, { same, ended })` (`map-review.js`), `appliedToast` (`review.js`), `moveBody` (`details.js`); `gatewayTree(…, { preview: {name, kind} })` (`gateway.js`), `dropBody` (`gateway-drag.js`); `MAP_PAGES` in `app.js` | 4 | 5, 6 | Signatures are in the Part 4 plan's Interfaces. The map review and the drag left `review.js` and `gateway.js` for `map-review.js` and `gateway-drag.js` (Part 4, Task 12); `map-review.js` reads no Gateway module. Part 5 adds `"library"` to `MAP_PAGES`. |
| Library hash `show=diff` | 5 | 5, 8 | The Differences filter. |
| Align answer groups `will_add`, `already`, `decide` and `cannot` | 5 | 5 (also the Gateway's "Add missing servers…"), 7, 8 | Add missing in four groups. |
| `gateway.add` action; `GET /api/market-servers?q=` → `{servers: [{id, name, plugin, marketplace, kind, held, refusal}]}` | 5 | 5, 8 | Map spec 5.6. |
| `views/imports.py`: `imports(path, home, project, hops=4) -> list[Import]` | 6 | 6 | Claude Code's `@path` imports (map spec 6.1), for the page only. |
| `changePlace(entry) -> {view, selected, project} \| null` in `changes.js`; `goTo(view, selected, { project })` | 6 | 6, 8 | "See it on the map", opened in the change's project. |
| `data-tour="<stop id>"` attributes | 8 | 8 | Tour anchors. |

## Review Focus (whole project)

These are the inputs most likely to bite a person. Each is pinned by a test in the part that owns
the code.

1. **A known project on another disk** (outside home): adds into it still preview and apply.
   Parts 1, 2, 5.
2. **A settings file that breaks while the page runs:** its items stay, marked as from the last
   good read, and no "+ Add" or grip appears for them. Parts 2, 4, 5.
3. **The large sample:** List opens first; the map layout stays within its time; and long names
   are cut with "…" and never overflow. Parts 4, 5.
4. **Keyboard only, a narrow window, reduced motion, both themes:** every block and row is
   reachable, a drag has a keyboard path, tools unfold down under 1024 px, and nothing moves while
   idle. Parts 4–6, 8.
5. **Two same-name items from different sources:** they are never shown as equal, never added
   over each other, and never counted as a duplicate unless the findings say so. Parts 2, 5.

## Walkthrough 1 rulings

The results are in `docs/research/walkthrough-2026-10-23.md`. Parts 2 and 3 built their rulings.
For Parts 4–6 these stand:

- The tools Details has its own scope choice, starting from the picked project, and a tool
  review's title starts with the scope (F10). Map spec 4.4.
- Add missing follows the page: "Add missing plugins and skills…" in the Library and "Add missing
  servers…" on the Gateway (F4). Map spec 5.4.
- The page shows what the gateway already holds for each client before it offers a move (F9).
  Map spec 4.5.
- The owner later replaced "Available" with "On", and moved "where it applies" from the cell to
  the tags and groups (2026-10-23). Map spec S.1.

## Walkthroughs

Part 1 wrote walkthrough script 1. Part 6's last task writes `docs/research/walkthrough-script-2.md`:
the seven tasks of concept §12 on the new pages, as plain steps for `kitden demo --size medium`,
with a table to fill in (task, done, wrong turns, time, what was confusing). The owner runs it.
The controller writes the results file and turns each finding into a ruling for Part 7.
