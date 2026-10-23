# Visual management: master plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One connected picture of the setup (shared context, true states, Details in five
questions, Compare with differences, Access with origins and routes, a setup map), then the
deferred findings of Parts 1–6, then documentation a person can try (`kitden demo` with a tour).

**Architecture:** Eight parts, each its own plan file with its own tasks, tests and commits, each
shipping on its own branch. Part 1 builds the sample setups and a safe demo mode that every
later part tests on. This file fixes the order, the rules every part follows, and the names
that cross part boundaries.

**Tech Stack:** Python 3.13, Starlette, the official MCP SDK 2.3, tomlkit, watchfiles; plain ES
modules and one CSS file; pytest (hypothesis, syrupy); node's test runner for the page's pure
functions. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-10-22-visual-management-design.md` (cited as "spec N.M"),
built on `docs/research/visual-management-ux-concept-2026-10-22.md` ("concept §N").

## Order

| Part | Plan file | Branch | Tasks | Ships |
| --- | --- | --- | --- | --- |
| 1 Sample setups and demo mode | `2026-10-22-visual-part1-demo.md` | `visual-part1-demo` | 9 | `kitden demo` on three sample sizes; write boundary; walkthrough 1 script |
| — Walkthrough 1 (owner, optional) | — | — | — | `docs/research/walkthrough-<date>.md`; settles the open words |
| 2 Shared words, scope and selection | `2026-10-22-visual-part2-words-scope.md` | `visual-part2-words` | 9 | All projects; origin label; Unknown, Needs review, last good read; scope before the click; selection in the address |
| 3 One Details panel, one change flow | `2026-10-22-visual-part3-details.md` | `visual-part3-details` | 9 | `panel.js` split; Details in five questions; Affects; context links; review outcome first; Cancel back; stale review; empty states |
| 4 Compare | `2026-10-22-visual-part4-compare.md` | `visual-part4-compare` | 8 | Differences filter; project exceptions and "a project keeps its own"; Add missing in four groups |
| 5 Access | `2026-10-22-visual-part5-access.md` | `visual-part5-access` | 8 | routes with Direct; server clients; tool origin; honest reviews; sessions line; removed-project rules; call counts |
| 6 Setup map | `2026-10-22-visual-part6-map.md` | `visual-part6-map` | 6 | `/api/setup-map`; the map on Overview; narrow list; walkthrough 2 script |
| — Walkthrough 2 (owner, optional) | — | — | — | results file; fixes feed Part 7 |
| 7 Leftovers | `2026-10-22-visual-part7-leftovers.md` | `visual-part7-leftovers` | 10 | walkthrough fixes, then the deferred findings of Parts 1–6 |
| 8 Documentation you can try | `2026-10-22-visual-part8-docs-tour.md` | `visual-part8-docs` | 9 | the tour; README; guide; pictures and their recipe; v0.3.0 notes |

Run the parts in this order; each branch starts from `main` after the previous part is merged.
A walkthrough the owner skips is recorded as "skipped" in the next part's ledger, and the
spec's default words stand.

## Rules every part follows

- `AGENTS.md` in full. Code, comments, UI text and docs in simple English, short and plain.
  Every change of a client's settings goes through preview → Apply with a backup → verify → Undo,
  through `src/kitden/changes/engine.py`, and never any other way. Main pages show a name, the
  client, a state and an action; paths, addresses and commands stay in Details.
- `docs/design.md` for how the page looks and moves. A part that changes the page updates
  design.md in the same commit as the change; this wins over any "docs last" line in a part plan,
  whose docs task then only reads design.md through once. New page text is pinned in
  `tests/unit/test_page_words.py`; a changed word changes its pin in the same commit. Page helper
  logic is a pure function exported from a module under `src/kitden/web/static/js/` and tested
  with `node --test tests/frontend/*.test.mjs`.
- Tests use sandbox homes only: `make_home(...)` and `write_cursor_fixture_state(home)` from
  `tests/conftest.py`, or, from Part 1 on, `build_demo_home(root, size)` (below). A test that
  needs a sample case uses the item Part 1 names for it (Part 1, Task 1, "Sample contract"); a
  case Part 1 does not build is added to Part 1's sample and its contract test. The conftest
  guards that refuse real `claude`, `codex`, `cursor` and `security` stay on. Every fake secret is
  a `SENTINEL_SECRET_*` (tests) or `DEMO_SECRET_*` (samples) string; `tests/security/test_no_secrets.py`
  fails if either shows on a page, in an API answer, in a log, or in an MCP tool answer.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`,
  `node --test tests/frontend/*.test.mjs`. All pass or the commit waits.
- Commits: stage files by name. Never `git add -A`, `git add .` or `git commit -a`. Messages: a
  short plain subject, one to three simple lines, no prefix such as `feat:`, ending with the
  co-author line the session gives.
- `ROADMAP.md`: the owner has an uncommitted edit there. While `git status` shows `ROADMAP.md`
  modified and not by this part, no task edits or stages it; the part's last task writes the
  roadmap lines into its report instead. Once the owner has committed it, the part's last task
  moves its line from "## Planned" to "### Not released yet" as AGENTS.md says.
- A fact about another tool (a client's file format, a CLI flag, an MCP rule) is checked against
  that tool's current docs before it is relied on, with the check date next to the claim
  (`checked 2026-10-22`). If it cannot be checked, the comment says "not checked" and the report
  names it.
- Line numbers in plans and surveys are hints; find code by name.
- No real client command, real MCP server, real Keychain or network in any test or demo run.
- `explain()` and `project_views()` feed the read-only MCP server too: a part that changes their
  output runs `tests/unit/test_mcp_server.py` and keeps file lines out of agent answers.

## Names that cross part boundaries

A part that defines a name below uses it exactly; a part that uses one does not rename it.

| Name | Defined in | Used in | What it is |
| --- | --- | --- | --- |
| `kitden.demo.build_demo_home(root: Path, size: str) -> Path` | 1 | 1–8, tests, `scripts/measure-start.py` | writes a synthetic home under `root`, returns the home path; `size` in `SIZES`; the medium sample's named cases are Part 1's "Sample contract" |
| `kitden.demo.SIZES = ("small", "medium", "large")` | 1 | 1, 8 | the three sample sizes (spec 1.1) |
| `DEMO_SECRET_` | 1 | 1, security tests | prefix of every fake secret in a sample |
| `create_app(..., demo: bool = False)` | 1 | 1, 4, 6, 8 | demo mode: demo runner, no server start, no Keychain, no network |
| test helper `demo_page(root, size="medium")` and `POST` in `tests/unit/test_demo_mode.py` | 1 | 1, 8 | a demo app on a fresh sample (Part 4's `served(home)` serves a sample a test changed first) |
| `GET /api/about` → `{"version": str, "demo": bool}` | 1 | 1, 8 | lets the page know it runs a demo |
| `kitden demo [--size small\|medium\|large]` | 1 | 3, 8, README | CLI command |
| `writable_roots(home: Path, inventory) -> list[Path]` and the refusal "Kitden writes only in your home folder and your known projects." | 1 | 1, 2 | the engine's write boundary (spec 1.3) |
| `ALL_PROJECTS = "All projects"` (JS `parts.js`) | 2 | 2, 5 | the picker's empty choice and the scope phrase |
| `Cell.origin: str \| None` in `views/load_map.py`, values `None`, `"project"`, `"override"` | 2 | 2, 8 | spec 2.2 |
| `Cell.state` values `"on" "off" "gw" "unk" "none" "missing" "review"` | 2 (adds `"review"`) | 2, 4, 6 | `"review"` = Needs review (spec 2.3) |
| `STATE_WORDS` (JS `parts.js`, exists) and `STATE_WORDS` (Python, new `views/words.py`, taking over `views/after.py WORDS`) | 2 | 2, 6, 7 | the one table of state words per language, so a rename is one change each |
| `Item.stale_at: str \| None` | 2 | 2, 6 | ISO time of the last good read when an item is kept from it (spec 2.3) |
| hash parameter `sel=<kind>:<name>`; JS `parseSel(text) -> {kind, name} \| null`, `selFor(selected) -> string` in `store.js` | 2 | 2–8 | selection in the address (spec 2.5) |
| `goTo(view: string, selected: {kind, name} \| null)` in `store.js` (not `app.js`: it runs `start()` on import) | 2 | 3, 4, 6 | open a place with project and selection kept (Part 8's tour writes the address instead) |
| `ADDS`, `addScope(action, into)`, `reviewLede(action, picked)` | 2 (in `panel.js`; `review.js` after Part 3) | 3 | Part 3 widens `reviewLede` to `reviewLede(change, picked)` |
| `/api/explain` answer `{definitions, inherits}`; `definitions[i].affects: {clients: string[], scope: "all" \| "project", note: str \| None}` (per definition Kitden can change; the page picks the lead) | 3 | 3, 8 | the Affects line (spec 3.1) |
| `contextLinks(row, definitions, view)` in `details.js` | 3 | 6, 7 | Part 6 adds "Show on the map" last; Part 7 leaves it out when it hides the map |
| `PLACE_IN_TITLE` in `review.js`: actions whose title names its place, so `changeWords` adds no scope words | 3 | 4, 5 | Part 5 adds `gateway.forget` |
| Library hash `show=diff` | 4 | 4, 8 | the Differences filter (spec 4.1) |
| align answer groups `will_add`, `already`, `decide`, `cannot` | 4 | 4, 7, 8 | Add missing's four groups (spec 4.3) |
| tool row fields `origin` in `"project" "parent" "global" "default" "strict"` and `origin_from: str \| None` | 5 | 5, 8 | spec 5.3 |
| `cutName(name, max = 24)` | 5 (`gateway.js`) | 6 | Part 6 moves it to `dom.js`; `gateway.js` exports it again |
| `GET /api/setup-map?project=` → `{project, sources, groups, items, clients, relations}`; relation `type` in `"defines" "contains" "available_to" "overrides" "routes_through"` | 6 | 6, 8 | spec 6.3 |
| `map.js`: `layoutMap(model, open) -> layout` (pure) and `renderMap(container, model)` | 6 | 6, 8 | spec 6.1–6.4 |
| local storage key `kitden.overview` = `"list"` \| `"map"`; `overviewMode()`, `setOverviewMode(mode)` in `store.js` | 6 | 6, 7, 8 | the remembered List / Map choice |
| `MAP_SWITCH` in `store.js` (only if walkthrough 2 hides the map) | 7 | 8 (`mapOffered()`) | spec 6.5 |
| `panel.js` split into `panel.js` (shell, re-exports), `details.js`, `tools.js`, `review.js` | 3 | 3–8 | later parts import a name from the module that defines it; a new node test goes in `tests/frontend/<that module>.test.mjs`, while existing tests in `panel.test.mjs` stay and import through the re-exports |
| `data-tour="<stop id>"` attributes | 8 | 8 | tour anchors; Part 8 adds them |

## Review Focus (whole project)

The inputs most likely to bite a person, each pinned by a test in the part that owns the code:

1. A known project on another disk (outside home): adds into it still preview and apply (Part 1
   write boundary test; Part 2 scope test).
2. A settings file that breaks while the page runs: its items stay, marked from the last good
   read, and no "+ Add" appears for them (Part 2).
3. The `large` sample: the Library, the map endpoint and the Gateway stay readable and within the
   time budgets; long names are cut with "…", never overflow (Parts 4, 5, 6).
4. Keyboard only, a narrow window, reduced motion, both themes: every new control is reachable,
   the map becomes a list under 900 px, nothing moves while idle (Parts 3, 5, 6, 8).
5. Two same-name items from different sources: never shown as equal, never added over each
   other, never counted as a duplicate unless the findings say so (Parts 2, 4, 6).

## Walkthrough 1 rulings (binding for Parts 2–5)

Results: `docs/research/walkthrough-2026-10-23.md`. The spec is updated (2.2, 2.2a, 2.3, 2.3a,
3.1, 4.3, 5.3a). Each part's preflight checks its plan against these and rules on the gaps; where
a part plan still says otherwise, these win.

- Part 2: cell words "Available" and "Off" (STATE_WORDS; "Has it" on Instructions also becomes
  "Available"); in a project view every cell carries its scope word ("all projects", "this
  project", "project override"); the route ("through Codex's folder", "from a plugin", "through the
  Kitden gateway") leaves the cell's word slot for the hover text and Details (F3, F5); a cell
  Kitden can fill always shows "+ Add", Details offers the same add, a project-only item adds into
  the project (F6); Overview notes: no "set up in more than one client" for different sources,
  every note row shows its clients, notes grouped by item (F7, F8).
- Part 3: the Why names a shared folder in words; a Remove that reaches more than one client names
  them all (F1); "Manage tools" from a Library row of a held server (F9).
- Part 4: Add missing follows the tab ("Add missing skills…", only that kind) (F4).
- Part 5: the tools panel has its own scope choice "For: <scope> ▾"; tool reviews' titles start
  with the scope; tool switch words stay "On" and "Off" (F10).

## Walkthroughs

Part 1's last task and Part 6's last task each write `docs/research/walkthrough-script-<n>.md`:
the seven tasks of concept §12 as plain steps for `kitden demo --size medium`, with a table to
fill in (task, done, wrong turns, time, what was confusing). The owner runs it; the controller
writes the results file and turns each finding into a ruling for the next part.
