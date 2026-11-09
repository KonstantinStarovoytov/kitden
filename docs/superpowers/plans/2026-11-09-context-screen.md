# Context Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new page, Context, that shows whether each client's skill list fits: the fact from the last chat log, and estimates only while Kitden's rule rebuilds that list.

**Architecture:** A new Python package `src/kitden/context/` reads the newest chat log of Claude Code and Codex (only the skill list part), runs each client's rule, and checks the rule against the log. `views/context_view.py` turns that into one JSON read model with every sentence already written, served at `/api/context`. A new page module `context.js` draws it like the prototype; switches add `skill.rule` rows to the existing tray, and the page asks `/api/context?draft=…` again to show "After Apply, estimate".

**Tech Stack:** Python 3.13, Starlette, pytest; vanilla JS ES modules, `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-09-skill-fit-design.md`. Prototype: `design/kitden-context.html`; states: `design/kitden-context-states.html` (untracked, in the owner's checkout).

## Global Constraints

- Code, comments, UI text and docs in simple English, short and plain.
- Every client settings change goes through preview → Apply with a backup → verify → Undo; this page only adds `skill.rule` rows to the tray.
- Main view: names, client, action. Paths, rule numbers and log names go behind Details and "How this is counted".
- Kitden reads only the skill list part of a log, keeps none of it on disk, sends nothing anywhere, starts no client.
- Each changing fact (rule, characters per token, window table, file paths, field names) carries `# checked YYYY-MM-DD (source)` next to it.
- Tests use sandbox homes (`tests/conftest.py` fixtures) and small fixture logs written by the tests, never copies of real chats.
- Before each commit: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`.
- Commit subjects: short and plain, one to three simple lines, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Look and motion follow `docs/design.md`; the prototype's tokens map to the app's (`--accent`→`--route`, `--warn`→`--lamp-warn`, `--ok`→`--lamp-on`, `--muted`→`--ink-3`, `--faint`→`--ink-4`, `--line`→`--wire`, `--raised`→`--panel-raised`, `--select`→`--route-soft`, `--pline`/`--pfill`→`--preview-line`/`--preview-fill`). A new `--hatch` token needs light and dark values in all three `:root` blocks of `style.css`.

## Review Focus

1. A huge log (hundreds of MB) must not slow the page: lines are filtered by a plain substring before `json.loads`. Test in Task 2.
2. A log being written now ends in a half line: that line is skipped, nothing fails. Tests in Tasks 2 and 3.
3. Non-ASCII descriptions (Russian) cost Codex twice the bytes; names with `:` (plugin skills) keep their prefix. Tests in Tasks 1 and 3.
4. A picked project with no chat of its own shows "No chat yet", never another project's result. Test in Task 6.
5. `SLASH_COMMAND_TOOL_CHAR_BUDGET` in settings that is not a whole number is ignored, and the limit comes from the window. Test in Task 6.

---

### Task 1: Rules and tables

**Files:**
- Create: `src/kitden/context/__init__.py` (empty), `src/kitden/context/tables.py`, `src/kitden/context/rules.py`
- Test: `tests/unit/test_context_rules.py`

**Interfaces:**
- Produces:
  - `tables.CLAUDE_WINDOWS: dict[str, tuple[int, int]]` model id → (window, characters per token): `"claude-opus-5-5": (1_000_000, 3)`, `"claude-fable-5-1": (1_000_000, 3)`, `"claude-sonnet-4-6": (200_000, 4)`. Comment: checked 2026-11-06 (Claude Code 2.1.311 binary, `EH`).
  - `tables.CLAUDE_OTHER_WINDOW: dict[int, tuple[int, int, str]]` the estimate card for a last window: `1_000_000: (200_000, 4, "Older models")`, `200_000: (1_000_000, 3, "Opus 5.5, Fable 5.1")`.
  - `tables.CLAUDE_ALWAYS_FULL: frozenset[str]` (Claude Code 2.1.311, checked 2026-11-07 with two test chats): `dataviz, artifact-design, artifact-diagramming, artifact-capabilities, update-config, keybindings-help, code-review, simplify, fewer-permission-prompts, loop, schedule, claude-api, workflow-authoring, run, plugin-authoring`.
  - `tables.CLAUDE_SHARE = 0.01`, `tables.CLAUDE_DESCRIPTION_CAP = 1536`, `tables.CODEX_SHARE = 0.02`, `tables.CODEX_FIXED_TOKENS = 166` (fitted to the real list of 2026-10-30; say so), `tables.CODEX_DESCRIPTION_CAP = 1024`, `tables.CODEX_MAX_LIMIT = 10_000`.
  - `@dataclass(frozen=True) class ClaudeSkill: name: str; description: str | None; always_full: bool; name_only: bool; weight: float` (`description` None = size not known).
  - `claude_budget(window: int, per_token: int) -> int` = `window * per_token * CLAUDE_SHARE` as int.
  - `claude_weight(count: int, last_used_ms: int, at_ms: int) -> float` = `count * max(0.5 ** (days / 7), 0.1)`, `days = (at_ms - last_used_ms) / 86_400_000`.
  - `claude_rule(skills: list[ClaudeSkill], budget: int) -> ClaudeFit` with `@dataclass(frozen=True) class ClaudeFit: full: frozenset[str]; name_only: frozenset[str]; used: int; size: int` (`size` = the list with every description, `used` = what is sent). Raises `ValueError` when a needed description is None.
  - `@dataclass(frozen=True) class CodexSkill: name: str; description: str; path: str`.
  - `codex_tokens(text: str) -> int` = `ceil(len((text + "\n").encode()) / 4)`.
  - `codex_line(skill: CodexSkill, description: str) -> str`: `f"- {name}: {description} (file: {path})"`, or `f"- {name}: (file: {path})"` for `""`.
  - `codex_rule(skills: list[CodexSkill], budget: int) -> CodexFit` with `@dataclass(frozen=True) class CodexFit: sent: dict[str, int | None]; used: int; size: int; cap: int | None` (`sent[name]` = characters of description sent, `None` = left out of the list).
  - `codex_budget(window: int, limit: int | None) -> int` = `limit` if set (capped at `CODEX_MAX_LIMIT`), else `int(window * CODEX_SHARE)`.

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_context_rules.py`:
  - `test_claude_all_fit_sends_every_description`: three skills, budget large → `full == {all three}`, `name_only == set()`.
  - `test_claude_built_ins_and_name_only_keep_their_place_then_the_most_used`: five skills, two `always_full`, one `name_only`, two others with weights 5.0 and 1.0; budget leaves room for one more description → `full` = the two built-ins and the weight-5 skill; the weight-1 skill is in `name_only`.
  - `test_claude_built_ins_alone_can_pass_the_limit`: two `always_full` skills bigger than the budget → both in `full`, `used > budget`.
  - `test_claude_caps_a_description_at_1536`: one 3,000-character description → `size == len(name) + 4 + 1536`.
  - `test_claude_entry_sizes`: entry = `len(name) + 4 + min(len(d), 1536)` with a description, `len(name) + 2` without, plus `N - 1` separators; assert exact `size` for two skills.
  - `test_claude_weight_halves_every_week_and_stops_at_a_tenth`: `claude_weight(8, t, t + 7 days) == 4.0`; `claude_weight(8, t, t + 70 days) == 0.8`.
  - `test_codex_cuts_every_long_description_to_one_length`: three skills, budget that fits only short ones → all `sent` values for long ones equal one cap; short ones are full.
  - `test_codex_leaves_skills_out_when_names_do_not_fit`: budget below `CODEX_FIXED_TOKENS + names` → some `sent` values are `None`, the rest `0`.
  - `test_codex_counts_bytes_so_russian_costs_more`: `codex_tokens("я" * 8) > codex_tokens("a" * 8)`.
  - `test_codex_never_sends_more_than_1024`: a 2,000-character description with a large budget → `sent == 1024`.

- [ ] **Step 2: Run** `uv run pytest tests/unit/test_context_rules.py -q`. Expected: FAIL (module missing).

- [ ] **Step 3: Implement** `tables.py` and `rules.py`. `claude_rule` follows the prototype's `calcCC`:

```python
# Claude Code 2.1.311 (checked 2026-11-07): everything when it fits; else built-ins and Name only
# keep their entry, every other skill shows its name, and descriptions go to the most used.
entry = lambda s: len(s.name) + 2 if s.name_only else len(s.name) + 4 + min(len(s.description), CAP)
size = sum(entry(s) for s in skills) + max(0, len(skills) - 1)
if size <= budget: full = {s.name for s in skills if not s.name_only}
else:
    fixed = lambda s: s.always_full or s.name_only
    left = budget - (sum(entry(s) if fixed(s) else len(s.name) + 2 for s in skills) + max(0, len(skills) - 1))
    full = {s.name for s in skills if s.always_full and not s.name_only}
    for s in sorted((s for s in skills if not fixed(s)), key=lambda s: -s.weight):  # stable: log order breaks ties
        if min(len(s.description), CAP) + 2 <= left: left -= min(len(s.description), CAP) + 2; full.add(s.name)
```

  `codex_rule` follows `calcCX`: room = `budget - CODEX_FIXED_TOKENS`; total(m) = sum of `codex_tokens(codex_line(s, s.description[:m]))`. If total(0) > room, walk skills in order adding name-only lines while `used + m <= budget`, the rest `None`. Else cap = 1024 if total(1024) <= room, else the largest m in 0..1024 with total(m) <= room (binary search); `sent[name] = min(len(d), cap)`.

- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** "Context: the skill list rules of Claude Code and Codex".

### Task 2: Claude Code's last list

**Files:**
- Create: `src/kitden/context/claude_log.py`
- Test: `tests/unit/test_context_claude_log.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class SentList: client: str; at: str; version: str; surface: str | None; model: str | None; folder: str | None; skills: tuple[tuple[str, str | None], ...]` (name, sent text or None for a name only; for Codex the text is what was sent, cut or not, and `path` goes in Task 3's own type).
  - `@dataclass(frozen=True) class Unreadable: client: str; version: str`.
  - `INTERACTIVE = {"claude-desktop": "in the Claude app", "cli": "in the terminal"}` (checked 2026-11-09 for `claude-desktop`; confirm `cli` by one terminal chat at build time and date it).
  - `KNOWN_VERSIONS`: the newest version whose list entry shape is known, `"2.1.311"`.
  - `last_claude_list(home: Path, folder: str | None) -> SentList | Unreadable | None`.

- [ ] **Step 1: Write the failing tests** with a helper `write_chat(home, slug, name, entries, mtime)` that writes JSONL under `home/".claude/projects"/slug/name.jsonl`; a list entry is `{"type": "attachment", "timestamp": …, "version": "2.1.311", "entrypoint": "claude-desktop", "cwd": folder, "isSidechain": False, "attachment": {"type": "skill_listing", "isInitial": True, "skillCount": n, "names": [...], "content": "- a: Does A.\n- b"}}` and an assistant entry `{"type": "assistant", "message": {"model": "claude-opus-5-5"}}`:
  - `test_reads_names_and_sent_text_from_the_last_full_list`: two lists in one chat; the second wins; `skills == (("a", "Does A."), ("b", None))`; `surface == "in the Claude app"`, `model == "claude-opus-5-5"`.
  - `test_a_description_with_a_dash_line_stays_whole`: content `"- a: One.\n- not a skill\n- b: Two."` with names `["a","b"]` → `a`'s text is `"One.\n- not a skill"` (entries split at `- <name>` for each name in `names`, in order).
  - `test_skips_subagent_logs_sidechains_and_runs_that_are_not_a_chat`: newest file under `<session>/subagents/`, newer one with `isSidechain: True`, newer one with `entrypoint: "sdk-cli"` → the older plain chat is read.
  - `test_a_chat_with_no_list_yet_falls_back_to_the_next_older`.
  - `test_a_picked_folder_reads_only_its_own_chats`: newest chat elsewhere → returns the folder's own; no own chat → `None`.
  - `test_a_newer_version_with_an_unknown_shape_is_unreadable`: version `"2.2.0"`, attachment without `names` → `Unreadable("claude_code", "2.2.0")`, not the older list.
  - `test_a_half_written_last_line_is_skipped`.
  - `test_only_list_lines_are_parsed`: a 50,000-line log of other entries reads in under 1 second.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_context_claude_log.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Files: `home/.claude/projects/*/*.jsonl` (not `*/*/subagents/*`), newest by `st_mtime` first; stream lines; parse a line only if it contains `"skill_listing"` or (for the model) `"model"`; keep the last entry with `isInitial is True` and `len(names) == skillCount`; skip the file when `isSidechain` or `entrypoint not in INTERACTIVE` or `folder` given and `cwd != folder`; a file with a list entry whose shape is unknown and `version` newer than `KNOWN_VERSIONS` returns `Unreadable`. Compare versions as integer tuples.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** "Context: read Claude Code's last skill list".

### Task 3: Codex's last list

**Files:**
- Create: `src/kitden/context/codex_log.py`
- Test: `tests/unit/test_context_codex_log.py`

**Interfaces:**
- Consumes: `SentList`, `Unreadable` (Task 2).
- Produces:
  - `@dataclass(frozen=True) class CodexSent: list: SentList; paths: dict[str, str]` (name → `file:` path).
  - `last_codex_list(codex_home: Path, folder: str | None) -> CodexSent | Unreadable | None`.
  - `codex_window(codex_home: Path, model: str | None) -> int | None` from `models_cache.json` `models[].slug == model` → `context_window` (checked 2026-11-09; `session_meta.context_window` holds only an id).
  - `codex_windows(codex_home: Path) -> list[tuple[int, list[str]]]`: distinct `context_window` values with their display names, for the second card.

- [ ] **Step 1: Write the failing tests** with a helper writing `codex_home/"sessions/2026/11/08/rollout-….jsonl"`: first line `{"type": "session_meta", "payload": {"timestamp": …, "cwd": folder, "thread_source": "user", "cli_version": "0.163.0-alpha.11"}}`, then `{"type": "turn_context", "payload": {"model": "gpt-6-astra"}}`, then `{"type": "response_item", "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "<skills_instructions>\n- a: Does A. (file: /s/a/SKILL.md)\n- b: (file: /s/b/SKILL.md)\n</skills_instructions>"}]}}`:
  - `test_reads_each_line_with_its_path`: `skills == (("a","Does A."),("b",""))`, `paths["b"] == "/s/b/SKILL.md"`, `model == "gpt-6-astra"`.
  - `test_a_description_with_a_colon_keeps_it`: `"- a: Use: when X. (file: /p)"` → `"Use: when X."`.
  - `test_skips_threads_not_started_by_a_person` (`thread_source` `"subagent"`) and `.zst` files.
  - `test_the_date_is_the_list_entry_not_the_file`.
  - `test_window_comes_from_the_model_cache`: `models_cache.json` with `{"models": [{"slug": "gpt-6-astra", "display_name": "GPT-6-Astra", "context_window": 272000}]}` → `272000`; unknown model → `None`.
  - `test_a_half_written_last_line_is_skipped`.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_context_codex_log.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Newest `rollout-*.jsonl` by `st_mtime` under `codex_home/"sessions"`; parse `session_meta`, `turn_context` and lines containing `<skills_instructions>`; a line matches `^- (?P<name>[^:]+): (?P<desc>.*?) ?\(file: (?P<path>[^)]*)\)$`. Unknown `cli_version` newer than the known one plus no parsable list → `Unreadable`.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** "Context: read Codex's last skill list".

### Task 4: A skill's own state on the Item

**Files:**
- Modify: `src/kitden/model.py:138` (Item), `src/kitden/clients/claude_code.py:121-160` (`_apply_rules`, `_project_rules`), `src/kitden/views/explain.py:33` (`brief`)
- Test: `tests/unit/test_claude_code_settings.py`, `tests/unit/test_explain.py`

**Interfaces:**
- Produces: `Item.skill_state: str | None = None`, the raw `skillOverrides` value for Claude Code (`"name-only"`, `"user-invocable-only"`, `"off"`), or `"only-asked"` when the skill file says `disable-model-invocation: true` (read with `views/skills.py` `front_matter`). `brief(item)` adds `"skill_state"` when set.

- [ ] **Step 1: Write the failing tests**: `test_name_only_is_kept_as_the_skills_state` (settings `{"skillOverrides": {"extra": "name-only"}}` → item `enabled == ON`, `skill_state == "name-only"`); `test_a_skill_that_waits_to_be_asked_says_so` (front matter `disable-model-invocation: true` → `"only-asked"`); `test_brief_names_the_skill_state`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** in `_apply_rules` (keep `state` instead of dropping it) and in the user skill scan; Codex and Cursor leave it `None`. The Library's Details show it as a fact ("Name only" / "Only when you ask") through `item_dict`; add the label to `STATE_WORDS` in `views/words.py` and its twin in `static/js/parts.js`.
- [ ] **Step 4: Run** `uv run pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** "Keep a skill's Name only state and show it".

### Task 5: The Name only switch

**Files:**
- Modify: `src/kitden/changes/actions.py:1439-1500` (`_claude_rule_steps`, `skill_rule_steps`), `src/kitden/clients/claude_code.py:317-325`, `src/kitden/views/after.py:782-800`, `src/kitden/views/words.py:63`, `src/kitden/web/static/js/tray.js` (`queued`), `src/kitden/web/static/js/library-rules.js:49` (`skillRuleWaits`)
- Test: `tests/unit/test_skill_rule.py`, `tests/frontend/tray.test.mjs`

**Interfaces:**
- Produces: `skill.rule` takes `params.state` in `{"off", "name-only", "on"}`; `params.off` stays and means `state = "off" if off else "on"` when `state` is absent. `ClaudeCodeAdapter.skill_rule_steps(name: str, project: str | None, state: str) -> list[Step]` writes `"off"`, `"name-only"`, or `ABSENT` for `"on"`. Codex refuses `"name-only"` with `"Codex has no Name only setting."`; plugin skills keep `PLUGIN_SKILL`.

- [ ] **Step 1: Write the failing tests**: `test_name_only_writes_skill_overrides_and_undo_restores` (preview → `"name-only"` in `settings.json`, Apply, Undo → file as before); `test_codex_refuses_name_only`; `test_after_words_say_name_only`; in JS, `queued()` treats a pending `state: "name-only"` row as queued for that state only.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement**; `AFTER_WORDS["skill.rule"]` and `_skill_rule_words` take the state's own word from `STATE_WORDS`.
- [ ] **Step 4: Run** all three checks. Expected: PASS.
- [ ] **Step 5: Commit** "Skills can be set to Name only in Claude Code".

### Task 6: The Context read model

**Files:**
- Create: `src/kitden/views/context_view.py`
- Modify: `src/kitden/web/app.py` (route `/api/context` via `_read_model`), `src/kitden/views/words.py` (every sentence below)
- Test: `tests/unit/test_context_view.py`, `tests/unit/test_api_views.py` (`ENDPOINTS`)

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `context_view(inventory, home: Path, codex_home: Path, folder: str | None, draft: dict[str, dict[str, str]]) -> dict` and the route `GET /api/context?project=<id>&draft=<json>`. `draft` maps client → skill name → state, from the tray. JSON:

```
{"clients": [{
  "client": "claude_code" | "codex" | "cursor",
  "lamp": "ok" | "warn" | "none",
  "lede": str,                       # spec "What the screen shows" 1
  "message": str | None,             # no chat / unreadable / no skills / Cursor
  "unit": "characters" | "tokens",
  "fact": {"date": "Nov 6", "surface": str | None, "folder": str | None, "version": str} | None,
  "checked": bool,                   # the rule rebuilt the last list
  "windows": [{"title": "1M window", "models": "Opus 5.5 · in the Claude app",
               "tag": "Last chat · Nov 6" | "Estimate" | "Set in config.toml",
               "budget": int, "result": {"short": str, "say": str,
               "sent": {name: int}, "over": {name: int}, "used": int, "size": int}}],
  "sides": [str, str], "skills": [{"name": str, "shown": str, "item": str | None, "size": int,
               "side": 0 | 1 | None, "state": str, "switch": [str], "note": str | None}],
  "after": {"say": str, "gets": [str], "loses": [str]} | None,
  "how": [str]}]}
```

- [ ] **Step 1: Write the failing tests**, each from a sandbox home with Task 2/3 fixture logs, asserting the spec's exact sentences (the "States" table):
  - `test_claude_everything_fits_is_a_fact_and_the_room_is_an_estimate` → `"In your last chat on Nov 6, all 3 skills were sent with their descriptions."` and a window `say` starting `"Estimate: about"`.
  - `test_claude_too_many_names_the_count` → `"In your last chat on Nov 7, 2 of 4 skills showed only a name. The agent may not have used them."`
  - `test_a_rule_that_does_not_rebuild_the_list_shows_no_estimate` → `checked is False`, only the fact window, `message == "Kitden cannot check its estimate against your last chat, so it shows none."`
  - `test_no_chat_yet`, `test_unreadable_log` (`"Kitden cannot read chat logs of Claude Code 2.2.0 yet, so it shows no result and no estimate."`), `test_no_skills` (`"There is nothing to fit."`), `test_cursor_has_no_verdict`.
  - `test_codex_cut_short` → `"In your last chat on Oct 30, 2 of 3 descriptions were cut to 40–41 characters. The agent saw only their start."` (numbers from the fixture).
  - `test_codex_left_out`, `test_codex_limit_from_config_toml` (`[skills] max_context_tokens = 900` → a window tagged `"Set in config.toml"`).
  - `test_a_draft_name_only_shows_after_apply_with_both_sides` → `after.say` starts `"After Apply, estimate:"`, `gets` and `loses` name the swapped skills.
  - `test_a_picked_project_without_its_own_chat_says_no_chat_yet` (Review Focus 4).
  - `test_a_budget_setting_that_is_not_a_number_is_ignored` (Review Focus 5).
  - `test_plugin_skills_have_no_switch_in_claude_code`, `test_cursor_skills_have_no_switch`.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_context_view.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Match log names to inventory items: a name `p:s` is plugin `p`'s skill `s` (`views/match.py` `plugin_of`); full descriptions come from `views/skills.py` `read_skill`. Claude weights read `~/.claude.json` `skillUsage[name] = {usageCount, lastUsedAt}` (checked 2026-11-09), aged from the list entry's timestamp. The limit is `env.SLASH_COMMAND_TOOL_CHAR_BUDGET` in Claude Code's settings files when it is a whole number, else `claude_budget(*CLAUDE_WINDOWS[model])`. The check is `claude_rule(...)` on the last list's skills and window equal to the log's full and name-only sets (Codex: equal `sent` lengths, `None` for skills on disk missing from the list); `ValueError` from a missing size means `checked = False`. "How this is counted" lines are the prototype's, with the real date and version.
- [ ] **Step 4: Run** all three checks. Expected: PASS.
- [ ] **Step 5: Commit** "Context: the read model for each client".

### Task 7: The Overview card

**Files:**
- Modify: `src/kitden/views/overview.py:314-346` (new `context_cards` keyword), `src/kitden/web/app.py:1016` (`_overview` passes it), `src/kitden/views/words.py`
- Test: `tests/unit/test_overview.py`

**Interfaces:**
- Consumes: `context_view` (Task 6).
- Produces: one `_card(..., group="attention", icon="gauge", …)` per client whose last chat was not a fit: line `"27 skills were cut short in your last Codex chat"` / `"46 skills showed only a name in your last Claude Code chat"` / `"14 skills were left out of your last Codex chat"`, action `{"label": "Show…", "go": {"view": "context", "sel": "client:codex"}}`. None when it fits, none for Cursor.

- [ ] **Step 1: Write the failing tests** `test_a_list_that_did_not_fit_gets_a_card` and `test_a_list_that_fits_gets_no_card`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement**; order the cards after `came_back`.
- [ ] **Step 4: Run** all three checks. Expected: PASS.
- [ ] **Step 5: Commit** "Overview says when a skill list did not fit".

### Task 8: The page shell

**Files:**
- Create: `src/kitden/web/static/js/context.js`
- Modify: `src/kitden/web/static/index.html:16-21` (rail link after Library), `src/kitden/web/static/js/app.js` (`PLACES`, `drawIcons`, `PROJECT_PLACES`), `src/kitden/web/static/js/store.js` (`VIEWS`, `data.context`, `loadContext()` in `reload()`), `src/kitden/web/static/js/panel.js:39` (`FLOATS`), `src/kitden/web/static/js/review.js:526` (`drawsInPlace`), `src/kitden/web/static/js/icons.js` (Lucide `gauge`), `src/kitden/web/static/style.css`
- Test: `tests/frontend/context-page.test.mjs` (not `context.test.mjs`, which exists), `tests/frontend/icons.test.mjs` (51 icons)

**Interfaces:**
- Consumes: `/api/context` (Task 6).
- Produces: `export function renderContext(main, { again = false } = {})`; address `#context?sel=client:codex` picks the client (default: the first with a lamp that is not `ok`, else Claude Code).

- [ ] **Step 1: Write the failing tests** (fake DOM as in `changes.test.mjs`): the rail has "Context" after "Library" with `dataset.icon === "gauge"`; `renderContext` draws h1 `"Do your skills fit?"`, the lede, three client chips with lamps, the window cards with their tags, and the verdict sentence from the fixture JSON; `sel=client:codex` shows Codex.
- [ ] **Step 2: Run** `node --test tests/frontend/context-page.test.mjs`. Expected: FAIL.
- [ ] **Step 3: Implement** following `changes.js` (`riseHead`, `setHint`, `banner`/`skeleton` while loading); a window card press shows that window's result.
- [ ] **Step 4: Run** all three checks. Expected: PASS.
- [ ] **Step 5: Commit** "Context page: title, clients, windows and verdict".

### Task 9: The picture, the switches and the estimate after Apply

**Files:**
- Modify: `src/kitden/web/static/js/context.js`, `src/kitden/web/static/js/dock.js:113` (`appliedToast`), `src/kitden/web/static/style.css`
- Test: `tests/frontend/context-page.test.mjs`

**Interfaces:**
- Consumes: `addToTray(body, {note})` / `onTray(fn)` (`tray.js`), `detailsCard`, `openPanel`, `keepFrom` (`details.js`, `panel.js`), `/api/context?draft=`.
- Produces: none for later tasks.

- [ ] **Step 1: Write the failing tests**:
  - the zoom bar has one piece per skill, widths in proportion to `result.sent`, a limit line labelled `"Limit: 8,000 characters"`, over-limit pieces hatched with `"Over the limit: not sent"` (Codex `"cut off"`), else `"Free"`;
  - the two sides list pills by `side`; hovering a pill marks its bar piece and the reverse;
  - a pill press opens Details with the size, source and a switch of `switch` values; choosing Name only adds `{action: "skill.rule", targets: [{client, item}], params: {scope: "all", state: "name-only"}}` to the tray;
  - a tray change asks `/api/context?draft=…` and shows `after.say`, lighting `loses` in amber;
  - after Apply from this page the toast says `"Applied 2 changes. The backup is in Changes. Your next chat will show the real list."`;
  - with `checked: false`, no estimate cards and no "After Apply" text.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** after the prototype's `drawBar`, `drawSides`, `drawInsp`; "How this is counted" is a `details` element with `how` lines. Motion: 240 ms `--calm` for the bar, one active element at a time.
- [ ] **Step 4: Run** all three checks. Expected: PASS.
- [ ] **Step 5: Commit** "Context page: the list picture and its switches".

### Task 10: Docs and a check in the real app

**Files:**
- Modify: `docs/guide.md`, `ROADMAP.md` ("Not released yet"), `docs/design.md` (a Context section), `docs/superpowers/specs/2026-11-09-skill-fit-design.md` (Codex window: from `models_cache.json`, since `session_meta.context_window` is only an id)

- [ ] **Step 1:** Add to the guide one short paragraph: what Context shows, that it reads only the skill list from the last chat log, and that Cursor gets no verdict.
- [ ] **Step 2:** ROADMAP line: "**Context: do your skills fit?** A new page shows what Claude Code and Codex sent in your last chat, and switches a skill to Name only or Off."
- [ ] **Step 3:** Run Kitden on a fixture home (`tests/fixtures` + fixture logs) and on the owner's real home, read-only; compare each client's result with the prototype's numbers; note any difference in the PR.
- [ ] **Step 4:** Run all three checks. Expected: PASS.
- [ ] **Step 5: Commit** "Context: docs and roadmap".
