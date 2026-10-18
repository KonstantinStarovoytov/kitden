# Implementation Plan: One-line install

**Branch**: `003-one-line-install` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-one-line-install/spec.md`

## Summary

Publish Kitden: a tag push runs the tests, builds the package and creates a GitHub release
(PyPI publishing comes later, by the owner's decision). Then one `uvx` command from the GitHub
repository runs the page with nothing installed. Add one install line (a script that installs uv when missing, installs Kitden as a uv
tool and opens the page; it stops on Linux and Windows until they are supported). Add one plugin
folder that Claude Code and Codex install from the repository, with a short skill and the
read-only server entry `kitden mcp`, and an "Add to Cursor" button for the same entry. Teach the
Agents place to recognise a server a plugin provides. The MCP server itself does not change.

## Technical Context

**Language/Version**: Python 3.13+ (unchanged); POSIX `sh` and PowerShell for the install
scripts; JSON and Markdown for the plugin; YAML for the workflow

**Primary Dependencies**: no new runtime dependency. Tooling: uv (build, publish, tool install),
GitHub Actions, `gh` on the runner; PyPI Trusted Publishing later

**Storage**: none new. Plugin files live in the repository; clients copy them into their own
plugin folders

**Testing**: pytest (unit tests for the plugin files and the install script with fake commands;
contract tests with the real `claude` and `codex` in sandbox homes); the release workflow checks
the built files; the quickstart on a clean macOS user account and the three real clients

**Target Platform**: macOS (unchanged). The scripts refuse Linux and Windows for now

**Project Type**: local CLI with a local page and a stdio MCP server, plus a client plugin and a
release pipeline

**Performance Goals**: first `uvx kitden` under 2 minutes, later ones under 10 seconds; the install
line under 3 minutes; a release visible within 15 minutes (SC-001 to SC-003)

**Constraints**: no stored secret anywhere; nothing writes to a client without the user's own
action in that client; the plugin adds no hooks or executables; the MCP server stays read-only

**Scale/Scope**: one maintainer, one package, one plugin folder, three clients

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
| --- | --- | --- |
| I. Clear communication | Spec, plan, scripts' messages and the skill in simple English; tables for the options; owner talk in Russian | Pass |
| II. Specify before building | Spec with open owner decisions labeled; every vendor claim in research links a primary source with the review date; `codex plugin add` checked on the real binary | Pass |
| III. Safe changes | No path in this feature writes to a client. The plugin's server and the Cursor button are added by the client itself after the user's own command and confirmation; the install line only installs | Pass |
| IV. Honest and private | The Agents place shows plugin-provided servers as such; the source distribution ships no fixtures; the skill never asks the agent to read or edit settings files; nothing leaves the machine except what the user publishes | Pass |
| V. Verify against real clients | Contract tests with real `claude` and `codex` in sandbox homes; the quickstart on the Claude Desktop Code tab, the Codex app and CLI, and Cursor, with versions recorded; the documented-only claims (Codex CLI starting a plugin server, Cursor's file) are named as checks, not facts | Pass |
| VI. Local and simple | No server, account or login for use. New moving parts: one workflow file, two scripts, one plugin folder, two marketplace files. The plugin server starts the installed `kitden`, not a second copy (research R6) | Pass, see note |

Note on VI: the release pipeline is new infrastructure, but it runs on GitHub, not on the user's
machine, and it replaces manual uploads and a stored token. The plugin keeps the MCP contract and
adds no runtime code.

Re-check after Phase 1: no change. The only runtime code change is the `plugin` state on the
Agents place (research R8), a read-only view.

## Project Structure

### Documentation (this feature)

```text
specs/003-one-line-install/
├── plan.md              # This file
├── research.md          # Decisions R1–R11 with sources
├── data-model.md        # Release, install run, plugin package, setup server states
├── quickstart.md        # How to check the feature on real machines and clients
├── contracts/
│   ├── release.md       # The tag → PyPI → GitHub release pipeline
│   ├── install-scripts.md
│   ├── plugin-package.md
│   └── mcp-tools.md     # Unchanged server; how clients start it
└── tasks.md             # Made by speckit-tasks
```

### Source Code (repository root)

```text
.github/workflows/release.yml      # new: test, build, publish, release (R1)
.claude-plugin/marketplace.json    # new: Claude Code marketplace, one entry (R5)
.agents/plugins/marketplace.json   # new: Codex marketplace, one entry (R5)
plugins/kitden/                    # new: the plugin both clients install (R5, R6)
├── .claude-plugin/plugin.json
├── plugin.json
├── .mcp.json
├── mcp.json
├── skills/setup/SKILL.md
└── README.md
install.sh                         # new: the macOS/Linux install line (R4)
install.ps1                        # new: the Windows line; stops until Windows is supported
LICENSE                            # new, after the owner's decision
pyproject.toml                     # metadata, sdist contents (R2)
README.md                          # install section first; maintainer section
src/kitden/views/setup_server.py   # the `plugin` state (R8)
src/kitden/web/static/js/agents.js # "Provided by the kitden plugin"

tests/
├── unit/test_plugin_package.py    # new
├── unit/test_install_script.py    # new
├── unit/test_setup_server.py      # plugin state
└── contract/test_plugin_install.py  # new: real claude and codex in sandbox homes
```

**Structure Decision**: keep the single package. The plugin is a folder of files next to the
code, not a second package, so one repository holds the engine, the marketplace and the plugin,
as Claude Code's publish page describes.

## Complexity Tracking

No constitution violations to justify.
