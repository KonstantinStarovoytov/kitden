# Kitden

**One local page that shows what each AI coding client actually loads, where each item comes from,
and what loads twice, with safe on/off toggles.** Clients: Claude Code (including the Claude
Desktop Code tab), Codex and Cursor.

**Stage:** 0.1.0 is the first public version. Earlier working versions were never published:
feature 001 built the page ([validation](specs/001-agent-setup-inventory/validation.md)),
feature 002 named it Kitden, feature 004 polished the design.

```mermaid
flowchart LR
    U[Developer] --> P[One local page]
    P -->|read everything| C[Claude Code, Codex, Cursor]
    P -->|plugins on/off,<br/>one gateway entry| C
    C -->|MCP calls| G[MCP gateway<br/>Obot or MetaMCP]
    U -->|tools on/off| G
```

The page shows MCP servers, skills, plugins, hooks and marketplaces for every client, with the
source file and scope of each item, and points out cross-loading and duplicates. MCP tools are
managed in an existing gateway (gateway first): the page connects it to every client once and flags
MCP servers that bypass it. Writes happen only after an explicit "Apply" and can be undone.
A read-only "show my setup" MCP server gives agents the same answer. Team administration and
Langfuse export come later.

## Install

Kitden runs on macOS. Paste one line into the Terminal:

```bash
curl -LsSf https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.sh | sh
```

It installs [uv](https://docs.astral.sh/uv/) if you do not have it (uv's installer also puts its
folder on your shell's PATH), installs the `kitden` command in its own folder, and opens the page.
It changes nothing in Claude Code, Codex or Cursor. Run the same line later to update. Until Kitden
is on PyPI, uv fetches it from this repository and needs git, which comes with the macOS command
line tools; the line says so if they are missing. Windows gets the same with PowerShell once Windows is supported:
`powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.ps1 | iex"`.

Already have uv? Run Kitden without installing it:

```bash
uvx --from git+https://github.com/KonstantinStarovoytov/kitden@v0.1.0 kitden
```

Without `@v0.1.0` it runs the latest code on `main`; this form needs git too. `uvx kitden` will work
once Kitden is on PyPI.

### From inside your coding agent

Each of these adds the read-only "show my setup" server to that client, after the client asks you.
Kitden itself still needs the line above.

| Client | Do this | What it adds |
| --- | --- | --- |
| Claude Code (2.1.275 or newer) | In a session: `/plugin install kitden --marketplace KonstantinStarovoytov/kitden`. From the shell: `claude plugin marketplace add KonstantinStarovoytov/kitden`, then `claude plugin install kitden@kitden` | The `kitden` plugin: one skill and the server `kitden mcp` |
| Codex | `codex plugin marketplace add KonstantinStarovoytov/kitden`, then `codex plugin add kitden@kitden` | The same plugin |
| Cursor | [![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=) or paste `cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=` into the browser | One MCP entry, `kitden mcp` |

Then ask the agent: "show my setup". The skill tells it to answer with the kitden tools and to open
the page with `kitden open` instead of editing settings files. Remove the plugin with
`claude plugin uninstall kitden@kitden` or `codex plugin remove kitden@kitden`.

## Linux and Windows

Not supported yet: the install scripts stop with a message, and `uvx` runs but the page looks for
macOS paths. Support for both is a later feature.

## Use it

```bash
kitden
```

This opens the page in the browser and returns at once. If the page already runs, the same page
opens; only one runs at a time. A coding agent can run `kitden open` too. The page stops by itself
10 minutes after its last tab closes. To run it in the terminal instead, use `kitden serve` and
stop it with Ctrl+C (if a page already runs, `kitden serve` opens that one).

| I want to | On the page | What changes |
| --- | --- | --- |
| See what needs attention | **Overview** | Nothing |
| See what each client loads, here or in one project | **Load map** (pick a project in **Where**) → click a row for where it comes from | Nothing |
| Add my MCP gateway to all clients | **Gateway** → Add a gateway → Connect clients → Preview → Apply | One user-level entry per client; a key is stored only as a variable name |
| See MCP servers that are not connected to the gateway | **Gateway** → the three groups below the diagram | Nothing |
| Remove an old direct MCP entry | **Load map** → row → Remove from … → Apply, or **Gateway** → Remove… | That entry |
| Turn a plugin on or off (Claude Code, Codex) | **Load map** → Plugins → row → Turn off in … / Turn on in … → Apply | The plugin's on/off flag |
| Install or move a plugin, add a marketplace | **Load map** → row → Commands… | Nothing: the page shows the command, you run it |
| Let agents see this setup | **Let agents read this setup** (bottom of the left rail) → Add… → Apply, or install the plugin (see Install) | One entry per client for `kitden mcp` |
| Undo a change | Undo in the note after Apply, or **Changes** → Undo | The previous file content comes back |

Other commands: `kitden scan --json` prints the same inventory and exits; `kitden mcp` is the
read-only server that clients start.

**Coming from `agentsetup`.** Kitden copies the old data folder once (gateways, history and Undo
carry over) and leaves the old folder as it is. If you added "show my setup" with the old version,
the page shows an "Old entry" card: use **Update to Kitden…** for each client. If you had installed
the old version with `uv tool install`, remove it with `uv tool uninstall agentsetup`; if you ran it
from the repository, there is nothing else to remove.

**Safety.** Every change is shown first and written only after Apply. Before writing, the tool
saves a private backup (`~/Library/Application Support/kitden/changes`, kept for 30 days or the
last 100 changes). It stops if a file changed after the preview, reads the file again after
writing, and puts the backup back if the result is wrong. Undo stops if the file changed after the
change.

**Privacy.** The page answers only on `127.0.0.1` and needs the start link. Secret values are never
shown or logged, and the tool itself opens no network connections. One thing to know: to show the
on/off state of Codex remote plugins, it runs `codex plugin list --json`, and Codex then asks
chatgpt.com for your installed plugins.

## Develop

Clone the repository, then `uv sync` and `uv run pytest -q`. `uv tool install .` gives you the
`kitden` command from this folder (`uv tool install --reinstall .` after new code). Contract tests
against the real clients run in sandbox homes with `uv run pytest -m contract`.

## For maintainers

A release is one tag push: set the version with `uv version X.Y.Z`, put the same number in
`plugins/kitden/.claude-plugin/plugin.json` and `plugins/kitden/plugin.json`, name the tag in
`KITDEN_REF` of `install.sh` and `install.ps1`, commit, then `git tag vX.Y.Z` and
`git push origin main vX.Y.Z`. The workflow runs the checks, builds the package and creates the
GitHub release with the built files. The one-time steps (the public repository, and later the
PyPI publisher and the `pypi` environment) are in
[research R11](specs/003-one-line-install/research.md#r11-owner-steps-outside-the-code-once).
Publishing to PyPI comes later (see the
[release contract](specs/003-one-line-install/contracts/release.md)); the name `kitden` should be
registered with that first release.

## Start here

| Document | Purpose |
| --- | --- |
| [Project brief](docs/project-brief.md) | Product goal, users, success, first release scope, and open questions |
| [Feature 001 spec](specs/001-agent-setup-inventory/spec.md) | First release specification: user stories, requirements, success criteria |
| [Feature 002 spec](specs/002-kitden-rename/spec.md) | The Kitden name, `kitden open`, one page per computer |
| [Feature 003 spec](specs/003-one-line-install/spec.md) | One-line install: the install line, `uvx` from the repository, the plugin for Claude Code and Codex, the Cursor button |
| [Naming and licensing](docs/research/naming-and-licensing-2026-10-17.md) | How the name Kitden was chosen; license options |
| [Brief review](docs/research/brief-review-2026-10-17.md) | Independent review by two models: scores, missed competitors, recommended cuts, experiments |
| [Gateway trial](docs/research/gateway-trial-2026-10-16.md) | MetaMCP and Obot tested with Codex and agent-docs; cross-client setup research |
| [Gateway research](docs/research/mcp-gateway-landscape.md) | Existing MCP gateways, security practices, and reading list |
| [Design skills and tools](docs/research/design-skills-and-tools-2026-10-17.md) | Agent skills and tools for UI design and review, with risks and a proposed way of working |
| [Architecture proposal](docs/architecture/overview.md) | Gateway architecture from the earlier idea; superseded for the first release |
| [Constitution](.specify/memory/constitution.md) | Project principles, version 2.1.1 (amended 2026-10-18) |
| [Spec Kit workflow](docs/spec-kit-workflow.md) | Installed tooling and next development steps |

## Working language

Discuss work in simple Russian. Write code, UI text, and documentation in simple English.
Use diagrams and tables where they make the idea easier to understand.

## Approach

Do not build another MCP gateway: MetaMCP and Obot already cover tool access and blocking. This
tool is the narrow, read-first page from the [project brief](docs/project-brief.md). Its gap
against [Cross-Code Organizer](https://github.com/mcpware/cross-code-organizer), the closest
existing tool, is Cursor, plugins and marketplaces, and cross-client loading.

Built with Python 3.13+, uv, Starlette and the official MCP SDK
([plan](specs/001-agent-setup-inventory/plan.md)). Research reviewed on **2026-10-16 and
2026-10-17**.
