# Part 3: Complete management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every management action the reviews found missing is a change with preview, Apply with a backup, verify and Undo: remove a plugin, a skill or a Kitden gateway server; put a held server back in a client; add an MCP server to another client; add a skill or a plugin into one project; align a project across clients in one review.

**Architecture:** New step builders in `src/kitden/changes/actions.py` and the three adapters (the plugins' own remove commands, `add_server_step`), one new module `src/kitden/changes/server_entry.py` that turns an entry of any client into the target client's format, one new step kind `FolderRemoval` in `model.py` that `engine.py` handles like `FolderCopy` (the folder is copied into the change's backup folder first; Undo copies it back), the new actions dispatched in `web/app.py`'s `preview`, review words in `views/after.py`, Library cells in `views/library.py`, and buttons and the two-choice panel in `library.js`, `panel.js` and `offer.js`. Every action is one change in the engine; nothing writes a client's file any other way.

**Tech Stack:** Python 3.13, Starlette, tomlkit; plain ES modules; pytest on sandbox homes; node's test runner.

**Spec:** `docs/superpowers/specs/2026-10-21-review-follow-up-design.md`, Part 3 (3.1 to 3.6), with Why, Non-goals, Anti-goals, Constraints and the Acceptance row for Part 3. Master plan: `docs/superpowers/plans/2026-10-21-review-follow-up.md` (the names `translate_entry`, `ClientAdapter.add_server_step`, `FolderRemoval`, `REMOVE_FOLDER`, `resolve_entry` are fixed there). Part 1's plan defines `addName(row, client, add, project)` and `scopeLine(project, rows)` in `library.js`; Task 5 builds on them. Line numbers below are as of `d33bfaf`; Parts 1 and 2 shift them a little.

## Global Constraints

- Code, comments, UI text and docs in simple English, short and plain; the owner is talked to in Russian (`AGENTS.md`).
- Every change of a client's settings goes through preview → Apply with a backup → verify → Undo, through `src/kitden/changes/engine.py`; nothing else ever writes a client's file (spec Anti-goals).
- A secret never reaches the page, a review, a log, a record's masked diff or an error message: every new output goes through `redact`; fixtures hold `SENTINEL_SECRET_*` strings and `tests/security/test_no_secrets.py` must still pass.
- A success look appears only after the server says `verified`; no promise the code cannot keep; no more text on the main pages (a name, the client and an action; paths, addresses and commands stay in Details).
- `docs/design.md`: new page text is tested in `tests/unit/test_page_words.py`; page logic is a pure function exported from a module under `src/kitden/web/static/js/` and tested with `node --test tests/frontend/*.test.mjs`; a quiet line is `el("p", "muted", …)` or `el("p", "group-note", …)`.
- Tests use sandbox homes only: `make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")` and `write_cursor_fixture_state(home)` from `tests/conftest.py`; `read_command_version` is stubbed as the existing tests do.
- Python 3.13, Starlette, the official MCP SDK 2.3, tomlkit, watchfiles; plain ES modules and one CSS file; no framework, no bundler, nothing loaded from another site; strict CSP. No new runtime dependency.
- A fact about a client (a CLI flag, a file format, a folder it reads) is checked against that client's current docs before it is relied on, and `checked YYYY-MM-DD` goes next to the claim in a comment.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`. All three pass or the commit waits.
- Commit messages: a short plain subject, one to three simple lines, no prefix such as `feat:`.
- `ROADMAP.md` is updated in the same change as the last task; release notes are written at release time, not here.
- Until Part 5 exists, Part 3 treats every held entry as plain: no `{"keychain": …}` reference is resolved (master plan, `resolve_entry`).

## Review Focus

1. A skill folder that is a symlink: Remove must refuse with "… is a link; Kitden removes only real folders" and touch nothing, neither the link nor what it points to (Task 2, `test_a_linked_skill_folder_is_refused` in `tests/unit/test_remove_skill.py` and `test_a_removal_of_a_link_is_refused` in `tests/unit/test_engine.py`).
2. Undo of a skill removal after a folder with that name came back by hand: Undo must stop (`undo_blocked`) and leave the new folder as it is, never overwrite it (Task 2, `test_undo_leaves_a_folder_that_came_back`).
3. Adding or putting back a server into a client that already has an entry of that name: refused before any step with "Codex already has neon." and nothing overwritten (Task 3, `test_put_back_is_refused_when_the_client_has_the_name`; Task 4, `test_a_name_the_client_has_is_refused`).
4. Removing a plugin that is turned off: Apply works, Undo installs it again and the plugin is then on, and the review said so before Apply (Task 1, `test_removing_an_off_plugin_says_undo_turns_it_on` and `test_undo_by_command_only_needs_the_entry_back` in `tests/unit/test_engine.py`).
5. "Add to this project…" for Codex in a project Codex has not trusted: the copy would land but never load, so it is refused with "Codex does not trust website yet, so it would not load the skill there." (Task 5, `test_a_codex_project_copy_needs_trust`).

---

### Task 1: Remove a plugin (3.1)

**Files:**
- Modify: `src/kitden/clients/base.py:305-309` (constants) and `256-262` (new `plugin_remove_step` default)
- Modify: `src/kitden/clients/claude_code.py:88-99` (`item_actions`), after `plugin_install_step` (155-173): new `plugin_remove_step`
- Modify: `src/kitden/clients/codex.py:164-174` (`item_actions`), after `plugin_install_step` (219-236): new `plugin_remove_step`
- Modify: `src/kitden/clients/cursor.py:46-49` (`CURSOR_HINT`)
- Modify: `src/kitden/changes/actions.py:222-227` (after `remove_steps`: new `remove_plugin_steps`)
- Modify: `src/kitden/changes/engine.py:673-677` (the Undo read-back check)
- Modify: `src/kitden/web/app.py:48` (import), `849-859` (dispatch), `866-868` (`cursor_imports` also for a removal)
- Modify: `src/kitden/views/after.py:33-44` (`WORDS`), `363-382` (`after_words`: the two notes)
- Modify: `src/kitden/web/static/js/panel.js:14-18` (`ACTION_BUTTONS`), `611-617` (`DONE_WORDS`), `638-665` (`changeWords`)
- Modify: `src/kitden/web/static/js/parts.js:212-226` (`ACTION_WORDS`), `246` (`plugin` actions)
- Create: `tests/unit/test_remove_plugin.py`
- Test: `tests/unit/test_engine.py`, `tests/unit/test_actions.py:32-37` (the actions set gains `plugin.remove`), `tests/unit/test_explain.py:44` (`["plugin.disable", "plugin.remove"]`), `tests/frontend/panel.test.mjs`, `tests/frontend/parts.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `FakeCli` from `tests/unit/test_api_plugin_install.py` (its `uninstall` deletes the `enabledPlugins` entry and the install record; its `codex plugin remove` deletes the `[plugins."<id>"]` table); `toggle_action`, `check_toggle` (`base.py`); `_other_copy_loads` and `CURSOR_IMPORT` (`after.py`).
- Produces: `PLUGIN_REMOVE = "plugin.remove"` (`base.py`); `ClientAdapter.plugin_remove_step(item: Item) -> Step`; `remove_plugin_steps(adapters: dict[str, ClientAdapter], item: Item) -> list[Step]` raising `ValueError(f"{item.name} cannot be removed here")`; Claude Code's step: `mechanism="client_cli"`, `command=["claude", "plugin", "uninstall", id, "-s", scope, "--json"]`, `undo_command=["claude", "plugin", "install", id, "-s", scope, "--json"]`, `edit=FileEdit(path=item.source.path, fmt="json", key=("enabledPlugins", id), after=ABSENT, check="entry")`, `cwd=item.project` for the project scope, `restart_note=RELOAD`, `shared_file` for the project scope; Codex's step: `command=["codex", "plugin", "remove", id]`, `undo_command=["codex", "plugin", "add", id, "--json"]`, `edit=FileEdit(path=config, fmt="toml", key=("plugins", id), after=ABSENT, check="entry")`, `restart_note=RESTART`. Engine: a `client_cli` step with an `undo_command` whose `after` is `ABSENT` reads back as undone when the entry is there again (`PRESENT`), not only when it equals `before`. `WORDS["plugin.remove"] = ("off", "Removed")`; the after entry of a plugin that was off carries `"note": "Undo installs it again and turns it on."`; a removal from Claude Code with Cursor importing adds `{"client": "cursor", "state": "off", "word": "Removed", "note": "Cursor loads Claude Code plugins, so it loses this one too."}`. `CURSOR_HINT = "Cursor keeps its plugins in its own database. Remove it in Cursor: Customize → Plugins."`. Page: `ACTION_BUTTONS["plugin.remove"]` gives `Remove from ${client}…`; `changeWords` title `Remove ${short} from ${clients}`, done `Removed ${short} from ${clients}`; `ACTION_WORDS["plugin.remove"] = "Removed"`.

- [ ] **Step 1: Check the clients' docs**

Check `claude plugin uninstall --help` (and code.claude.com/docs/en/plugins) for the `-s <scope>` and `--json` flags and that it removes the `enabledPlugins` entry of that scope's settings file; write `# checked YYYY-MM-DD: …` above `plugin_remove_step` in `claude_code.py`. Check `codex plugin remove --help` (and developers.openai.com/codex/plugins) for the command's form and that it deletes the `[plugins."<id>"]` table; write the same line in `codex.py`. If a fact differs (the entry becomes `false` instead of going away, say), change `after` and the test's assertions together in this task.

- [ ] **Step 2: Write the failing tests**

`tests/unit/test_remove_plugin.py` (fixture `client` built like `cursor_client` in `test_api_plugin_install.py`: Claude Code, Codex and Cursor with import on, `run=FakeCli(home)`):

```python
SUPERPOWERS = "superpowers@claude-plugins-official"
OFF = "claude-md-management@claude-plugins-official"
BROWSER = "browser@openai-bundled"


def _item(client, name, who="claude_code"):
    return next(i for i in client.get(f"/api/items?client={who}&kind=plugin").json() if i["name"] == name)


def _remove(client, item_id):
    body = {"action": "plugin.remove", "targets": [{"item": item_id}], "params": {}}
    return client.post("/api/changes/preview", json=body, headers=POST)


def test_removing_a_claude_code_plugin_runs_uninstall_and_undo_installs_it_again(client):
    change = _remove(client, _item(client, SUPERPOWERS)["id"]).json()
    assert [(s["client"], s["name"]) for s in change["steps"]] == [("claude_code", SUPERPOWERS)]
    assert change["steps"][0]["command"] == f"claude plugin uninstall {SUPERPOWERS} -s user --json"
    assert change["after"] == [
        {"client": "claude_code", "state": "off", "word": "Removed"},
        {"client": "cursor", "state": "off", "word": "Removed",
         "note": "Cursor loads Claude Code plugins, so it loses this one too."},
    ]
    assert client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
    settings = json.loads((client.home / ".claude/settings.json").read_text())
    assert SUPERPOWERS not in settings["enabledPlugins"]
    assert client.run.calls[-1][:3] == ["claude", "plugin", "uninstall"]
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    assert client.run.calls[-1][:3] == ["claude", "plugin", "install"]
    settings = json.loads((client.home / ".claude/settings.json").read_text())
    assert settings["enabledPlugins"][SUPERPOWERS] is True


def test_removing_an_off_plugin_says_undo_turns_it_on(client):
    change = _remove(client, _item(client, OFF)["id"]).json()
    assert change["after"][0]["note"] == "Undo installs it again and turns it on."
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    assert client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    settings = json.loads((client.home / ".claude/settings.json").read_text())
    assert settings["enabledPlugins"][OFF] is True


def test_removing_a_codex_plugin_keeps_the_rest_of_the_file(client):
    change = _remove(client, _item(client, BROWSER, "codex")["id"]).json()
    assert change["steps"][0]["command"] == f"codex plugin remove {BROWSER}"
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    text = (client.home / ".codex/config.toml").read_text()
    assert BROWSER not in tomllib.loads(text).get("plugins", {}) and "# Owner comment: keep me" in text
    assert client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    assert tomllib.loads((client.home / ".codex/config.toml").read_text())["plugins"][BROWSER] == {"enabled": True}


def test_plugins_without_a_file_entry_cannot_be_removed(client):
    gmail = _item(client, "gmail@openai-curated-remote", "codex")  # cache only, state in the account
    assert _remove(client, gmail["id"]).status_code == 422
    cursor = _item(client, SUPERPOWERS, "cursor")  # imported from Claude Code
    assert _remove(client, cursor["id"]).status_code == 422
    assert "Remove it in Cursor: Customize → Plugins." in CURSOR_HINT


def test_details_offer_remove_for_each_definition_that_has_a_file(client):
    answer = client.get(f"/api/explain?name={SUPERPOWERS}&kind=plugin").json()["definitions"]
    by_client = {(d["client"], d["scope"]): d["actions"] for d in answer}
    assert "plugin.remove" in by_client[("claude_code", "user")]
    assert "plugin.remove" in by_client[("claude_code", "project")]
    assert by_client[("cursor", "user")] == []
```

`tests/unit/test_engine.py`, after `test_undo_runs_the_inverse_commands_in_reverse_order`:

```python
def test_undo_by_command_only_needs_the_entry_back(tmp_path, settings):
    # The plugin was off; uninstall removes its entry and the client's own install puts it
    # back on. Undo is still an undo: the entry is there again.
    settings.write_text(json.dumps({"enabledPlugins": {"lint@tools": False}}))
    engine = make_engine(tmp_path, run=FakePluginCli(settings))
    remove = Step(
        client="claude_code", scope=Scope.USER, name="lint@tools",
        edit=FileEdit(path=str(settings), fmt="json", key=("enabledPlugins", "lint@tools"), after=ABSENT, check="entry"),
        mechanism="client_cli",
        command=["claude", "plugin", "uninstall", "lint@tools", "-s", "user", "--json"],
        undo_command=["claude", "plugin", "install", "lint@tools", "-s", "user", "--json"],
    )
    change = engine.preview("plugin.remove", [remove])
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    assert json.loads(settings.read_text())["enabledPlugins"] == {}
    assert engine.undo(change.id).state is ChangeState.UNDONE
    assert json.loads(settings.read_text())["enabledPlugins"] == {"lint@tools": True}
```

`tests/frontend/panel.test.mjs`: in the test "a problem comes before an option", add `const removePlugin = { def: { id: 'p-1', client: 'claude_code' }, action: 'plugin.remove' };` and `assert.deepEqual(footerActions([off, removePlugin], [{ level: 'warning', client: 'claude_code', fix_action: 'plugin.disable' }], null), { lead: off, rest: [removePlugin] });` (`off` as in the Details test). Also: `assert.equal(changeWords({ action: 'plugin.remove', steps: [{ client: 'claude_code', name: 'superpowers@claude-plugins-official' }] }).title, 'Remove superpowers from Claude Code');` and `.done === 'Removed superpowers from Claude Code'`.

`tests/frontend/parts.test.mjs`: `assert.equal(changeTitle({ action: 'plugin.remove', steps: [{ client: 'codex', name: 'browser@openai-bundled' }] }), 'Removed browser · Codex');`.

`tests/unit/test_page_words.py`: `test_details_offer_remove_for_plugins_and_skills`: `panel.js` contains `'"plugin.remove": (client) => \`Remove from ${client}…\`'` (Task 2 adds the `skill.remove` line to the same test).

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/unit/test_remove_plugin.py tests/unit/test_engine.py::test_undo_by_command_only_needs_the_entry_back -v` and `node --test tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs`
Expected: FAIL: the action is not offered (422), the engine raises "undo did not read back as expected", the words are missing.

- [ ] **Step 4: Implement the steps and the engine check**

`base.py`: the constant and the default method. `claude_code.py` `item_actions`: the plugin branch returns `(*toggle_action(item), PLUGIN_REMOVE)`; `plugin_remove_step` as the interface says (a project scope needs its folder: reuse the `is_dir` check `plugin_step` makes). `codex.py`: the same for a plugin with a file source. `cursor.py`: the new `CURSOR_HINT`. `actions.py`: `remove_plugin_steps`. `engine.py` `undo`, at the final read-back (lines 673-675): `expected = PRESENT if step.mechanism == CLIENT_CLI and step.undo_command and step.edit.after is ABSENT else step.edit.before`, then `if not _matches(step, _value(...), expected): raise RuntimeError(...)`.

- [ ] **Step 5: Wire the page and the words**

`app.py`: dispatch `PLUGIN_REMOVE` next to `PLUGIN_ENABLE`/`PLUGIN_DISABLE` (one item; `remove_plugin_steps`), and `cursor = _found_cursor() if action in (PLUGIN_INSTALL, PLUGIN_REMOVE) else None`. `after.py`: the `WORDS` entry; in the generic loop, for `plugin.remove` with `step.edit.before is False` set the note; after the loop, `if change.action == "plugin.remove" and to_claude and cursor_imports and change.steps[0].scope is Scope.USER: out.append({...the cursor entry...})`. `panel.js` and `parts.js` as the interface says (`REMOVES = ["mcp.remove_direct", "plugin.remove", "skill.remove"]` picks the `from` wording in `changeWords`; `parts.js` line 246 adds `"plugin.remove"` to the plugin list so names are short). Update `tests/unit/test_actions.py:32-37` and `test_explain.py:44`.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/unit/test_remove_plugin.py tests/unit/test_engine.py tests/unit/test_actions.py tests/unit/test_explain.py tests/unit/test_page_words.py -v` and `node --test tests/frontend/*.test.mjs`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/kitden/clients/base.py src/kitden/clients/claude_code.py src/kitden/clients/codex.py src/kitden/clients/cursor.py src/kitden/changes/actions.py src/kitden/changes/engine.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/panel.js src/kitden/web/static/js/parts.js tests/unit/test_remove_plugin.py tests/unit/test_engine.py tests/unit/test_actions.py tests/unit/test_explain.py tests/unit/test_page_words.py tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs
git commit -m "Library: remove a plugin with Undo"
```

---

### Task 2: Remove a skill (3.2)

**Files:**
- Modify: `src/kitden/model.py:222-266` (`REMOVE_FOLDER`, `FolderRemoval`, `Step.removal`)
- Modify: `src/kitden/changes/backup.py:47-113` (`ChangeStore.backup_folder`)
- Modify: `src/kitden/changes/engine.py:69-75` (`_step_path`), `200-278` (records), `306-342` (`preview` calls `_preview_removals`), `449-523` (`apply`), `597-683` (`undo`), `687-711` (`_log`: `reaches`)
- Modify: `src/kitden/clients/base.py:284-302` (after `skill_copy_step`: `skill_remove_step`) and the constants
- Modify: `src/kitden/clients/claude_code.py:88-99`, `codex.py:164-174`, `cursor.py:83-85` (`item_actions`: skills)
- Modify: `src/kitden/views/skills.py` (end: `skill_readers`)
- Modify: `src/kitden/views/load_map.py:94-98` (`DUPLICATE_FIXES[ItemKind.SKILL]`)
- Modify: `src/kitden/changes/actions.py` (after `remove_plugin_steps`: `skill_remove_steps`)
- Modify: `src/kitden/web/app.py:138-148` (`_step_path`, `change_dict` `reaches`), `849-859` (dispatch)
- Modify: `src/kitden/views/after.py` (`_skill_remove_words`, wired first in `after_words`)
- Modify: `src/kitden/web/static/js/panel.js:14-18`, `611-617`, `638-665`; `parts.js:212-226`
- Create: `tests/unit/test_remove_skill.py`
- Test: `tests/unit/test_engine.py`, `tests/unit/test_actions.py:32-37` (the set gains `skill.remove`), `tests/unit/test_load_map.py` (the skill duplicate fix), `tests/frontend/panel.test.mjs`, `tests/frontend/parts.test.mjs`

**Interfaces:**
- Consumes: `copy_folder`, `remove_folder`, `digest`, `list_files`, `CopyRefusedError` (`copy_folder.py`); `_private_folder`, `_change_folder` (`backup.py`); `skill_items` sets `source.link_path` for a linked skill folder (`base.py:132-135`).
- Produces: `REMOVE_FOLDER = "remove_folder"` and `FolderRemoval(path: str, readers: list[str] = [], content_hash: str | None = None, backup_path: str | None = None, masked_diff: str = "")` in `model.py`; `Step.removal: FolderRemoval | None = None`; `ChangeStore.backup_folder(change_id: str, path: str) -> Path` (copies the folder into `<change folder>/folder-<name>` with `copy_folder`); engine: `_preview_removals(steps)` sets `path = realpath`, refuses a symlink with `ChangeRefusedError(f"{path} is a link; Kitden removes only real folders")`, a missing folder with `f"{path} is not a folder"`, a folder listed twice with `f"{path} would be removed twice in one change"`, fills `content_hash = digest(path)` and `masked_diff = "\n".join(f"-{f}" for f in list_files(path))`; `apply` (after the copies, before the file steps): stale when the folder is gone (`f"{path} is gone since preview; review the change again"`) or its digest changed; then `backup_path = store.backup_folder(...)`, `remove_folder(path)`, verify `not lexists(path)`; a later failure copies the backup back when nothing is at the path; `undo`: `lexists(path)` → `UNDO_BLOCKED` with `f"{path} is back; undo would overwrite it, so nothing was changed"`; backup gone → `UNDO_BLOCKED` with `f"the backup of {path} is gone, so nothing was changed"`; else `copy_folder(backup_path, path)` and verify `digest(path) == content_hash`. The log's `reaches` is `removal.readers`. `SKILL_REMOVE = "skill.remove"` (`base.py`); `ClientAdapter.skill_remove_step(item: Item, readers: list[str]) -> Step` (`mechanism=REMOVE_FOLDER`, `removal=FolderRemoval(path=str(Path(item.source.path).parent), readers=readers)`, `scope=item.scope`, `restart_note=self.skill_note or None`, `shared_file=item.scope is Scope.PROJECT`); an item gets `SKILL_REMOVE` when `kind is SKILL`, `scope in (USER, PROJECT)`, `source.kind is FOLDER`, `source.owner_client == self.id`, `source.link_path is None`; `skill_readers(inventory, item: Item) -> list[str]`: the clients (in `CLIENTS` order) of every skill item whose `realpath(source.path)` equals the item's; `skill_remove_steps(adapters, item, readers) -> list[Step]`; `DUPLICATE_FIXES[ItemKind.SKILL] = ("Remove one copy to keep the other.", "skill.remove")`; `WORDS["skill.remove"] = ("off", "Removed")` and the after entries are one per reader; page words as for `plugin.remove` with `skill.remove`: title `Remove ${names} from ${clients}`, done `Removed ${names} from ${clients}`, `ACTION_WORDS["skill.remove"] = "Removed"`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_engine.py` (use `tmp_path / "skills/tidy"` with a `SKILL.md`; a step `Step(client="codex", scope=Scope.USER, name="tidy", mechanism="remove_folder", removal=FolderRemoval(path=str(folder), readers=["codex", "cursor"]))`):

```python
def test_a_folder_removal_is_backed_up_and_undone(tmp_path):
    folder = tmp_path / "skills/tidy"; folder.mkdir(parents=True); (folder / "SKILL.md").write_text("tidy\n")
    before = digest(folder)
    engine = make_engine(tmp_path)
    change = engine.preview("skill.remove", [removal_step(folder)])
    assert change.steps[0].removal.masked_diff == "-SKILL.md"
    assert engine.apply(change.id).state is ChangeState.VERIFIED
    assert not folder.exists()
    backup = Path(change.steps[0].removal.backup_path)
    assert backup.is_relative_to(tmp_path / "data/changes") and digest(backup) == before
    assert engine.undo(change.id).state is ChangeState.UNDONE
    assert digest(folder) == before


def test_a_failed_step_after_a_removal_puts_the_folder_back(tmp_path, claude_json):
    # a removal followed by a client command that fails: the folder comes back from the backup
    ...
    assert change.state is ChangeState.RESTORED and folder.is_dir()


def test_a_removal_of_a_link_is_refused(tmp_path):
    real = tmp_path / "elsewhere/tidy"; real.mkdir(parents=True); (real / "SKILL.md").write_text("x")
    link = tmp_path / "skills/tidy"; link.parent.mkdir(); link.symlink_to(real)
    with pytest.raises(ChangeRefusedError, match="is a link; Kitden removes only real folders"):
        make_engine(tmp_path).preview("skill.remove", [removal_step(link)])
    assert link.is_symlink() and (real / "SKILL.md").exists()


def test_undo_leaves_a_folder_that_came_back(tmp_path):
    ...apply the removal, then folder.mkdir(parents=True); (folder / "notes.md").write_text("mine\n")
    assert engine.undo(change.id).state is ChangeState.UNDO_BLOCKED
    assert "is back" in change.error and (folder / "notes.md").read_text() == "mine\n"
```

`tests/unit/test_remove_skill.py` (fixture: the three clients, `write_cursor_fixture_state(home)`, `run=_no_run` as `test_api_skill_install.py` has it; `_remove(client, item_id)` posts `{"action": "skill.remove", "targets": [{"item": item_id}], "params": {}}`):

```python
def test_removing_a_skill_backs_it_up_and_undo_copies_it_back(client):
    home = client.home
    folder = home / ".claude/skills/brandkit"
    before = digest(folder)
    brandkit = _skill_item(client, "claude_code", "brandkit")
    change = _remove(client, brandkit["id"]).json()
    step = change["steps"][0]
    assert (step["client"], step["name"], step["reaches"], step["command"]) == ("claude_code", "brandkit", ["claude_code", "cursor"], None)
    assert step["path"] == str(folder) and step["diff"] == "-SKILL.md"
    assert change["after"] == [
        {"client": "claude_code", "state": "off", "word": "Removed"},
        {"client": "cursor", "state": "off", "word": "Removed"},
    ]
    assert client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
    assert not folder.exists()
    copies = list((data_dir(home) / "changes" / change["id"]).glob("folder-brandkit"))
    assert len(copies) == 1 and digest(copies[0]) == before
    rows = client.get("/api/library?kind=skill").json()["rows"]
    assert all(r["name"] != "brandkit" or r["cells"]["claude_code"]["state"] == "none" for r in rows)
    undone = client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")
    assert digest(folder) == before
    entry = client.get("/api/changes").json()[0]
    assert (entry["action"], entry["steps"][0]["reaches"]) == ("skill.remove", ["claude_code", "cursor"])


def test_a_plugin_skill_and_a_cross_loaded_skill_cannot_be_removed(client):
    assert _remove(client, _skill_item(client, "claude_code", "brainstorming")["id"]).status_code == 422
    assert _remove(client, _skill_item(client, "cursor", "brandkit")["id"]).status_code == 422
    assert _remove(client, _skill_item(client, "cursor", "docker-expert")["id"]).status_code == 422  # the shared folder is Codex's to remove


def test_a_linked_skill_folder_is_refused(client, tmp_path):
    real = tmp_path / "elsewhere/linked"; real.mkdir(parents=True)
    (real / "SKILL.md").write_text("---\nname: linked\n---\n")
    (client.home / ".claude/skills/linked").symlink_to(real)
    client.post("/api/rescan", headers=POST)
    linked = _skill_item(client, "claude_code", "linked")
    assert "skill.remove" not in linked["actions"]
    assert _remove(client, linked["id"]).status_code == 422
    assert (client.home / ".claude/skills/linked").is_symlink() and (real / "SKILL.md").exists()


def test_undo_leaves_a_folder_that_came_back(client):
    folder = client.home / ".agents/skills/docker-expert"
    change = _remove(client, _skill_item(client, "codex", "docker-expert", where=str(folder))["id"]).json()
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    folder.mkdir(parents=True); (folder / "notes.md").write_text("mine\n")
    blocked = client.post(f"/api/changes/{change['id']}/undo", headers=POST)
    assert blocked.status_code == 409 and blocked.json()["state"] == "undo_blocked"
    assert "is back" in blocked.json()["error"] and (folder / "notes.md").read_text() == "mine\n"


def test_a_duplicate_skill_keeps_one(client):
    # Codex loads docker-expert from ~/.agents/skills and ~/.codex/skills.
    row = next(r for r in client.get("/api/library?kind=skill").json()["rows"] if r["name"] == "docker-expert")
    flag = next(f for f in row["flags"] if f["level"] == "warning")
    assert (flag["fix"], flag["fix_action"]) == ("Remove one copy to keep the other.", "skill.remove")
    definitions = client.get("/api/explain?name=docker-expert&kind=skill").json()["definitions"]
    assert [d["source"] for d in definitions if "skill.remove" in d["actions"]] == [
        str(client.home / ".agents/skills/docker-expert/SKILL.md"),
        str(client.home / ".codex/skills/docker-expert/SKILL.md"),
    ]
    own = _skill_item(client, "codex", "docker-expert", where=str(client.home / ".codex/skills/docker-expert"))
    change = _remove(client, own["id"]).json()
    # Cursor reads ~/.codex/skills too (Include Third-Party Plugins is on in the fixture).
    assert change["after"] == [{"client": "codex", "state": "off", "word": "Removed"}, {"client": "cursor", "state": "off", "word": "Removed"}]
    client.post(f"/api/changes/{change['id']}/apply", headers=POST)
    row = next(r for r in client.get("/api/library?kind=skill").json()["rows"] if r["name"] == "docker-expert")
    assert not [f for f in row["flags"] if f["level"] == "warning"]


def test_a_project_skill_removal_names_the_project(client):
    site = _skill_item(client, "claude_code", "site-style")
    change = _remove(client, site["id"]).json()
    assert (change["steps"][0]["scope"], change["shared_file_warning"]) == ("project", True)
    assert client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
    assert client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
```

`_skill_item(client, who, name, where=None)` picks the skill item of that client and name, and by `source` path when `where` is given.

`tests/frontend/panel.test.mjs`: `changeWords({ action: 'skill.remove', steps: [{ client: 'codex', name: 'tidy', reaches: ['codex', 'cursor'] }] })` → title `'Remove tidy from Codex and Cursor'`, done `'Removed tidy from Codex and Cursor'`. `tests/frontend/parts.test.mjs`: `changeTitle({ action: 'skill.remove', steps: [{ client: 'codex', name: 'tidy', reaches: ['codex', 'cursor'] }] })` → `'Removed tidy · Codex, Cursor'`. `tests/unit/test_load_map.py`: the skill duplicate flag carries the fix and `skill.remove`. `tests/unit/test_page_words.py` `test_details_offer_remove_for_plugins_and_skills`: add that `panel.js` contains `'"skill.remove": (client) => \`Remove from ${client}…\`'`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/unit/test_engine.py tests/unit/test_remove_skill.py -v -k "removal or remove or link or came_back"` and `node --test tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs`
Expected: FAIL: `FolderRemoval` does not exist; the action is not offered.

- [ ] **Step 3: Implement the model, the store and the engine**

`model.py`: the constant, the dataclass (docstring: the folder is copied into the change's backup folder first; Undo copies it back only when nothing is at the path) and `Step.removal`. `backup.py`: `backup_folder` (the change folder is 0700; `copy_folder` keeps file modes). `engine.py`: records (`"removal": dict(removal.__dict__)` and `FolderRemoval(**r)` back), `_step_path`, `_preview_removals`, `_stale_removal`, `_apply_removal`, the restore branch in `apply`'s `except`, the two `UNDO_BLOCKED` cases and the copy back in `undo`, `_log`'s `reaches`. Apply order: gateway → copies → removals → file steps; Undo order: gateway → copies removed → removals copied back → inverse commands → files.

- [ ] **Step 4: Implement the action and the words**

`base.py`: `SKILL_REMOVE`, `skill_remove_step`. The three adapters' `item_actions` skill branch (the rule in Interfaces; Cursor's own `.cursor/skills` items qualify, its `"shared"` and other-client items do not). `skills.py`: `skill_readers`. `actions.py`: `skill_remove_steps` (`SKILL_REMOVE` in `item.actions`, else `ValueError(f"{item.name} cannot be removed here")`). `app.py`: dispatch `SKILL_REMOVE` with one item, `readers = skill_readers(state.inventory, item)`; `_step_path` and `change_dict["reaches"]` read `removal` too. `load_map.py`: the skill fix. `after.py`: `_skill_remove_words` returns one `{"client", "state": "off", "word": "Removed"}` per reader, in `SKILL_CLIENTS` order. `panel.js`, `parts.js`: the words.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/unit/test_engine.py tests/unit/test_remove_skill.py tests/unit/test_actions.py tests/unit/test_load_map.py tests/unit/test_page_words.py tests/security -v` and `node --test tests/frontend/*.test.mjs`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/kitden/model.py src/kitden/changes/backup.py src/kitden/changes/engine.py src/kitden/clients/base.py src/kitden/clients/claude_code.py src/kitden/clients/codex.py src/kitden/clients/cursor.py src/kitden/views/skills.py src/kitden/views/load_map.py src/kitden/changes/actions.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/panel.js src/kitden/web/static/js/parts.js tests/unit/test_engine.py tests/unit/test_remove_skill.py tests/unit/test_actions.py tests/unit/test_load_map.py tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs
git commit -m "Library: remove a skill with Undo"
```

---

### Task 3: Remove a server from the Kitden gateway, and put it back in a client (3.3)

**Files:**
- Create: `src/kitden/changes/server_entry.py` (`translate_entry`, plain entries only; Task 4 adds references)
- Modify: `src/kitden/clients/base.py:256-262` (new `add_server_step` default); `claude_code.py:194-215`, `codex.py:264-281`, `cursor.py:110-127` (`add_server_step` on `_add_entry`)
- Modify: `src/kitden/local_gateway/settings.py:185-190` (after `settings_step`: `remove_server_steps`)
- Modify: `src/kitden/changes/actions.py:389-391` (`GATEWAY_REMOVE`, `GATEWAY_PUT_BACK`), after `local_move_steps`: `put_back_steps`, `_refuse_if_present`
- Modify: `src/kitden/web/app.py:835-837` (dispatch after `GATEWAY_RULE`)
- Modify: `src/kitden/views/after.py` (`_gateway_remove_words`, `_put_back_words`, `home_path`)
- Modify: `src/kitden/web/static/js/panel.js:494-555` (`showDetails`: the held server's footer), `611-670` (words), new `heldActions`
- Modify: `src/kitden/web/static/js/gateway.js:317-327` (`showKitdenServer`: the same footer); `parts.js:212-263`
- Create: `tests/unit/test_server_entry.py`, `tests/unit/test_gateway_remove.py`
- Test: `tests/frontend/panel.test.mjs`, `tests/frontend/parts.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `settings_step`, `load_settings`, `state_in` (`settings.py`); `_raw_entry` (`actions.py:285-298`); `redact`; `hold`, `add_kitden`, `page_for`, `tool`, `FILES` from `tests/unit/test_local_gateway_views.py`; `FakeClaude` from `tests/unit/test_api_changes.py`; `_offering` (`after.py:188-194`). Later: Part 5's `resolve_entry(entry)`; until it exists `put_back_steps` passes the held entry as it is, and a non-string value (a reference) fails `translate_entry`'s shape check with "The entry could not be read."
- Produces: `translate_entry(entry: dict, client: str) -> dict` (`server_entry.py`): the entry as the target client writes it. In this task it takes a held entry (`command`, `args`, `env` or `url`, `headers`, plus `startup_timeout_sec`, no references): `claude_code` → `{"type": "stdio", command, args, env}` or `{"type": "http", url, headers}`; `codex` → `{command, args, env}` or `{url, "http_headers": headers}`, keeping `startup_timeout_sec`; `cursor` → the six fields as they are; an unknown client raises `ValueError(f"{client} cannot take an MCP entry")`; a value of the wrong shape (`command` not a string, `args` not a list of strings, `env`/`headers` not a dict of strings) raises `ValueError("The entry could not be read.")`; the source's `type` is dropped (Claude Code's is set from the fields). `ClientAdapter.add_server_step(name: str, entry: dict) -> Step` = `self._add_entry(name, entry)` in each adapter (base raises `ValueError(f"{self.id} cannot take an MCP entry")`). `remove_server_steps(home: Path, server: str) -> list[Step]` (`settings.py`): `settings_step(home, ("servers", server), ABSENT, server)`, then `("rules", "global", server)` when that key exists, then `("rules", "projects", <project>, server)` for every project whose rules hold the server; raises `ValueError("Choose a server in the Kitden gateway.")` when not held. `GATEWAY_REMOVE = "gateway.remove"` (params `{"server": str}`, no targets) and `GATEWAY_PUT_BACK = "gateway.put_back"` (targets `[{"client": str}]`, params `{"server": str}`). `put_back_steps(adapters, home: Path, server: str, clients: list[str]) -> list[Step]`: one `add_server_step(server, translate_entry(held, client))` per client, each checked by `_refuse_if_present(step, client, name)` which raises `ValueError(f"{CLIENT_WORDS[client]} already has {name}.")` when `_raw_entry(step)` is not None; `"Choose at least one client"` with no clients. Review words: `gateway.remove` → one entry `{"client", "state": "off", "word": "Removed"}` per client whose `kitden` entry is on (`_offering`), the first with `"note": f"{server} is then in no client. Undo brings it back."`; with no such client, `[{"note": …}]` alone. `gateway.put_back` → one entry per step `{"client", "state": "on", "word": "Loads"}`, with a note made of, in this order, `f"This writes a secret into {home_path(path, home)}."` when `redact(step.edit.after)[1]` is true, and `f"{Client} then loads {server} twice: directly and through the Kitden gateway. Remove it from the gateway to keep one."` when that client offers the gateway and `state_in(settings, [], server, None) == "on"`. `home_path(path: str, home: Path) -> str` gives `~/.claude.json` for a path under home, else the path. Page: `export function heldActions(server, clients)` in `panel.js` returns `[{ label: "Remove from the Kitden gateway…", body: { action: "gateway.remove", targets: [], params: { server } } }, …one per client: { label: \`Put back in ${CLIENT_NAMES[client]}…\`, body: { action: "gateway.put_back", targets: [{ client }], params: { server } } }]`; both Details draw them as plain buttons (`footerButtons({ lead: null, rest }, …)`) that call `review(body)`; `clients` are the found writable clients (`data.clients`, as `gateway.js` `foundClients()` reads them). `changeWords`: `gateway.remove` → title `Remove ${server} from the Kitden gateway`, done `Removed ${server} from the Kitden gateway`; `gateway.put_back` → title `Put ${server} back in ${clients}`, done `Put ${server} back in ${clients}`; `server` is `previewBody.params.server`, else `change.steps[0].name`. `ACTION_WORDS`: `"gateway.remove": "Removed from the Kitden gateway"`, `"gateway.put_back": "Put back"`; `changeTitle` for `gateway.remove` is `Removed ${steps[0].name} from the Kitden gateway`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_server_entry.py`:

```python
FILES = {"command": "npx", "args": ["files-mcp"], "env": {"FILES_TOKEN": "SENTINEL_SECRET_FILES"}}
REMOTE = {"url": "https://api.invalid/mcp", "headers": {"Authorization": "Bearer SENTINEL_SECRET_R"}}


def test_a_held_local_entry_in_each_client():
    assert translate_entry(FILES, "claude_code") == {"type": "stdio", **FILES}
    assert translate_entry(FILES, "codex") == FILES
    assert translate_entry(FILES, "cursor") == FILES
    waits = {**FILES, "startup_timeout_sec": 45}
    assert translate_entry(waits, "codex") == waits
    assert translate_entry(waits, "claude_code") == {"type": "stdio", **FILES}
    assert translate_entry(waits, "cursor") == FILES


def test_a_held_remote_entry_in_each_client():
    assert translate_entry(REMOTE, "claude_code") == {"type": "http", **REMOTE}
    assert translate_entry(REMOTE, "codex") == {"url": REMOTE["url"], "http_headers": REMOTE["headers"]}
    assert translate_entry(REMOTE, "cursor") == REMOTE


def test_a_wrong_shape_or_client_is_refused():
    with pytest.raises(ValueError, match="^The entry could not be read.$"):
        translate_entry({"command": "npx", "env": {"KEY": {"keychain": "files/KEY"}}}, "codex")
    with pytest.raises(ValueError, match="cannot take an MCP entry"):
        translate_entry(FILES, "claude_desktop_code_tab")
```

`tests/unit/test_gateway_remove.py` (helpers imported from `tests/unit/test_local_gateway_views.py`; `page_for(home, run=FakeClaude(home))`; `website = str(home / "work/website")`):

```python
def test_removing_a_held_server_takes_its_rules_and_undo_restores(home):
    rules = {"global": {"files": {"server": "off", "tools": {"search": "off"}}, "other": {"server": "on"}},
             "projects": {website: {"files": {"server": "on"}}}}
    hold(home, {"files": FILES, "other": {"command": "x"}}, rules)
    save_tools(home, "files", [tool("search")])
    add_kitden(home, "claude_code", "cursor")
    path = data_dir(home) / SETTINGS_FILE
    before = path.read_bytes()
    with page_for(home) as page:
        answer = page.post("/api/changes/preview", json={"action": "gateway.remove", "targets": [], "params": {"server": "files"}}, headers=POST)
        assert answer.status_code == 200, answer.json()
        change = answer.json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [("kitden", "files")] * 3
        assert [s["diff"].splitlines()[0] for s in change["steps"]] == [
            "servers > files", "rules > global > files", f"rules > projects > {website} > files",
        ]
        assert "SENTINEL" not in answer.text
        assert change["after"] == [
            {"client": "claude_code", "state": "off", "word": "Removed", "note": "files is then in no client. Undo brings it back."},
            {"client": "cursor", "state": "off", "word": "Removed"},
        ]
        assert page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
        saved = load_settings(home)
        assert saved["servers"] == {"other": {"command": "x"}}
        assert saved["rules"] == {"global": {"other": {"server": "on"}}, "projects": {website: {}}}
        assert "files" in load_tools(home)  # found data stays
        rows = page.get("/api/library?kind=mcp_server").json()["rows"]
        assert not any(r["name"] == "files" for r in rows)
        assert page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    assert path.read_bytes() == before


def test_removing_without_a_connected_client_only_has_the_note(home):
    hold(home, {"files": FILES})
    with page_for(home) as page:
        change = page.post("/api/changes/preview", json={"action": "gateway.remove", "targets": [], "params": {"server": "files"}}, headers=POST).json()
    assert change["after"] == [{"note": "files is then in no client. Undo brings it back."}]


def test_removing_an_unknown_server_is_refused(home):
    with page_for(home) as page:
        answer = page.post("/api/changes/preview", json={"action": "gateway.remove", "targets": [], "params": {"server": "nope"}}, headers=POST)
    assert (answer.status_code, answer.json()["detail"]) == (422, "Choose a server in the Kitden gateway.")


def _put_back(page, server, *clients):
    body = {"action": "gateway.put_back", "targets": [{"client": c} for c in clients], "params": {"server": server}}
    return page.post("/api/changes/preview", json=body, headers=POST)


def test_putting_a_server_back_writes_the_clients_entry_and_says_about_the_secret(home):
    hold(home, {"files": {**FILES, "startup_timeout_sec": 45}})
    add_kitden(home, "claude_code")
    original = (home / ".claude.json").read_bytes()
    with page_for(home, run=FakeClaude(home)) as page:
        change = _put_back(page, "files", "claude_code").json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [("claude_code", "files")]
        assert change["steps"][0]["command"].startswith("claude mcp add-json -s user files ")
        assert "[secret]" in change["steps"][0]["diff"] and "SENTINEL" not in json.dumps(change)
        assert change["after"] == [{
            "client": "claude_code", "state": "on", "word": "Loads",
            "note": "This writes a secret into ~/.claude.json. Claude Code then loads files twice: "
                    "directly and through the Kitden gateway. Remove it from the gateway to keep one.",
        }]
        assert page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
        assert json.loads((home / ".claude.json").read_text())["mcpServers"]["files"] == {"type": "stdio", **FILES}
        assert load_settings(home)["servers"]["files"] == {**FILES, "startup_timeout_sec": 45}
        assert "SENTINEL" not in page.get("/api/changes").text
        assert page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    assert (home / ".claude.json").read_bytes() == original


def test_put_back_in_codex_and_cursor_keeps_each_clients_shape(home):
    hold(home, {"files": {**FILES, "startup_timeout_sec": 45}, "api": {"url": "https://api.invalid/mcp", "headers": {"X": "1"}}})
    with page_for(home) as page:
        codex = _put_back(page, "files", "codex").json()
        assert "http_headers" not in codex["steps"][0]["diff"]  # a local entry: command, args, env
        assert page.post(f"/api/changes/{codex['id']}/apply", headers=POST).json()["state"] == "verified"
        assert tomllib.loads((home / ".codex/config.toml").read_text())["mcp_servers"]["files"] == {**FILES, "startup_timeout_sec": 45}
        cursor = _put_back(page, "api", "cursor").json()
        assert "note" not in cursor["after"][0]  # no secret, no kitden entry in Cursor
        assert page.post(f"/api/changes/{cursor['id']}/apply", headers=POST).json()["state"] == "verified"
        assert json.loads((home / ".cursor/mcp.json").read_text())["mcpServers"]["api"] == {"url": "https://api.invalid/mcp", "headers": {"X": "1"}}


def test_put_back_is_refused_when_the_client_has_the_name(home):
    hold(home, {"github": {"url": "https://api.githubcopilot.com/mcp/"}})
    before = (home / ".claude.json").read_bytes()
    with page_for(home) as page:
        answer = _put_back(page, "github", "claude_code")
    assert (answer.status_code, answer.json()["detail"]) == (422, "Claude Code already has github.")
    assert (home / ".claude.json").read_bytes() == before
```

For `api` put back in Codex (add one more preview in the same test), assert `"http_headers" in diff`.

`tests/frontend/panel.test.mjs`:

```js
test('a held server offers Remove and Put back in each found client', () => {
  const actions = heldActions('files', ['claude_code', 'cursor']);
  assert.deepEqual(actions.map((a) => a.label), ['Remove from the Kitden gateway…', 'Put back in Claude Code…', 'Put back in Cursor…']);
  assert.deepEqual(actions[0].body, { action: 'gateway.remove', targets: [], params: { server: 'files' } });
  assert.deepEqual(actions[2].body, { action: 'gateway.put_back', targets: [{ client: 'cursor' }], params: { server: 'files' } });
});
test('removing from or putting back from the Kitden gateway is named', () => {
  const remove = { action: 'gateway.remove', steps: [{ client: 'kitden', name: 'files' }, { client: 'kitden', name: 'files' }] };
  assert.deepEqual(changeWords(remove, { params: { server: 'files' } }), { title: 'Remove files from the Kitden gateway', done: 'Removed files from the Kitden gateway' });
  const back = { action: 'gateway.put_back', steps: [{ client: 'claude_code', name: 'files', restart_note: 'Start a new Claude Code session (or a new Code tab chat) for this to take effect.' }] };
  assert.deepEqual(changeWords(back, { params: { server: 'files' } }), { title: 'Put files back in Claude Code', done: 'Put files back in Claude Code · Start a new Claude Code session (or a new Code tab chat)' });
});
```

`tests/frontend/parts.test.mjs`: `changeTitle({ action: 'gateway.remove', steps: [{ client: 'kitden', name: 'files' }] })` → `'Removed files from the Kitden gateway'`; `changeTitle({ action: 'gateway.put_back', steps: [{ client: 'codex', name: 'files' }] })` → `'Put back files · Codex'`.

`tests/unit/test_page_words.py`: `test_a_held_server_can_be_removed_or_put_back`: `panel.js` contains `"Remove from the Kitden gateway…"` and `` `Put back in ${CLIENT_NAMES[client]}…` ``; `gateway.js` contains `heldActions(`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/unit/test_server_entry.py tests/unit/test_gateway_remove.py -v` and `node --test tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs`
Expected: FAIL: no module `server_entry`; the actions are not offered; `heldActions` is not exported.

- [ ] **Step 3: Implement `translate_entry` and `add_server_step`**

`server_entry.py`: a module docstring that names the three formats (checked dates come in Task 4); `translate_entry` as the interface says, with one private `_shape(entry) -> dict` that checks the six fields' types. The three adapters: `add_server_step` returns `self._add_entry(name, entry)`.

- [ ] **Step 4: Implement the removal, the put back and the words**

`settings.py`: `remove_server_steps`. `actions.py`: the two constants, `_refuse_if_present`, `put_back_steps`. `app.py`: `GATEWAY_REMOVE` → `remove_server_steps(home, str(params.get("server", "")))`; `GATEWAY_PUT_BACK` → `put_back_steps(adapters, home, server, clients)`. `after.py`: `home_path`, `_gateway_remove_words`, `_put_back_words`, chosen in `after_words` by action. `panel.js`: `heldActions`, the footer in `showDetails` when `definitions.some((d) => d.via_gateway === "kitden")`, the words in `changeWords` (`DONE_WORDS` gets `"gateway.remove": "Removed"`, `"gateway.put_back": "Put"`; the `gateway.remove` branch drops the client list). `gateway.js` `showKitdenServer`: the same footer through `openInfo(…, actions)`. `parts.js`: `ACTION_WORDS` and the `changeTitle` branch.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/unit/test_server_entry.py tests/unit/test_gateway_remove.py tests/unit/test_page_words.py tests/security -v` and `node --test tests/frontend/*.test.mjs`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/kitden/changes/server_entry.py src/kitden/clients/base.py src/kitden/clients/claude_code.py src/kitden/clients/codex.py src/kitden/clients/cursor.py src/kitden/local_gateway/settings.py src/kitden/changes/actions.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/panel.js src/kitden/web/static/js/gateway.js src/kitden/web/static/js/parts.js tests/unit/test_server_entry.py tests/unit/test_gateway_remove.py tests/unit/test_page_words.py tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs
git commit -m "Gateway: remove a held server, or put it back in a client"
```

---

### Task 4: Add an MCP server to another client (3.4)

**Files:**
- Modify: `src/kitden/changes/server_entry.py` (references, the other clients' key forms, refusals)
- Modify: `src/kitden/changes/actions.py:389-391` (`MCP_ADD`), after `put_back_steps`: `add_server_steps`
- Modify: `src/kitden/views/library.py:46-61` (`_add`: `item`), `110-126` (`_map_rows`: an `add` builder), `129-166` (`_server_why`: an add wins over the share reason), new `_server_add`, `496-505` (`library()`)
- Modify: `src/kitden/web/app.py:849-861` (dispatch)
- Modify: `src/kitden/views/after.py` (`_add_server_words`)
- Modify: `src/kitden/web/static/js/library.js:62-66` (`previewFor`), `panel.js:611-670`, `parts.js:212-226`
- Modify: `tests/security/test_no_secrets.py:80-105` (`_page_outputs`: an `mcp.add` of github into Codex, applied and undone)
- Create: `tests/unit/test_add_server.py`
- Test: `tests/unit/test_server_entry.py`, `tests/unit/test_library.py:507-519` (`test_a_server_dash_says_how_the_gateway_would_share_it`), `tests/frontend/library.test.mjs`, `tests/frontend/panel.test.mjs`, `tests/frontend/parts.test.mjs`

**Interfaces:**
- Consumes: `translate_entry`, `add_server_step`, `_refuse_if_present` (Task 3); `remove_steps`, `_raw_entry`, `FROM_ELSEWHERE`, `SETUP_NAME` (`actions.py`); `is_direct_entry` (`base.py`); `add_claude`, `add_codex`, `add_cursor` from `tests/unit/test_local_gateway_move.py`; `FakeClaude` from `tests/unit/test_api_changes.py`.
- Produces: `translate_entry` now takes an entry in any client's format. Rules, in this order (each refusal is a `ValueError` with exactly these words):
  1. `envFile`, `http_headers_helper`, `headersHelper` present → "The entry reads values from a file or a helper program; put the values in."
  2. `enabled` is `False` → "The entry is turned off; turn it on first." `enabled_tools` or `disabled_tools` present → "The entry keeps some tools off. Move it into the gateway to share it with its switches."
  3. `type` `sse` or `ws` (or no `type` and the url ends in `/sse`) → for `codex` and `cursor`: `f"{Client} cannot use an SSE connection from here."` / `"… a WebSocket connection …"`; `claude_code` keeps `type`.
  4. `cwd` → for `claude_code` and `cursor`: `f"{Client} has no setting for a start folder."`; `codex` keeps it.
  5. The source is read into the canonical shape: `headers` from `headers` or `http_headers`; Codex's `bearer_token_env_var: "V"` → `headers["Authorization"] = "Bearer ${V}"`; `env_http_headers: {"H": "V"}` → `headers["H"] = "${V}"`; `env_vars: ["V"]` → `env["V"] = "${V}"`; Cursor's `${env:V}` → `${V}`. `startup_timeout_sec` and `tool_timeout_sec` are kept for `codex` only; `type`, `enabled` (`True`) are dropped; any other key → `f"Kitden does not know the setting {key}."`
  6. References (`${V}` and `${V:-default}`) in the target: `claude_code` keeps them as they are; `cursor` writes `${env:V}` (a `:-default` form is refused); `codex` writes `bearer_token_env_var` for `Authorization: Bearer ${V}`, `env_http_headers` for a header whose whole value is `${V}`, `env_vars` for an env value `${V}` under the key `V`; any other reference (in `command`, `args`, `url`, a header or env value with text around it, an env key that differs) is refused with `f"{Client} cannot read `${{V}}` from your shell; put the value in."` (the literal text is, for example, ``Codex cannot read `${TOKEN}` from your shell; put the value in.``).
  `MCP_ADD = "mcp.add"` (targets `[{"client": str}]`, params `{"item": str}`). `add_server_steps(adapters, item: Item, clients: list[str]) -> list[Step]`: refuses `item.scope in (PROJECT, LOCAL)` with "It is already per project; copy the file into the project instead.", `item.name == SETUP_NAME` with "Kitden's own entry stays in each client.", `item.via_gateway` or `REMOVE_DIRECT not in item.actions` with `f"{item.name} is not a direct entry."`, an unreadable entry with `f"{item.name} could not be read from its file."`, no clients with "Choose at least one client"; reads the entry with `_raw_entry(remove_steps(adapters, item)[0])`, then per client `add_server_step(item.name, translate_entry(entry, client))` checked by `_refuse_if_present`. Library: `_add(..., item: str | None = None)`; for an MCP row, a found writable client whose cell is `"none"` gets `_add(MCP_ADD, "+ Add", item=<source item id>)` when the row has a source: a loaded item (cell state `"on"`) that is a user-scope direct entry (`is_direct_entry(i, i.client, {Scope.USER})`, `via_gateway is None`, `name != SETUP_NAME`), the first in `COLUMNS` order; a row with any `"gw"` cell has no add; the add replaces the `SHARE_IN_GATEWAY` reason (the "Connect … to the gateway" reason stays for rows a gateway serves). Review words: one entry per step `{"client", "state": "on", "word": "Loads"}`, with `"note": f"This makes a second copy of a secret in {home_path(path, home)}."` when `redact(step.edit.after)[1]`. Page: `previewFor` for `mcp.add` sends `params: { item: add.item }`; `changeWords` `mcp.add` → title `Add ${names} to ${clients}`, done `Added ${short} to ${clients}`; `ACTION_WORDS["mcp.add"] = "Added"`.

- [ ] **Step 1: Check the three clients' docs and write the dates**

In `server_entry.py`'s docstring, one line per client with `checked YYYY-MM-DD`: Claude Code (code.claude.com/docs/en/mcp, "Environment variable expansion"): the `${VAR}` and `${VAR:-default}` forms, the fields they work in, and whether they work in user-scope entries added with `claude mcp add-json`, not only in `.mcp.json` — if user scope does not expand them, rule 6 refuses references for `claude_code` with the same wording and the tests below flip to that. Cursor (cursor.com/docs/context/mcp): the `${env:VAR}` form and the fields it works in (`env`, `headers`, `args`, `url`); a field it does not expand is a refusal. Codex (developers.openai.com/codex/mcp, config reference): `bearer_token_env_var`, `env_http_headers`, `env_vars`, `http_headers`, `cwd`, and that a remote server is streamable HTTP only (rule 3). Write each fact and its date in the docstring; where a fact differs from the rules above, change the rule and the test together in this task.

- [ ] **Step 2: Write the failing tests**

`tests/unit/test_server_entry.py`, added:

```python
API = {"type": "http", "url": "https://api.invalid/mcp", "headers": {"Authorization": "Bearer ${API_KEY}"}}


def test_a_reference_is_kept_where_the_client_can_read_it():
    assert translate_entry(API, "claude_code") == API
    assert translate_entry(API, "cursor") == {"url": API["url"], "headers": {"Authorization": "Bearer ${env:API_KEY}"}}
    assert translate_entry(API, "codex") == {"url": API["url"], "bearer_token_env_var": "API_KEY"}
    other = {"url": API["url"], "headers": {"X-Key": "${X_KEY}"}}
    assert translate_entry(other, "codex") == {"url": API["url"], "env_http_headers": {"X-Key": "X_KEY"}}
    env = {"command": "npx", "args": ["x"], "env": {"HOME_TOKEN": "${HOME_TOKEN}"}}
    assert translate_entry(env, "codex") == {"command": "npx", "args": ["x"], "env_vars": ["HOME_TOKEN"]}
    assert translate_entry(env, "cursor") == {"command": "npx", "args": ["x"], "env": {"HOME_TOKEN": "${env:HOME_TOKEN}"}}


def test_a_reference_the_client_cannot_read_is_refused_with_the_spec_words():
    shelled = {"command": "npx", "args": ["x", "${TOKEN}"]}
    with pytest.raises(ValueError, match=r"^Codex cannot read `\$\{TOKEN\}` from your shell; put the value in\.$"):
        translate_entry(shelled, "codex")
    with pytest.raises(ValueError, match=r"^Cursor cannot read `\$\{TOKEN:-x\}` from your shell; put the value in\.$"):
        translate_entry({"url": "https://a.invalid/mcp", "headers": {"A": "${TOKEN:-x}"}}, "cursor")
    with pytest.raises(ValueError, match=r"^Codex cannot read `\$\{OTHER\}` from your shell"):
        translate_entry({"command": "npx", "env": {"KEY": "${OTHER}"}}, "codex")


def test_the_other_clients_forms_are_read_into_the_canonical_shape():
    codex = {"url": "https://t.invalid/mcp", "bearer_token_env_var": "TOKEN", "env_http_headers": {"X": "X_KEY"}}
    assert translate_entry(codex, "claude_code") == {"type": "http", "url": codex["url"], "headers": {"Authorization": "Bearer ${TOKEN}", "X": "${X_KEY}"}}
    assert translate_entry({"command": "npx", "env_vars": ["HOME_TOKEN"]}, "claude_code") == {"type": "stdio", "command": "npx", "env": {"HOME_TOKEN": "${HOME_TOKEN}"}}
    cursor = {"command": "npx", "env": {"KEY": "${env:KEY}"}}
    assert translate_entry(cursor, "claude_code") == {"type": "stdio", "command": "npx", "env": {"KEY": "${KEY}"}}
    assert translate_entry(cursor, "codex") == {"command": "npx", "env_vars": ["KEY"]}


@pytest.mark.parametrize("entry, client, words", [
    ({"command": "npx", "envFile": "/opt/app/.env"}, "codex", "The entry reads values from a file or a helper program; put the values in."),
    ({"command": "uv", "args": ["run"], "enabled": False}, "claude_code", "The entry is turned off; turn it on first."),
    ({"command": "uv", "enabled_tools": ["draw"]}, "cursor", "The entry keeps some tools off. Move it into the gateway to share it with its switches."),
    ({"type": "sse", "url": "https://s.invalid/sse"}, "codex", "Codex cannot use an SSE connection from here."),
    ({"command": "npx", "cwd": "/opt/app"}, "cursor", "Cursor has no setting for a start folder."),
    ({"command": "npx", "mystery": 1}, "codex", "Kitden does not know the setting mystery."),
])
def test_what_cannot_be_copied_is_refused_with_the_reason(entry, client, words):
    with pytest.raises(ValueError, match=f"^{re.escape(words)}$"):
        translate_entry(entry, client)
    assert translate_entry({"type": "sse", "url": "https://s.invalid/sse"}, "claude_code")["type"] == "sse"
    assert translate_entry({"command": "npx", "cwd": "/opt/app"}, "codex") == {"command": "npx", "cwd": "/opt/app"}
```

`tests/unit/test_add_server.py` (fixture `page`: the three clients, `page_for(home, run=FakeClaude(home))` from `test_gateway_remove.py`; `_add(page, item_id, *clients)` posts `{"action": "mcp.add", "targets": [{"client": c} …], "params": {"item": item_id}}`; `_item(page, who, name, scope="user")` from `/api/items?kind=mcp_server`):

```python
def test_the_library_offers_add_for_a_direct_server_another_client_lacks(home):
    with page_for(home) as page:
        rows = {r["name"]: r for r in page.get("/api/library?kind=mcp_server").json()["rows"]}
        github = _item(page, "claude_code", "github")["id"]
        for client in ("codex", "cursor"):
            add = rows["github"]["cells"][client]["add"]
            assert (add["action"], add["label"], add["item"]) == ("mcp.add", "+ Add", github)
            assert rows["github"]["cells"][client]["reason"] is None
        n8n = _item(page, "cursor", "n8n-mcp")["id"]  # a local server is copied too
        assert rows["n8n-mcp"]["cells"]["claude_code"]["add"]["item"] == n8n
        assert rows["docs"]["cells"]["codex"]["add"] is None if "docs" in rows else True  # a project entry (shown in a project view only) gets no add


def test_adding_a_server_to_another_client_previews_applies_and_undoes(home):
    config = home / ".codex/config.toml"
    before = config.read_bytes()
    with page_for(home) as page:
        change = _add(page, _item(page, "claude_code", "github")["id"], "codex").json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [("codex", "github")]
        assert "http_headers" in change["steps"][0]["diff"] and "[secret]" in change["steps"][0]["diff"]
        assert "SENTINEL" not in json.dumps(change)
        assert change["after"] == [{"client": "codex", "state": "on", "word": "Loads",
                                    "note": "This makes a second copy of a secret in ~/.codex/config.toml."}]
        assert page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
        text = config.read_text()
        assert tomllib.loads(text)["mcp_servers"]["github"] == {
            "url": "https://api.githubcopilot.com/mcp/",
            "http_headers": {"Authorization": "Bearer SENTINEL_SECRET_GITHUB"},
        }
        assert "# Owner comment: keep me" in text
        rows = {r["name"]: r for r in page.get("/api/library?kind=mcp_server").json()["rows"]}
        assert rows["github"]["cells"]["codex"]["state"] == "on"
        assert page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    assert config.read_bytes() == before


def test_a_codex_entry_goes_to_claude_code_with_its_type(home):
    with page_for(home, run=FakeClaude(home)) as page:
        change = _add(page, _item(page, "codex", "neon")["id"], "claude_code", "cursor").json()
        assert change["steps"][0]["command"] == 'claude mcp add-json -s user neon {"type": "http", "url": "https://mcp.neon.tech/mcp"}'
        assert "note" not in change["after"][0]  # no secret in it
        assert page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
        assert json.loads((home / ".cursor/mcp.json").read_text())["mcpServers"]["neon"] == {"url": "https://mcp.neon.tech/mcp"}
        assert page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"


def test_a_reference_is_kept_or_refused(home):
    add_claude(home, "api", {"type": "http", "url": "https://api.invalid/mcp", "headers": {"Authorization": "Bearer ${API_KEY}"}})
    add_claude(home, "shelled", {"type": "stdio", "command": "npx", "args": ["x", "${TOKEN}"]})
    with page_for(home) as page:
        change = _add(page, _item(page, "claude_code", "api")["id"], "codex").json()
        assert "bearer_token_env_var" in change["steps"][0]["diff"]
        refused = _add(page, _item(page, "claude_code", "shelled")["id"], "codex")
        assert (refused.status_code, refused.json()["detail"]) == (422, "Codex cannot read `${TOKEN}` from your shell; put the value in.")


def test_project_entries_and_kitdens_own_entry_are_refused(home):
    add_kitden(home, "claude_code")
    with page_for(home) as page:
        docs = _item(page, "claude_code", "docs", scope="project")
        answer = _add(page, docs["id"], "codex")
        assert (answer.status_code, answer.json()["detail"]) == (422, "It is already per project; copy the file into the project instead.")
        local = _item(page, "claude_code", "local-db", scope="local")
        assert _add(page, local["id"], "codex").json()["detail"] == "It is already per project; copy the file into the project instead."
        kitden = _item(page, "claude_code", "kitden")
        assert _add(page, kitden["id"], "codex").json()["detail"] == "Kitden's own entry stays in each client."


def test_a_name_the_client_has_is_refused(home):
    add_cursor(home, "github", {"url": "https://other.invalid/mcp"})
    before = (home / ".cursor/mcp.json").read_bytes()
    with page_for(home) as page:
        answer = _add(page, _item(page, "claude_code", "github")["id"], "cursor")
    assert (answer.status_code, answer.json()["detail"]) == (422, "Cursor already has github.")
    assert (home / ".cursor/mcp.json").read_bytes() == before
```

`tests/unit/test_library.py` `test_a_server_dash_says_how_the_gateway_would_share_it`: `reasons["github"]` becomes `{"codex": None, "cursor": None}` and `reasons["langfuse-data"]["cursor"]` is `None`; add `adds = {...}` built like `_server_reasons` from `cell["add"]` and assert `adds["github"] == {"codex": "mcp.add", "cursor": "mcp.add"}` and `adds["neon"]["claude_code"] is None` (Claude Code is offered "Connect … to the gateway", not a copy).

`tests/frontend/library.test.mjs`: `assert.deepEqual(previewFor(add({ action: 'mcp.add', item: 'item-1' }), 'codex'), { action: 'mcp.add', targets: [{ client: 'codex' }], params: { item: 'item-1' } });` (extend the `add` helper with `item: null`); the cell's aria-label for `{ kind: 'mcp_server', name: 'github' }` is `'Add github to Codex'`. `panel.test.mjs`: `changeWords({ action: 'mcp.add', steps: [{ client: 'codex', name: 'github' }] })` → `{ title: 'Add github to Codex', done: 'Added github to Codex' }`. `parts.test.mjs`: `changeTitle({ action: 'mcp.add', steps: [{ client: 'codex', name: 'github' }] })` → `'Added github · Codex'`.

`tests/security/test_no_secrets.py` `_page_outputs`: after the removals, preview `mcp.add` of Claude Code's `github` into `codex`, apply and undo it, so a leak of `SENTINEL_SECRET_GITHUB` through the new diff, the log or the manifest would be caught.

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/unit/test_server_entry.py tests/unit/test_add_server.py tests/unit/test_library.py -v` and `node --test tests/frontend/*.test.mjs`
Expected: FAIL: references are refused as a wrong shape; the action is not offered; no `add` on MCP cells.

- [ ] **Step 4: Implement `translate_entry`'s rules**

In `server_entry.py`, two private steps: `_canonical(entry: dict) -> dict` (rules 1, 2, 5: refusals, the Codex and Cursor forms into `${V}`, the kept extras under a `_keep` key for `codex`) and `_render(canonical: dict, client: str) -> dict` (rules 3, 4, 6). The reference pattern is `re.compile(r"\$\{(env:)?([A-Za-z_][A-Za-z0-9_]*)(:-[^}]*)?\}")`. A whole-value reference means the regex matches the whole string; `Bearer ${V}` is the only partial form Codex takes (as `bearer_token_env_var`).

- [ ] **Step 5: Implement the action, the cells and the words**

`actions.py`: `MCP_ADD`, `add_server_steps`. `app.py`: dispatch (`item` from params, clients from targets). `library.py`: `_add(..., item=None)`, `_server_add(found, items) -> Callable[[Row, str], dict | None]`, `_map_rows(..., add=None)` sets `cell["add"]` before asking `why` and asks `why` only without an add. `after.py`: `_add_server_words`. `library.js`, `panel.js`, `parts.js`: the words.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/unit/test_server_entry.py tests/unit/test_add_server.py tests/unit/test_library.py tests/security -v` and `node --test tests/frontend/*.test.mjs`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/kitden/changes/server_entry.py src/kitden/changes/actions.py src/kitden/views/library.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/library.js src/kitden/web/static/js/panel.js src/kitden/web/static/js/parts.js tests/unit/test_server_entry.py tests/unit/test_add_server.py tests/unit/test_library.py tests/security/test_no_secrets.py tests/frontend/library.test.mjs tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs
git commit -m "Library: add an MCP server to another client"
```

---

### Task 5: Add into one project (3.6)

**Files:**
- Modify: `src/kitden/clients/base.py:284-302` (`skill_copy_step(folder, readers, project=None)`), `280-282` (`plugin_install_step(plugin_id, project=None)`)
- Modify: `src/kitden/clients/claude_code.py:155-173` (`plugin_install_step`), `codex.py:219-236` (`plugin_install_step` refuses a project), new `CodexAdapter.trusts(project)`, `codex.py:368-389` (`_project`: the fact and its date)
- Modify: `src/kitden/changes/actions.py:91-120` (`install_steps(..., project=None)`), `123-155` (`skill_steps(..., project=None)`; the readers go into `_skill_readers`)
- Modify: `src/kitden/views/library.py:46-61` (`_add`: `project_place`, `project_hint`), `190-234` (`_plugin_cell`), `305-333` (`_skill_cell`)
- Modify: `src/kitden/views/skills.py:1-8` (the docstring: project folders, checked)
- Modify: `src/kitden/web/app.py:735-762` (`PLUGIN_INSTALL`, `SKILL_INSTALL`: `params.project`)
- Modify: `src/kitden/web/static/js/library.js:62-93` (`previewFor`, `noteFor`, `addName`, `scopeLine`, `cellNode`, new `addChoices`, `startAdd`), `offer.js:170-174` (`addButton` uses `startAdd`), `panel.js:638-665` (`changeWords`: the project)
- Modify: `tests/unit/test_api_plugin_install.py:40-70` (`FakeCli`: `-s project` writes `<cwd>/.claude/settings.json`)
- Create: `tests/unit/test_project_add.py`
- Test: `tests/frontend/library.test.mjs`, `tests/frontend/panel.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: Part 1's `addName(row, client, add, project)` and `scopeLine(project, rows)` (`library.js`); `add_skills_marketplace`, `PLUGIN` (`tests/unit/test_skills_catalog.py`); `LINTER`, `add_marketplaces`, `FakeCli` (`tests/unit/test_api_plugin_install.py`); `project_views` is not needed.
- Produces: `ClientAdapter.skill_copy_step(folder: Path, readers: list[str], project: str | None = None) -> Step`: with a project the target is `Path(project) / self.skills_folder / folder.name`, `scope=Scope.PROJECT`, `shared_file=True`; `CodexAdapter.trusts(project: str) -> bool` (`config.toml` `projects[<path>].trust_level == "trusted"`), and its `skill_copy_step` with a project it does not trust raises `ValueError(f"Codex does not trust {Path(project).name} yet, so it would not load the skill there.")`; `ClaudeCodeAdapter.plugin_install_step(plugin_id, project: str | None = None)`: with a project `command=[..., "-s", "project", "--json"]`, `undo_command` the same with `uninstall`, `cwd=project`, `edit.path = <project>/.claude/settings.json`, `scope=PROJECT`, `shared_file=True`; `CodexAdapter.plugin_install_step` with a project raises `ValueError("Codex has no project place for a plugin here; add it for all projects.")`; `install_steps(adapters, offer, clients, project=None)` and `skill_steps(adapters, skill, clients, found, project=None)` pass it through; `_skill_readers(client: str, adapters, found: set[str]) -> list[str]` holds the reader rule of `skill_steps` (used again in Task 6). Library: `_add(..., project_place: bool = False, project_hint: str | None = None)`; `project_place` is true for `skill.install` (every client) and for `plugin.install` to `claude_code`; `project_hint` is `"Codex plugins are for all projects."` on a Codex `plugin.install`. API: `params["project"]` (a project id) on `plugin.install` and `skill.install`; unknown → 422 `"Unknown project."`. Page: `export function addChoices(add, folder)` → `[{ label: "Add to this project…", scope: "project", look: "btn primary" }, { label: "Add for all projects…", scope: "all", look: "btn" }]`; `previewFor(add, client, scope = "all")` adds `project: state.project` to `params` when `scope === "project"`; `noteFor(add, project, scope = "all")`: `scope === "project"` → `` `Adds to ${folder} only.` `` (the folder from `projectPath()`); else `[add.warn, add.project_hint || projectNote(project)]` joined; `addName(row, client, add, project)`: with a project and `add.project_place` the name ends with `"…"`, else as Part 1 made it; `scopeLine(project, rows)`: when any row's cell add has `project_place`, `"An Add asks: this project, or all your projects. Adds without that choice go to all of them."`, else Part 1's line; `export function startAdd(add, client, row)`: with `state.project` and `add.project_place`, `openInfo("Add", rowTitle(row), body, choices)` with the two buttons (primary last, as `moveInto` draws them), each calling `review(previewFor(add, client, scope), { note: noteFor(add, state.project, scope) })`; else `review(previewFor(add, client), { note: noteFor(add, state.project) })`. `cellNode` and `offer.js`'s `addButton` call `startAdd`. `changeWords`: for `skill.install` and `plugin.install` with `previewBody.params.project`, title and done end with `` ` in ${projectLabel(project)}` ``.

- [ ] **Step 1: Check the clients' docs and write the dates**

`claude plugin install --help` and code.claude.com/docs/en/plugins: `-s project` and the file it writes (`<project>/.claude/settings.json`, `enabledPlugins`); write `# checked YYYY-MM-DD` above the project branch in `claude_code.py`. Project skill folders, in `skills.py`'s docstring with the date: Claude Code `<project>/.claude/skills` (code.claude.com/docs/en/skills); Codex `<project>/.agents/skills`, and whether it loads them only in a trusted project (developers.openai.com/codex/skills) — `codex.py:385` already reads them only when trusted; Cursor `<project>/.cursor/skills`, and whether it reads `<project>/.agents/skills` without Include Third-Party Plugins (cursor.com/docs skills) — `cursor.py:381-396` reads it always; if the docs say otherwise, change `_skills` and the readers together. Codex per-project plugins (developers.openai.com/codex/plugins): if Codex has a per-project install, `project_hint` names where (`"In Codex: …"`); if not, it stays `"Codex plugins are for all projects."`; the test below asserts the final words.

- [ ] **Step 2: Write the failing tests**

`tests/unit/test_api_plugin_install.py` `FakeCli`: when the command holds `-s project`, `plugin install` writes `enabledPlugins[<id>] = true` into `<cwd>/.claude/settings.json` (made if missing) and `uninstall -s project` removes it there.

`tests/unit/test_project_add.py` (fixture `client`: `_client(tmp_path, monkeypatch)` as in `test_api_skill_install.py` plus `add_marketplaces(home)` and `run=FakeCli(home)`; `pid(client, folder)` reads the project id from `/api/projects`; `_preview(client, action, chosen, params)`):

```python
def test_a_skill_goes_into_the_project_folder(client):
    home, website = client.home, str(client.home / "work/website")
    change = _preview(client, "skill.install", ["claude_code"], {"skill": TIDY, "project": pid(client, website)}).json()
    step = change["steps"][0]
    assert (step["scope"], step["path"], step["reaches"]) == ("project", f"{website}/.claude/skills/tidy", ["claude_code", "cursor"])
    assert change["shared_file_warning"] is True
    assert client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
    rows = client.get(f"/api/library?kind=skill&project={pid(client, website)}").json()["rows"]
    tidy = next(r for r in rows if r["name"] == "tidy")
    assert (tidy["cells"]["claude_code"]["state"], tidy["cells"]["claude_code"]["where"]) == ("on", "this project")
    everywhere = next(r for r in client.get("/api/library?kind=skill&show=all").json()["rows"] if r["name"] == "tidy")
    assert everywhere["cells"]["claude_code"]["state"] == "none"
    assert client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    assert not (home / "work/website/.claude/skills/tidy").exists()


def test_codex_and_cursor_project_folders(client):
    api = str(client.home / "work/api")  # Codex trusts it
    codex = _preview(client, "skill.install", ["codex"], {"skill": TIDY, "project": pid(client, api)}).json()
    assert (codex["steps"][0]["path"], codex["steps"][0]["reaches"]) == (f"{api}/.agents/skills/tidy", ["codex", "cursor"])
    cursor = _preview(client, "skill.install", ["cursor"], {"skill": TIDY, "project": pid(client, api)}).json()
    assert (cursor["steps"][0]["path"], cursor["steps"][0]["reaches"]) == (f"{api}/.cursor/skills/tidy", ["cursor"])


def test_a_codex_project_copy_needs_trust(client):
    website = str(client.home / "work/website")
    answer = _preview(client, "skill.install", ["codex"], {"skill": TIDY, "project": pid(client, website)})
    assert (answer.status_code, answer.json()["detail"]) == (422, "Codex does not trust website yet, so it would not load the skill there.")


def test_a_claude_code_plugin_goes_into_the_project(client):
    website = str(client.home / "work/website")
    change = _preview(client, "plugin.install", ["claude_code"], {"plugin": LINTER, "project": pid(client, website)}).json()
    step = change["steps"][0]
    assert step["command"] == f"claude plugin install {LINTER} -s project --json"
    assert (step["scope"], step["path"]) == ("project", f"{website}/.claude/settings.json")
    assert change["shared_file_warning"] is True
    assert client.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
    assert json.loads((client.home / "work/website/.claude/settings.json").read_text())["enabledPlugins"][LINTER] is True
    assert client.run.calls[-1][-4:] == [LINTER, "-s", "project", "--json"]
    assert client.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    assert LINTER not in json.loads((client.home / "work/website/.claude/settings.json").read_text())["enabledPlugins"]


def test_codex_has_no_project_place_for_a_plugin(client):
    website = str(client.home / "work/website")
    answer = _preview(client, "plugin.install", ["codex"], {"plugin": LINTER, "project": pid(client, website)})
    assert (answer.status_code, answer.json()["detail"]) == (422, "Codex has no project place for a plugin here; add it for all projects.")
    assert _preview(client, "plugin.install", ["codex"], {"plugin": LINTER, "project": "nope"}).json()["detail"] == "Unknown project."


def test_the_cells_say_which_adds_have_a_project_place(client):
    website = pid(client, str(client.home / "work/website"))
    skills = client.get(f"/api/library?kind=skill&show=new&project={website}").json()["rows"]
    tidy = next(r for r in skills if r["name"] == "tidy")
    assert all(tidy["cells"][c]["add"]["project_place"] is True for c in ("claude_code", "codex", "cursor"))
    plugins = client.get(f"/api/library?kind=plugin&show=new&project={website}").json()["rows"]
    linter = next(r for r in plugins if r["name"] == "linter")
    assert (linter["cells"]["claude_code"]["add"]["project_place"], linter["cells"]["claude_code"]["add"]["project_hint"]) == (True, None)
    assert (linter["cells"]["codex"]["add"]["project_place"], linter["cells"]["codex"]["add"]["project_hint"]) == (False, "Codex plugins are for all projects.")
```

`tests/frontend/library.test.mjs` (extend the `add` helper with `project_place: false, project_hint: null`):

```js
test('in a project an add with a project place asks where it goes', () => {
  assert.deepEqual(addChoices(add({ project_place: true }), 'website').map((c) => [c.label, c.scope, c.look]), [
    ['Add to this project…', 'project', 'btn primary'], ['Add for all projects…', 'all', 'btn'],
  ]);
  state.project = 'p1';
  assert.deepEqual(previewFor(add({ action: 'skill.install', skill: 'tidy@toolbox@x', project_place: true }), 'codex', 'project'),
    { action: 'skill.install', targets: [{ client: 'codex' }], params: { skill: 'tidy@toolbox@x', project: 'p1' } });
  assert.deepEqual(previewFor(add({ action: 'skill.install', skill: 'tidy@toolbox@x', project_place: true }), 'codex', 'all').params, { skill: 'tidy@toolbox@x' });
  state.project = '';
});
test('the review note says the project, or where a client has no project place', () => {
  // noteFor reads the folder from projectPath(); the test sets data.projects as panel.test.mjs does.
  assert.equal(noteFor(add({ project_place: true }), 'p1', 'project'), 'Adds to website only.');
  assert.equal(noteFor(add({ project_place: true }), 'p1', 'all'), 'Adds for all your projects.');
  assert.equal(noteFor(add({ project_hint: 'Codex plugins are for all projects.' }), 'p1'), 'Codex plugins are for all projects.');
});
test('the scope line and the button name follow the project place', () => {
  const row = { name: 'tidy', kind: 'skill', same_name: false };
  assert.ok(addName(row, 'codex', add({ project_place: true }), 'p1').endsWith('…'));
  assert.ok(addName(row, 'codex', add({}), 'p1').endsWith(' for all projects'));
  assert.equal(scopeLine('p1', [{ cells: { codex: cell({ add: add({ project_place: true }) }) } }]), 'An Add asks: this project, or all your projects. Adds without that choice go to all of them.');
  assert.equal(scopeLine('p1', [{ cells: { codex: cell({ add: add({}) }) } }]), 'Adding puts an item in all your projects.');
});
```

`tests/frontend/panel.test.mjs`: with `data.projects = [{ id: 'p1', path: '/Users/me/work/website' }]`, `changeWords({ action: 'skill.install', steps: [{ client: 'codex', name: 'tidy', reaches: ['codex'] }] }, { params: { skill: 'x', project: 'p1' } })` → `{ title: 'Add tidy to Codex in website', done: 'Added tidy to Codex in website' }`.

`tests/unit/test_page_words.py`: `test_an_add_in_a_project_offers_two_choices`: `library.js` contains `"Add to this project…"`, `"Add for all projects…"` and `"An Add asks: this project, or all your projects."`; `offer.js` calls `startAdd(`.

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/unit/test_project_add.py -v` and `node --test tests/frontend/library.test.mjs tests/frontend/panel.test.mjs`
Expected: FAIL: `project` is ignored (user-scope paths), `addChoices` is not exported.

- [ ] **Step 4: Implement the Python side**

The adapters and `actions.py` as the interface says (`_skill_readers` extracted from `skill_steps` lines 147-154). `library.py`: the two `_add` fields, set in `_skill_cell` (`project_place=True`) and `_plugin_cell` (`project_place=client == "claude_code"` for `plugin.install`; `project_hint` for Codex). `app.py`: read `params.get("project")`, map the id through `{p["id"]: p["path"] for p in state.data["projects"]}`, pass `project=path`.

- [ ] **Step 5: Implement the page**

`library.js`: `addChoices`, `startAdd`, the new parameters of `previewFor`, `noteFor`, `addName`, `scopeLine`. `offer.js` `addButton` → `startAdd(option.add, option.client, row)`. `panel.js` `changeWords` → the ` in <folder>` suffix.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/unit/test_project_add.py tests/unit/test_api_plugin_install.py tests/unit/test_api_skill_install.py tests/unit/test_page_words.py -v` and `node --test tests/frontend/*.test.mjs`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/kitden/clients/base.py src/kitden/clients/claude_code.py src/kitden/clients/codex.py src/kitden/changes/actions.py src/kitden/views/library.py src/kitden/views/skills.py src/kitden/web/app.py src/kitden/web/static/js/library.js src/kitden/web/static/js/offer.js src/kitden/web/static/js/panel.js tests/unit/test_api_plugin_install.py tests/unit/test_project_add.py tests/unit/test_page_words.py tests/frontend/library.test.mjs tests/frontend/panel.test.mjs
git commit -m "Library: add a skill or a plugin into one project"
```

---

### Task 6: Align a project across clients (3.5)

**Files:**
- Create: `src/kitden/changes/align.py` (`align_steps`)
- Modify: `src/kitden/changes/actions.py:389-391` (`PROJECT_ALIGN = "project.align"`)
- Modify: `src/kitden/web/app.py:717-875` (dispatch; the answer carries `align`)
- Modify: `src/kitden/views/after.py` (`_align_words`)
- Modify: `src/kitden/web/static/js/library.js:362-391` (`toolbar`: "Add missing…"), `panel.js:740-790` (`showReview`: the checkbox list), new `alignGroups`, `chosenKeys`; `panel.js:611-670` (words); `parts.js:212-263`
- Create: `tests/unit/test_align.py`
- Test: `tests/frontend/panel.test.mjs`, `tests/frontend/parts.test.mjs`, `tests/unit/test_page_words.py`

**Interfaces:**
- Consumes: `effective_view` (`views/effective.py`); `catalog`, `skill_catalog`, `read_skill` (`views/catalog.py`, `views/skills.py`); `install_steps`, `skill_steps`'s `_skill_readers`, `add_server_steps`, `remove_steps`, `_raw_entry` (Tasks 4 and 5); `is_direct_entry`; the `GATEWAY_RULES` review pattern of Part 2 (one review, several steps of one kind, listed in the review); `FakeCli` and `FakeClaude` composed into one runner: `run = lambda command, cwd: (FakeClaude(home) if command[1] == "mcp" else FakeCli(home))(command, cwd)`.
- Produces: `PROJECT_ALIGN = "project.align"` (no targets; params `{"project": str (an id), "chosen": list[str] | None}`). `align_steps(inventory, adapters, home: Path, project: str, found: set[str], chosen: list[str] | None) -> tuple[list[Step], dict]`. The listing `{"candidates": [{"key", "kind", "name", "from", "to", "chosen": bool}], "not_same": [{"kind", "name", "clients": [...]}], "left_out": [{"name", "why"}]}`; `key` is `f"{kind}:{name}:{to}"`. Candidates, from every found client `A` (`CLIENTS` order) to every other found client `B`, per `A` MCP servers first, then plugins, then skills, each kind by name, each `(kind, name, B)` once with the first `A` that has it; the steps follow the candidate order: an MCP server `A` loads in the project that is a user-scope direct entry (`is_direct_entry(i, A, {Scope.USER})`, `via_gateway is None`, `name != SETUP_NAME`) and `B` loads no MCP server of that name (names compared lower-cased); a plugin `A` loads (scope `USER` or `PROJECT`, `"@"` in the name) whose base name no plugin `B` loads, when the catalog offer of `A`'s plugin id has a route for `B` (else `left_out` with `f"{Client} cannot get {name}"`; no offer at all → `f"{name} is not in a marketplace on this computer"`); a skill `A` loads from its own folder (scope `USER` or `PROJECT`, `source.owner_client == A`, `link_path is None`) that `B` loads under no such name, when `read_skill(folder)["self_contained"]` (else `left_out` with "needs the rest of its plugin"). `not_same`: `B` loads the name but from another source — a plugin of the same base name from another marketplace, a skill whose `realpath(source.path)` differs, an MCP server whose redacted `summary` differs; one line per `(kind, name)` naming every found client that loads the name (`CLIENTS` order), when at least two of them load different sources. Steps: MCP → `add_server_steps(adapters, item, [B])`; plugin → `install_steps(adapters, offer, [B], project=project if A's item is project-scoped and B == "claude_code" else None)`, with one marketplace step per `(client, marketplace)` in the whole change; skill → `adapters[B].skill_copy_step(folder, _skill_readers(B, adapters, found), project=project if A's item is project-scoped else None)`; a `ValueError` from a builder moves the candidate to `left_out` with `str(error)` as `why`. `chosen` None marks every candidate chosen; a list keeps only those keys; no step at all raises `ValueError("Choose at least one item.")` when the list is empty and `ValueError(f"Nothing is missing in {Path(project).name}.")` when there was no candidate. API: the preview answer carries `"align": listing`; an unknown project id → 422 `"Unknown project."`. Review words: one `{"client", "state": "on", "word": "Loads"}` per client in `CLIENTS` order that is a step's client or a copy's reader. Page: the Library toolbar shows `button("Add missing…", …, "btn small")` with `dataset.focus = "add:missing"` when `state.project` is set, opening `review({ action: "project.align", targets: [], params: { project: state.project, chosen: null } })`; `export function alignGroups(align)` → `[{ client, name, items: [{ key, label, chosen }] }]` grouped by `to` in `CLIENT_ORDER`, `label` is `` `${name} · ${KIND_WORDS[kind]} · from ${CLIENT_NAMES[from]}` ``; `export function chosenKeys(align, key, checked)` → the chosen keys with `key` added or removed; the review draws the groups as checkboxes above the file changes, a `"Not the same; not touched"` list (`` `${name} · ${KIND_WORDS[kind]} · ${clients joined}` ``) and the left-out line as `leftOutText` draws it; a checkbox change cancels the preview and calls `review` again with `params.chosen = chosenKeys(...)`. `changeWords`: `project.align` → title `` `Add what ${folder} is missing` ``, done `` `Added ${plural(n, "item", "items")} for ${folder}` `` with `n` the chosen candidates and `folder` from `previewBody.params.project`; `ACTION_WORDS["project.align"] = "Added missing items"`; `changeTitle` → `` `Added missing items · ${clients}` ``.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_align.py` (fixture: the three clients with `add_skills_marketplace(home)` and `add_marketplaces(home)`, `write_cursor_fixture_state(home)`; `runner(home)` returns the composed runner from Interfaces; `api = str(home / "work/api")` — Codex trusts it; before the page starts: `add_codex(home, "superpowers_other", …)` is not needed, instead write `[plugins."superpowers@team-mkt"]\nenabled = true` into `config.toml`, `add_claude(home, "neon", {"type": "http", "url": "https://other.invalid/mcp"})` and `add_claude(home, "shelled", {"type": "stdio", "command": "npx", "args": ["x", "${TOKEN}"]})`; `_align(page, project, chosen=None)` posts the preview):

```python
def test_add_missing_lists_what_each_client_lacks(home):
    with page_for(home, run=runner(home)) as page:
        listing = _align(page, pid(page, api)).json()["align"]
    keys = {c["key"]: c for c in listing["candidates"]}
    assert all(c["chosen"] for c in listing["candidates"])
    assert keys["mcp_server:github:codex"]["from"] == "claude_code"
    assert keys["mcp_server:github:cursor"]["from"] == "claude_code"
    assert keys["mcp_server:langfuse-data:claude_code"]["from"] == "codex"
    assert keys["skill:brandkit:codex"]["from"] == "claude_code"
    assert keys["skill:docker-expert:claude_code"]["from"] == "codex"
    assert "mcp_server:Neon:codex" not in keys  # Codex has neon, the same server
    assert "mcp_server:neon:cursor" not in keys  # Cursor has Neon
    assert {"kind": "mcp_server", "name": "neon", "clients": ["claude_code", "codex", "cursor"]} in listing["not_same"]
    assert {"kind": "plugin", "name": "superpowers", "clients": ["claude_code", "codex", "cursor"]} in listing["not_same"]
    assert {"name": "shelled", "why": "Codex cannot read `${TOKEN}` from your shell; put the value in."} in listing["left_out"]
    assert "browser@openai-bundled" in {e["name"] for e in listing["left_out"]}  # its marketplace folder is not in the fixture


def test_add_missing_is_one_change_and_undo_takes_it_all_back(home):
    files = [home / ".codex/config.toml", home / ".claude.json"]
    before = {p: p.read_bytes() for p in files}
    with page_for(home, run=runner(home)) as page:
        chosen = ["mcp_server:github:codex", "skill:brandkit:codex", "mcp_server:langfuse-data:claude_code"]
        change = _align(page, pid(page, api), chosen).json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [
            ("codex", "github"), ("codex", "brandkit"), ("claude_code", "langfuse-data"),
        ]
        assert change["steps"][1]["reaches"] == ["codex", "cursor"]
        assert [c["key"] for c in change["align"]["candidates"] if c["chosen"]] == chosen
        assert change["after"] == [{"client": "claude_code", "state": "on", "word": "Loads"}, {"client": "codex", "state": "on", "word": "Loads"}, {"client": "cursor", "state": "on", "word": "Loads"}]
        assert "SENTINEL" not in json.dumps(change)
        assert page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()["state"] == "verified"
        assert (home / ".agents/skills/brandkit/SKILL.md").is_file()
        assert "github" in tomllib.loads((home / ".codex/config.toml").read_text())["mcp_servers"]
        assert page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()["state"] == "undone"
    assert {p: p.read_bytes() for p in files} == before
    assert not (home / ".agents/skills/brandkit").exists()


def test_unchecked_items_are_left_out_of_the_change(home):
    with page_for(home, run=runner(home)) as page:
        none = _align(page, pid(page, api), [])
        assert (none.status_code, none.json()["detail"]) == (422, "Choose at least one item.")
        one = _align(page, pid(page, api), ["skill:brandkit:codex"]).json()
        assert [s["name"] for s in one["steps"]] == ["brandkit"]
        unknown = _align(page, "nope")
        assert (unknown.status_code, unknown.json()["detail"]) == (422, "Unknown project.")


def test_a_project_skill_goes_into_the_project_and_nothing_is_overwritten(home):
    # Claude Code's site-style lives in work/website; Codex does not trust website, so it is left out
    # with the trust words; Cursor gets it under <website>/.cursor/skills.
    with page_for(home, run=runner(home)) as page:
        listing = _align(page, pid(page, str(home / "work/website"))).json()
        assert {"name": "site-style", "why": "Codex does not trust website yet, so it would not load the skill there."} in listing["align"]["left_out"]
        step = next(s for s in listing["steps"] if s["name"] == "site-style")
        assert (step["client"], step["path"]) == ("cursor", f"{home}/work/website/.cursor/skills/site-style")
```

`tests/frontend/panel.test.mjs`:

```js
test('the align review groups what each client lacks and keeps the choice', () => {
  const align = { candidates: [
    { key: 'mcp_server:github:codex', kind: 'mcp_server', name: 'github', from: 'claude_code', to: 'codex', chosen: true },
    { key: 'skill:brandkit:cursor', kind: 'skill', name: 'brandkit', from: 'claude_code', to: 'cursor', chosen: false },
  ], not_same: [], left_out: [] };
  assert.deepEqual(alignGroups(align), [
    { client: 'codex', name: 'Codex', items: [{ key: 'mcp_server:github:codex', label: 'github · MCP server · from Claude Code', chosen: true }] },
    { client: 'cursor', name: 'Cursor', items: [{ key: 'skill:brandkit:cursor', label: 'brandkit · Skill · from Claude Code', chosen: false }] },
  ]);
  assert.deepEqual(chosenKeys(align, 'skill:brandkit:cursor', true), ['mcp_server:github:codex', 'skill:brandkit:cursor']);
  assert.deepEqual(chosenKeys(align, 'mcp_server:github:codex', false), []);
  data.projects = [{ id: 'p1', path: '/Users/me/work/website' }];
  assert.deepEqual(changeWords({ action: 'project.align', steps: [{ client: 'codex', name: 'github' }], align }, { params: { project: 'p1' } }), { title: 'Add what website is missing', done: 'Added 1 item for website' });
  data.projects = null;
});
```

`tests/frontend/parts.test.mjs`: `changeTitle({ action: 'project.align', steps: [{ client: 'codex', name: 'github' }, { client: 'codex', name: 'brandkit', reaches: ['codex', 'cursor'] }] })` → `'Added missing items · Codex, Cursor'`.

`tests/unit/test_page_words.py`: `test_a_project_can_be_aligned_in_one_review`: `library.js` contains `"Add missing…"` and `'"add:missing"'`; `panel.js` contains `"Not the same; not touched"` and `'"project.align"'`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/unit/test_align.py -v` and `node --test tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs`
Expected: FAIL: the action is not offered; `alignGroups` is not exported.

- [ ] **Step 3: Implement `align_steps`**

`align.py`: `_loaded(inventory, found, project) -> dict[str, EffectiveView]`; `_candidates(...)` walks the three kinds as the interface says; `_build(candidate, ...)` calls the builder and catches `ValueError`; marketplace steps are deduplicated by `(step.client, step.edit.key)`. `actions.py`: the constant. `app.py`: the dispatch (`project` id → path, else 422; `found` as the other branches read it) and `answer["align"] = listing`. `after.py`: `_align_words`.

- [ ] **Step 4: Implement the page**

`library.js` `toolbar`: the button. `panel.js`: `alignGroups`, `chosenKeys`, the checkbox section in `showReview` (drawn only when `change.align`), the words. `parts.js`: the words.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/unit/test_align.py tests/unit/test_page_words.py tests/security -v` and `node --test tests/frontend/*.test.mjs`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/kitden/changes/align.py src/kitden/changes/actions.py src/kitden/web/app.py src/kitden/views/after.py src/kitden/web/static/js/library.js src/kitden/web/static/js/panel.js src/kitden/web/static/js/parts.js tests/unit/test_align.py tests/unit/test_page_words.py tests/frontend/panel.test.mjs tests/frontend/parts.test.mjs
git commit -m "Library: add what a project is missing in one review"
```

---

### Task 7: Docs, hand check and roadmap for Part 3

**Files:**
- Modify: `README.md` ("See what each client has, and add what it lacks": the Library paragraph; "The Kitden gateway: tools per project": the Gateway paragraph)
- Modify: `ROADMAP.md` ("## Planned": the Part 3 line moves to "### Not released yet" under Done as one bullet per shipped action; remove "## Under review" if it is still there)
- Modify: `docs/development.md` ("Check before a release": steps for remove, put back, add to another client, add into a project, add missing)
- Test: `tests/unit/test_docs_words.py` (Part 1 created it)

- [ ] **Step 1: Write the failing test** in `tests/unit/test_docs_words.py`

```python
def test_readme_names_the_management_actions():
    readme = (ROOT / "README.md").read_text()
    for words in (
        "Remove from",  # a plugin or a skill, with Undo
        "+ Add\" on an MCP server copies its entry to another client",
        "Add to this project…",
        "Add missing…",
        "Put back in",
        "Remove from the Kitden gateway…",
    ):
        assert words in readme, words
    check = (ROOT / "docs/development.md").read_text()
    for words in ("Remove", "Put back", "Add missing", "Add to this project"):
        assert words in check, words
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/unit/test_docs_words.py -v`
Expected: FAIL

- [ ] **Step 3: Write the README sentences**

In the Library paragraph, after the "+ Add" sentences: "Details of a plugin or a skill offer \"Remove from <client>…\", with Undo. \"+ Add\" on an MCP server copies its entry to another client; a `${VAR}` reference stays a reference where that client can read one, and the review says when a secret gets a second copy. With a project picked, \"+ Add\" on a skill or a Claude Code plugin asks \"Add to this project…\" or \"Add for all projects…\", and \"Add missing…\" lists what one client loads there and another lacks, as one review with checkboxes; items with the same name but a different source are listed as not the same and not touched." In the Gateway paragraph: "A held server's Details offer \"Remove from the Kitden gateway…\" (its switches go with it; the tool list stays; Undo brings it back) and \"Put back in <client>…\", which writes the entry into that client again." Plain words, no paths.

- [ ] **Step 4: Add the hand-check steps** to `docs/development.md`, numbered after the existing ones (and after Part 2's): remove a plugin in Claude Code and in Codex, start a new session, it is gone, Undo brings it back; remove a skill, same; put a held server back in one client and remove it from the gateway, a new session sees it direct; "+ Add" a server with a `${VAR}` header from Claude Code into Cursor and Codex, a new session reaches it; "Add to this project…" a skill, a session in that folder has it and one elsewhere does not; "Add missing…" on a throwaway project, Undo. Write the date next to the steps once done.

- [ ] **Step 5: Update ROADMAP.md**

Under "### Not released yet": "**Complete management:** remove a plugin, a skill or a server in the Kitden gateway, with Undo; put a held server back in a client; add an MCP server to another client, references kept where the client reads them; add a skill or a Claude Code plugin into one project; add what a project is missing in one review." Remove line 3 from "## Planned". Remove "## Under review" if present. Change "Last updated".

- [ ] **Step 6: Run all checks**

Run: `uv run pytest -q && uv run ruff check . && node --test tests/frontend/*.test.mjs`
Expected: all pass.

- [ ] **Step 7: Do the hand check once** in Claude Code, Codex and Cursor on a throwaway project and note the date in `docs/development.md`.

- [ ] **Step 8: Commit**

```bash
git add README.md ROADMAP.md docs/development.md tests/unit/test_docs_words.py
git commit -m "Docs: Part 3 of the review follow-up"
```
