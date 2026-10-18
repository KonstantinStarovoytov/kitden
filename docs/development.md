# Developing and releasing Kitden

## Develop

Clone the repository, then `uv sync` and `uv run pytest -q`. `uv tool install .` gives you the
`kitden` command from this folder (`uv tool install --reinstall .` after new code). Contract tests
against the real clients run in sandbox homes with `uv run pytest -m contract`.

Built with Python 3.13+, uv, Starlette and the official MCP SDK
([plan](../specs/001-agent-setup-inventory/plan.md)).

## Release

A release is one tag push: set the version with `uv version X.Y.Z`, put the same number in
`plugins/kitden/.claude-plugin/plugin.json` and `plugins/kitden/plugin.json`, name the tag in
`KITDEN_REF` of `install.sh` and `install.ps1`, commit, then `git tag vX.Y.Z` and
`git push origin main vX.Y.Z`. The workflow runs the checks, builds the package, publishes it to
PyPI and creates the GitHub release with the built files
([release contract](../specs/003-one-line-install/contracts/release.md)). The one-time steps (the
public repository, the PyPI trusted publisher and the `pypi` environment) are in
[research R11](../specs/003-one-line-install/research.md#r11-owner-steps-outside-the-code-once).

## Other commands

`kitden scan --json` prints the same inventory as the page and exits. `kitden mcp` is the
read-only server that clients start. `kitden serve` runs the page in the terminal until Ctrl+C
(if a page already runs, it opens that one). A page started by `kitden` or `kitden open` stops by
itself 10 minutes after its last tab closes.

## Coming from `agentsetup`

Kitden copies the old data folder once (gateways, history and Undo carry over) and leaves the old
folder as it is. If you added "show my setup" with the old version, the page shows an "Old entry"
card: use **Update to Kitden…** for each client. If you had installed the old version with
`uv tool install`, remove it with `uv tool uninstall agentsetup`; if you ran it from the
repository, there is nothing else to remove.

## Linux and Windows

Not supported yet: the install scripts stop with a message, and `uvx` runs but the page looks for
macOS paths. Support for both is a later feature.

## Project documents

| Document | Purpose |
| --- | --- |
| [Project brief](project-brief.md) | Product goal, users, success, first release scope, and open questions |
| [Feature 001 spec](../specs/001-agent-setup-inventory/spec.md) | First release specification: user stories, requirements, success criteria |
| [Feature 002 spec](../specs/002-kitden-rename/spec.md) | The Kitden name, `kitden open`, one page per computer |
| [Feature 003 spec](../specs/003-one-line-install/spec.md) | One-line install: the install line, `uvx` from the repository, the plugin for Claude Code and Codex, the Cursor button |
| [Visual system](../DESIGN.md) | The Kitden house, colors and client marks ([feature 005 spec](../specs/005-den-brand/spec.md)) |
| [Design and install review](research/design-and-install-review-2026-10-18.md) | Fresh-eyes review of the page and the install path |
| [Naming and licensing](research/naming-and-licensing-2026-10-17.md) | How the name Kitden was chosen; license options |
| [Brief review](research/brief-review-2026-10-17.md) | Independent review by two models: scores, missed competitors, recommended cuts, experiments |
| [Gateway trial](research/gateway-trial-2026-10-16.md) | MetaMCP and Obot tested with Codex and agent-docs; cross-client setup research |
| [Gateway research](research/mcp-gateway-landscape.md) | Existing MCP gateways, security practices, and reading list |
| [Design skills and tools](research/design-skills-and-tools-2026-10-17.md) | Agent skills and tools for UI design and review, with risks and a proposed way of working |
| [Architecture proposal](architecture/overview.md) | Gateway architecture from the earlier idea; superseded for the first release |
| [Constitution](../.specify/memory/constitution.md) | Project principles, version 2.1.1 (amended 2026-10-18) |
| [Spec Kit workflow](spec-kit-workflow.md) | Installed tooling and next development steps |

## Working language

Discuss work in simple Russian. Write code, UI text, and documentation in simple English.
Use diagrams and tables where they make the idea easier to understand.

## Approach

Do not build another MCP gateway: MetaMCP and Obot already cover tool access and blocking. This
tool is the narrow, read-first page from the [project brief](project-brief.md). Its gap against
[Cross-Code Organizer](https://github.com/mcpware/cross-code-organizer), the closest existing
tool, is Cursor, plugins and marketplaces, and cross-client loading. Research reviewed on
2026-10-16, 2026-10-17 and 2026-10-18.
