# Tasks: One-line install

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required for code (scripts, the `plugin` state, the plugin files); write each test
first and watch it fail. Documentation-only changes get a consistency and link check.

Format: `[ID] [P?] [Story] Description`. `[P]` = can run in parallel (different files).

## Phase 1: Setup

- [ ] T001 Package metadata in `pyproject.toml`: version 0.1.0 (`uv version 0.1.0`; the first
  public version), `license = "Apache-2.0"` and `license-files`, classifiers (macOS, Python 3.13
  and 3.14), `[project.urls]`, keywords, and
  `[tool.hatch.build.targets.sdist] only-include = ["src/kitden", "README.md", "LICENSE"]`.
  Add `LICENSE` (Apache-2.0). Tests first in `tests/unit/test_release_files.py`: the version in
  `pyproject.toml` equals `kitden.__version__` and is `0.1.0`; `LICENSE` exists and names the
  Apache License; the `license` field is `Apache-2.0`. Check the build with the commands of
  [quickstart §1](quickstart.md#1-the-built-package-any-machine-with-uv)
  ([R2](research.md#r2-package-metadata-and-contents), [R10](research.md#r10-versions-and-the-first-release)).
- [ ] T002 [P] Workflow `.github/workflows/release.yml` per
  [contracts/release.md](contracts/release.md): job `build` on every push, pull request and tag
  (macOS: uv, ruff, pytest, on a tag the tag equals the version, `uv build`, sdist and wheel
  checks, wheel smoke test, upload); job `release` on tags only (`contents: write`,
  `gh release create … --generate-notes --verify-tag`). Pin the actions and the uv version
  ([R1](research.md#r1-release-pipeline)). No PyPI job yet (T017).

## Phase 2: US1 — Run with one command, nothing installed (P1) 🎯 MVP

**Goal**: one `uvx` command from the GitHub repository runs the page; a tag push releases.
**Independent test**: quickstart §1 and §2.

- [ ] T003 [US1] README: a new "Install" section at the top with
  `uvx --from git+https://github.com/<owner>/kitden kitden`, the pinned `@v0.1.0` form, and a
  line that this is the first public version; a "For maintainers" section with the release steps
  and the owner's one-time steps ([R3](research.md#r3-run-without-installing),
  [R11](research.md#r11-owner-steps-outside-the-code-once)). Replace the "Use it" clone
  instructions; keep `uv tool install .` as the developer path under "Develop".
- [ ] T004 [US1] Owner, once: create the public repository `<owner>/kitden` in the personal
  profile and give the login (R11). Builder, then: replace every `<owner>` placeholder in the
  repository with it.

**Checkpoint**: quickstart §2 passes from the git form on a clean account.

## Phase 3: US2 — Install with one line (P1)

**Goal**: one line installs uv when missing, installs Kitden and opens the page; refuses other
systems.
**Independent test**: quickstart §3.

- [ ] T005 [US2] Tests first in `tests/unit/test_install_script.py` with fake `uv`, `curl` and
  `uname` on PATH and a temporary home: macOS without uv → installer called, `tool install` with
  the git source and the script's `KITDEN_REF`, `kitden` run from the tool folder, PATH hint; uv
  present → no installer; Linux → exit 1 and no call; failures give exit 2 and 3 with the
  contract messages. Then write `install.sh` per
  [contracts/install-scripts.md](contracts/install-scripts.md)
  ([R4](research.md#r4-the-install-line-and-the-scripts)).
- [ ] T006 [P] [US2] `install.ps1` with the same five steps and uv's PowerShell line; step 1 stops
  on Windows with the contract message. Syntax check with `pwsh -NoProfile` when `pwsh` exists;
  otherwise record "not verified on Windows" in the quickstart table.
- [ ] T007 [US2] README: the two install lines first in the "Install" section, each with one line
  on what it changes (installs uv and the `kitden` command; nothing in any client) and the
  Windows line marked "coming with Windows support" (FR-016).

**Checkpoint**: quickstart §3 passes on a clean account without uv.

## Phase 4: US3 — Install from inside Claude Code (P2)

**Goal**: one plugin command gives the skill and the read-only server.
**Independent test**: quickstart §4.

- [ ] T008 [US3] Tests first in `tests/unit/test_plugin_package.py`: every JSON file parses; names
  and marketplace name are `kitden`; both manifest versions equal `kitden.__version__`;
  `.mcp.json` equals `mcp.json` and holds only the stdio entry `kitden mcp`; the skill has
  `name`, `description` and the four rules; no `hooks/`, `commands/`, `bin/`, `agents/`. Then
  write `plugins/kitden/` (both manifests, both MCP files, `skills/setup/SKILL.md`, `README.md`),
  `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` per
  [contracts/plugin-package.md](contracts/plugin-package.md) ([R5](research.md#r5-one-plugin-folder-for-claude-code-and-codex),
  [R6](research.md#r6-how-the-plugin-starts-the-server)). `claude plugin validate --strict` on
  both passes.
- [ ] T009 [P] [US3] Tests first in `tests/unit/test_setup_server.py`: state `plugin` when a client
  has a `kitden` MCP server from a plugin source; `added` wins when a user-level entry exists
  too; Cursor never `plugin`; `tests/unit/test_findings.py`: the pair is a duplicate. Then
  `src/kitden/views/setup_server.py` and the Agents place text "Provided by the kitden plugin"
  with no Add button in `src/kitden/web/static/js/agents.js`
  ([R8](research.md#r8-the-page-and-plugin-provided-servers)). Browser check with `--home`.
- [ ] T010 [US3] Contract test `tests/contract/test_plugin_install.py` (marker `contract`, sandbox
  home as in `tests/contract/test_mcp_handshake.py`): `claude plugin validate --strict` on the
  plugin and the marketplace; `claude plugin marketplace add <repo path>`; `claude plugin install
  kitden@kitden`; `claude plugin list` shows it enabled; uninstall; the sandbox settings file
  keeps every other key ([R9](research.md#r9-testing)).
- [ ] T011 [US3] README: the Claude Code command (in-session form, 2.1.275+; the two shell commands)
  and what it changes (the client adds the plugin; the server runs the installed `kitden`).

**Checkpoint**: quickstart §4 passes in the terminal and in the Claude Desktop Code tab; if the
Code tab fails on PATH, apply the R6 fallback and record it.

## Phase 5: US4 — Codex and Cursor (P3)

**Goal**: the same plugin in Codex; a button for Cursor.
**Independent test**: quickstart §5 and §6.

- [ ] T012 [US4] Extend `tests/contract/test_plugin_install.py`: `codex plugin marketplace add
  <repo path>`, `codex plugin add kitden@kitden`, `codex plugin list --json` shows it, remove;
  `config.toml` keeps every other table (R7, R9).
- [ ] T013 [P] [US4] README: the Codex commands and the "Add to Cursor" button with the plain link
  as text, per the contract. Add to `tests/unit/test_plugin_package.py`: the README's Cursor link
  decodes to the `.mcp.json` entry.

**Checkpoint**: quickstart §5 and §6 pass; the Cursor file and the Codex CLI result are recorded.

## Phase 6: Polish

- [ ] T014 [P] Docs consistency: README says Python 3.13+ everywhere (today one line says 3.14);
  the brief's "Install and use" points to the README's Install section; `docs/spec-kit-workflow.md`
  unchanged. Link check over the new files.
- [ ] T015 Full checks: `uv run pytest -q`, contract tests, ruff; quickstart §1–§6 on the real
  machines with the versions table filled in.
- [ ] T016 Owner: the first release, `v0.1.0` (quickstart §7, SC-003).

## Later (not in this feature)

- [ ] T017 PyPI: when the owner opens PyPI, add the `publish` job (`environment: pypi`,
  `id-token: write`, `uv publish`) between `build` and `release`, do the one-time steps of R11
  step 4, register the name `kitden` with that first publish, and switch the README and
  `install.sh` to the PyPI forms (`uvx kitden`, `uv tool install kitden`).

## Order

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 →
T014 → T015 → T016. T002, T006, T009, T013 and T014 touch separate files and can run beside the
task before them. T004 and T016 are the owner's; the builder does the rest.

## Strategy

MVP is US1 + US2: a released version and one install line. US3 and US4 add the client doors on
top. Commit after each task with a short plain message.
