# Phase 3 backend: the preview tray as one change — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Many preview-tray requests become ONE change in the change engine, so Apply all and Undo all are all-or-nothing, and a request that clashes with the tray is refused when it is added.

**Architecture:** A new pure module `src/kitden/changes/batch.py` reads the requests, finds clashes and merges the step lists in tray order (an identical write is kept once). `app.py`'s preview builder moves into one helper that both `POST /api/changes/preview` and the new `POST /api/batch/preview` and `POST /api/batch/check` call. The combined change keeps its rows (`Change.rows`, kept in the record and the log), so progress events can name the row of each step. Apply, Undo and Cancel stay today's `POST /api/changes/{id}/{verb}`.

**Tech Stack:** Python 3.13, Starlette, pytest on sandbox homes (`build_demo_home`, `make_home`).

**Spec:** master plan `docs/superpowers/plans/2026-10-24-mockup-alignment.md` (Phase 3, Tasks 3.1–3.3; decisions D10, D11, D13, D20), `docs/mockup/motion-spec.md` M4, the `tray` object in `docs/mockup/kitden-motion.html`.

## Decisions

- **Several projects for one tool rule: one request per project.** D13 says each ticked project is one tray row, and the mockup's `changeProject` adds one row per project, which can be taken out alone. `rule_steps` stays as it is; two projects write two different keys, so they never clash, and the batch makes them all-or-nothing anyway.
- **Words of a row come from the page.** The page already makes every review title (`ruleText`, `changeTitle`), and the mockup sets `title` and `detail` when a row is added. Each request carries `title` (required) and `detail`; the server returns them in `rows`. The server adds what only it knows: `project`, `steps`, `after`, `target`, `undo_note`.
- **The change's action:** one request → its own kind (so the Changes page, `rule_of` and the refresh after a move work as today); two or more → `"batch"`.
- **An identical write is kept once.** Two moves into the Kitden gateway both add the same `kitden` entry, PATH or Codex timeouts. Same file, key, value, mechanism and command, and no Keychain item: one step, listed in both rows.
- **Progress names a row, not a done row.** The engine still runs steps by kind (Keychain, gateway, copies, removals, then files in tray order). Each `change_progress` event carries `row`, the id of the row whose step just ended (the first row, for a shared step; `null` for Undo's final count). A row shows a check only when the whole change answers `verified` (D20).

## Global Constraints

- `AGENTS.md` in full: simple English in code, comments and words; tests on sandbox homes only, never the real home.
- Every write is preview → Apply with a backup → verify → Undo through `src/kitden/changes/engine.py`. Nothing in this phase writes outside the engine.
- No page, CSS, `docs/design.md`, `ROADMAP.md` or `design/` change in this phase.
- Refusal words are plain and name no path, address or command.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs`.
- Commit messages: a short plain subject, one to three simple lines, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- A file changed by hand between the batch preview and Apply all: the whole change is `stale` (409), every file stays as the person left it. Test in Task 3.3.
- Two moves into the Kitden gateway from Cursor, which lacks the `kitden` entry: both add that entry; they must join, not clash, and the entry is written once. Test in Task 3.2.
- A file changed after Apply all, before Undo all: the whole Undo is blocked and nothing changes, also in the other files. Test in Task 3.3.
- A request the builder refuses (an unknown server, a project Kitden does not know): 422 with the builder's words and that row's id; nothing is previewed. Test in Task 3.1.
- A body with a missing title or two rows with one id: 422 with plain words. Test in Task 3.1.

---

### Task 3.1: One change from many requests

**Files:**
- Create: `src/kitden/changes/batch.py`
- Modify: `src/kitden/model.py` (`Change.rows`), `src/kitden/changes/engine.py` (`_record`, `_from_record`, `_log`), `src/kitden/web/app.py` (`preview` at 946-1190, `change_dict` at 189, routes at 1330)
- Test: `tests/unit/test_batch.py`, `tests/unit/test_api_batch.py`

**Interfaces:**
- Produces in `batch.py`:
  - `BATCH = "batch"`
  - `@dataclass class Part: id: str; title: str; steps: list[Step]`
  - `requests_in(body: dict) -> list[dict]`: each `{id, kind, title, detail, targets, params}`; raises `ValueError(NEEDS)` (`NEEDS = "Each change needs an id, a kind and a title."`) or `ValueError(SAME_ID)` (`SAME_ID = "Two changes in the preview have the same id."`). `requests` must be a non-empty list of dicts; `id`, `kind`, `title` non-empty strings; `detail` a string (default `""`); `targets` a list (default `[]`); `params` a dict (default `{}`).
  - `same_write(a: Step, b: Step) -> bool`
  - `combine(parts: list[Part]) -> tuple[list[Step], list[list[int]]]`: one step list in tray order, an identical write kept once (the first), and each part's indices into it.
  - `part_of(change: Change, row: dict) -> Change`: `Change(action=row["kind"], steps=[change.steps[i] for i in row["steps"]])`, sharing the step objects.
- Produces in `model.py`: `Change.rows: list[dict] | None = None` — each `{id, kind, title, detail, project, steps}`.
- Produces in `app.py` (inside `create_app`): `@dataclass Built(steps, items=[], left_out=None, copied=None, align=None)` at module level; `async def _steps_for(action: str, targets: list, params: dict) -> Built` (every builder refusal raises `ValueError` with today's words); `def _review(change: Change, built: Built, picked: str | None) -> dict` (runs `mark_reach`, sets `change.target`, returns `{"after", "undo_note"}` plus `left_out` / `align` when set).

- [ ] **Step 1: Write the failing module tests** in `tests/unit/test_batch.py` (steps built with `settings_step`, `rule_step` and plain `FileEdit`s on files in `tmp_path`):
  - `test_requests_in_reads_each_change`: a body with two requests returns them with defaults filled (`detail == ""`, `targets == []`, `params == {}`).
  - `test_requests_in_refuses_a_missing_title_or_a_repeated_id`: `pytest.raises(ValueError, match=re.escape(NEEDS))` for no title, an empty list, a non-dict request; `match=re.escape(SAME_ID)` for two ids `"a"`.
  - `test_combine_keeps_tray_order_and_maps_each_part`: parts `a` = [s1, s2], `b` = [s3] → steps `[s1, s2, s3]`, maps `[[0, 1], [2]]`.
  - `test_an_identical_write_is_kept_once`: two parts each with `settings_step(home, ("path",), "/bin", "PATH")` plus one own step → three steps, maps `[[0, 1], [0, 2]]`; `same_write` is False when the value differs or one step has a Keychain item.
  - `test_record_keeps_the_rows`: an engine on a `ChangeStore` in `tmp_path`; preview two settings steps, set `change.rows`, apply; `Engine(store, run)` again → `changes[id].rows == rows`; the log's last entry has the same `rows`.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_batch.py -q` — expected: FAIL (`kitden.changes.batch` not found).
- [ ] **Step 3: Implement** `batch.py` (the Interfaces above), `Change.rows`, and the record and log fields in `engine.py` (`"rows": change.rows`; read back with `record.get("rows")`). `same_write` compares the real path (`os.path.realpath`), `fmt`, `key`, `after`, `mechanism` and `command`; a step without `edit` or with `keychain` is never the same write.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_batch.py -q` — expected: PASS.
- [ ] **Step 5: Write the failing route tests** in `tests/unit/test_api_batch.py`. Helper `_page(tmp_path, fail=None)`: `build_demo_home(tmp_path / "demo", "medium")`, `create_app(demo_build(home), token="tok", port=47800, home=home, demo=True, run=…)` where `run` wraps `DemoRunner(home)` and answers `CommandResult(1, "failed")` for a command that starts with `fail`; yields a `TestClient` with `.home`. Helpers `_ids(page, client)` (user-scope MCP item ids by name, from `/api/items`), `_files(home)` (bytes of `.claude.json`, `.codex/config.toml`, `.cursor/mcp.json` and the Kitden gateway settings file), `_remove(id, item_id, title)` (a `mcp.remove_direct` request). Tests:
  - `test_two_requests_on_cursors_file_apply_as_one_change`: requests remove `n8n` and `browser-tools` from Cursor → 200, `action == "batch"`, `rows` ids `["a", "b"]` with their titles, each with one step index; apply → 200 `verified`; Cursor's file still has `files` and neither of the two.
  - `test_a_failing_last_step_puts_every_file_back`: `fail=["claude", "mcp", "remove"]`; requests remove `n8n` (Cursor), `docs` (Codex), `docs` (Claude Code), in that order → apply answers 500, `state == "restored"`, error ends with `"The original settings were restored."`, `_files(home)` equals the bytes before.
  - `test_one_project_per_request_for_one_tool`: three `gateway.rule` requests (`files`, `read_file`, `off`) for the projects `work/atlas`, `work/atlas/web`, `work/website` (ids from `/api/projects`) → one change; each row's `project` is its folder; apply → `verified`; the settings file has `read_file: off` under each of the three projects.
  - `test_one_request_keeps_its_own_kind`: one `gateway.rule` request → `action == "gateway.rule"`, `rows` has one row, the row's `after` equals what `/api/changes/preview` answers for the same request.
  - `test_a_refused_request_names_its_row`: a `gateway.rule` request for server `nope` → 422, `detail == "Choose a server in the Kitden gateway."`, `row == "b"`; `/api/changes` log unchanged.
  - `test_a_bad_body_is_refused_in_plain_words`: no title → 422 `detail == NEEDS`; ids `a`, `a` → 422 `detail == SAME_ID`.
- [ ] **Step 6: Run** `uv run pytest tests/unit/test_api_batch.py -q` — expected: FAIL (404 on `/api/batch/preview`).
- [ ] **Step 7: Refactor `preview` and add the route.** Move the builder branches of `preview` (the stale-item check, every `action` branch, the unread-file check) into `_steps_for`; each `return _error(text, 422)` there becomes `raise ValueError(text)`. `project.align` with no steps returns `Built(steps=[], align=align)` and `preview` answers the listing as today. Move the after-preview part into `_review`. `preview` keeps its answers byte for byte. `change_dict` gains `"rows": change.rows`. Add `batch_preview` at `Route("/api/batch/preview", batch_preview, methods=["POST"])`: `requests_in(body)` (422 `{"detail"}`); `_steps_for` per request (422 `{"detail": refusal_words(error), "row": id}`); `combine`; `engine.preview(kind if one else BATCH, steps)` in a thread (422 `{"detail", "row": None}`); `change.rows` = one row per request with `project` = `sub.target["project"]` when `sub.target["scope"] == "project"`, else `None`, where `sub = part_of(change, row)` after `_review(sub, built, picked)`; `change.target = change_target(change, known, inventory, picked, all items)`; publish `change_state`; answer `{**change_dict(change), "rows": [row + {after, target, undo_note, left_out?, align?}], "undo_note": the rows' notes joined, each once, or None}`.
- [ ] **Step 8: Run** `uv run pytest -q` — expected: PASS (the old preview tests too).
- [ ] **Step 9: Commit** — `Tray: many previews as one change` + the checks.

### Task 3.2: Refuse clashes at add time

**Files:**
- Modify: `src/kitden/changes/batch.py`, `src/kitden/changes/engine.py` (`Engine.check`), `src/kitden/web/app.py`
- Test: `tests/unit/test_batch.py`, `tests/unit/test_api_batch.py`

**Interfaces:**
- Consumes: `Part`, `combine`, `same_write`, `requests_in`, `_steps_for`, `Built` (Task 3.1).
- Produces in `batch.py`:
  - Words: `SAME = "“{other}” in the preview changes the same {what}. Apply the preview first, or take that one out."` (`what` is `setting`, `folder` or `server`); `LEAVES = "“{other}” in the preview removes {server} from the gateway. Apply the preview first, or take that one out."`; `REMOVES = "This removes {server} from the gateway, but “{other}” in the preview changes it. Apply the preview first, or take that one out."`; `TWO_GATEWAYS = "“{other}” in the preview moves servers into another gateway. Apply the preview first, or take that one out."`
  - `clash(earlier: list[Part], new: Part) -> str | None` — checks in this order: registered gateways (another `gateway_id` → `TWO_GATEWAYS`; same gateway and name → `SAME` with `server`); a Kitden gateway server one part removes (`client == "kitden"`, key `("servers", S)`, after `ABSENT`) while the other touches S (`("servers", S)`, `("rules", "global", S, …)`, `("rules", "projects", P, S, …)`) → `REMOVES` when the new part removes, `LEAVES` when an earlier one does; a file entry on the same real path where one key is the other or starts with it, unless `same_write` → `SAME` with `setting`; one copy target or removed folder twice → `SAME` with `folder`. `other` is the earlier part's title.
  - `first_clash(parts: list[Part]) -> tuple[str, str] | None`: `(reason, id of the part that cannot join)`.
- Produces in `engine.py`: `Engine.check(self, steps: list[Step]) -> None` — runs `preview("check", steps)` and forgets that change; raises as `preview` does; writes nothing.
- Produces route `POST /api/batch/check`.

- [ ] **Step 1: Write the failing module tests** in `tests/unit/test_batch.py`:
  - `test_removing_a_server_clashes_with_a_rule_for_it`: `held = {"github": {...}}` with no rules; `a` = `remove_server_steps` for github (title `"Remove github from the gateway"`), `b` = `rule_step(home, None, "github", "create_issue", "off")` → `clash([a], b) == LEAVES.format(other="Remove github from the gateway", server="github")`; reversed → `REMOVES.format(other=b.title, server="github")`.
  - `test_the_same_entry_twice_clashes`: two `rule_step`s for one tool with `on` and `off` → `SAME` with `setting`; `on` twice → `None`.
  - `test_one_entry_inside_another_clashes`: steps on one JSON file with keys `("mcpServers", "x")` and `("mcpServers", "x", "env")` → `SAME` with `setting`.
  - `test_two_registered_gateways_clash`: two gateway steps (`GatewayEdit`) with ids `g1`, `g2` → `TWO_GATEWAYS`; same id and name → `SAME` with `server`.
  - `test_first_clash_names_the_part_that_cannot_join`: parts `a`, `b`, `c` where only `c` clashes with `a` → `(reason, "c")`.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_batch.py -q` — expected: FAIL (`clash` not defined).
- [ ] **Step 3: Implement** `clash`, `first_clash`, the words and `Engine.check`.
- [ ] **Step 4: Run** `uv run pytest tests/unit/test_batch.py -q` — expected: PASS.
- [ ] **Step 5: Write the failing route tests** in `tests/unit/test_api_batch.py` (a helper `_hold(home, "github", ["create_issue", "list_issues"])` adds github to the demo gateway's settings and tools files):
  - `test_remove_github_and_a_github_tool_are_refused_at_check`: `/api/batch/check` with `[remove github (a), turn off create_issue of github (b)]` → 200 `{"ok": False, "reason": LEAVES…, "row": "b"}`; the same body to `/api/batch/preview` → 422 with the same `detail` and `row`.
  - `test_check_says_ok_for_two_rules`: two rules for two tools → `{"ok": True}`; no `change_state` event is published (subscribe to `page.app.state.events` first) and the `/api/changes` log is unchanged.
  - `test_check_names_the_new_row_when_nothing_would_change`: a rule that turns `delete_file` of `files` off for all projects (already off) → `{"ok": False, "reason": "The Kitden gateway has this already. Nothing to change.", "row": <its id>}`.
  - `test_two_moves_from_cursor_join`: `gateway.move` into `kitden` for Cursor's `n8n` (a) and `browser-tools` (b) → check `{"ok": True}`; preview → one step writes Cursor's `kitden` entry and both rows list its index; apply → `verified`, Cursor's file has `kitden` once and neither server.
- [ ] **Step 6: Run** `uv run pytest tests/unit/test_api_batch.py -q` — expected: FAIL.
- [ ] **Step 7: Implement** one helper in `create_app`, `async def _batch(requests, keep: bool) -> tuple[Change | None, list[dict], list[Built]]` raising `_RowRefused(reason, row)`: build each request (row = its id), `first_clash` (row = the part that cannot join), `combine`, then `engine.preview` when `keep`, else `engine.check` (row = `None`). `batch_preview` uses it with `keep=True`. `batch_check` at `Route("/api/batch/check", batch_check, methods=["POST"])` uses `keep=False` and answers `{"ok": True}` or `{"ok": False, "reason", "row": row or the last request's id}`, 200; a bad body is 422 `{"detail"}`. Check publishes no event.
- [ ] **Step 8: Run** `uv run pytest -q` — expected: PASS.
- [ ] **Step 9: Commit** — `Tray: refuse a clash when a change is added`.

### Task 3.3: Apply all and Undo all

**Files:**
- Modify: `src/kitden/changes/engine.py` (`on_progress`, `_counter`, `_apply_gateway`, `_remove_from_gateway`, the ticks in `_apply` and `undo`), `src/kitden/web/app.py` (`change_action` at 1192-1227)
- Test: `tests/unit/test_engine.py:458-469`, `tests/unit/test_api_batch.py`

**Interfaces:**
- Consumes: `Change.rows`, `part_of` (Task 3.1).
- Produces in `engine.py`: `Engine.on_progress: Callable[[str, int, int, int | None], None]` — `(change id, steps done, all steps, index in change.steps of the step just done)`; the index is `None` only for Undo's final count. `_counter(change)` returns `tick(step: Step) -> None` (index by identity, not `==`).
- Produces in `batch.py`: `step_rows(rows: list[dict]) -> dict[int, str]` — step index → the first row (tray order) that lists it.
- Produces event: `change_progress` data `{"id", "done", "total", "row"}`; `row` is `None` for a change without rows.

- [ ] **Step 1: Write the failing tests:**
  - In `test_engine.py`, `test_apply_and_undo_say_how_many_steps_are_done`: the lambda takes four values; apply gives `[(id, 1, 2, 0), (id, 2, 2, 1)]`; Undo's last is `(id, 2, 2, None)`.
  - In `test_batch.py`, `test_step_rows_names_the_first_row_of_a_shared_step`: rows `a: [0, 1]`, `b: [0, 2]` → `{0: "a", 1: "a", 2: "b"}`.
  - In `test_api_batch.py`:
    - `test_progress_names_each_row`: subscribe to `page.app.state.events` before apply of three requests (Cursor `n8n`, Codex `docs`, a `files` rule) → every `change_progress` event has `row` in `{"a", "b", "c"}`, all three appear, the last has `done == total`; apply answers `verified`.
    - `test_undo_all_restores_every_file`: requests remove `n8n` (Cursor), `browser-tools` (Cursor), `docs` (Codex), a `files` rule → apply `verified`, then `POST /api/changes/{id}/undo` → 200 `undone`, `_files(home)` equals the bytes before the preview; the Undo's progress events carry rows too.
    - `test_a_file_changed_before_apply_all_stops_all`: batch preview of Cursor `n8n` and Codex `docs`, then a hand edit of Cursor's file → apply 409 `stale`; Codex's file and Cursor's hand edit are as they were.
    - `test_a_file_changed_before_undo_all_blocks_all`: apply the same two, then a hand edit of Cursor's file → undo 409 `undo_blocked`; Codex's file is still without `docs`.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_engine.py tests/unit/test_batch.py tests/unit/test_api_batch.py -q` — expected: FAIL on the progress tests.
- [ ] **Step 3: Implement** the engine's tick with the step (every call site passes the step it just finished; Undo's final call passes `None`), `step_rows`, and in `change_action`: `owners = step_rows(change.rows or [])`, `progress(change_id, done, total, index)` publishes `{"id", "done", "total", "row": owners.get(index)}`; the default `on_progress` is a four-value lambda. After a verified Apply, refresh the tools of servers moved in by `gateway.move` rows too: `moved_in(part_of(change, row))` for each row of kind `gateway.move`, or `moved_in(change)` for a plain move.
- [ ] **Step 4: Run** `uv run pytest -q` — expected: PASS.
- [ ] **Step 5: Run all checks** — `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src tests`, `node --test tests/frontend/*.test.mjs` — all pass.
- [ ] **Step 6: Commit** — `Tray: progress names the row of each step`.
