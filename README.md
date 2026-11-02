<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/hero-dark.svg">
    <source srcset="docs/images/hero.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/hero.svg" width="640" alt="Kitden: Your AI coding tools, under one roof.">
  </picture>
</h1>

<p align="center"><strong>Your AI coding tools, under one roof.</strong></p>

<p align="center">See and share the MCP servers, plugins and skills<br>
that <b>Claude Code, Codex and Cursor</b> load.</p>

<p align="center">
  <a href="https://github.com/KonstantinStarovoytov/kitden/actions/workflows/release.yml"><img src="https://github.com/KonstantinStarovoytov/kitden/actions/workflows/release.yml/badge.svg?branch=main" alt="Checks on main"></a>
  <a href="https://github.com/KonstantinStarovoytov/kitden/releases/latest"><img src="https://img.shields.io/github/v/release/KonstantinStarovoytov/kitden?label=latest%20release" alt="Latest release"></a>
  <a href="https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0"></a>
</p>

### See what each agent loads

The plugins, skills and MCP servers of Claude Code, Codex and Cursor on one map. What one
agent has and another lacks shows at a glance.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme/library-dark.png">
  <source srcset="docs/images/readme/library-light.png">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/readme/library-light.png" width="470" alt="The Library map: Claude Code and Cursor load the superpowers plugin, Codex and Cursor load the frontend-design skill.">
</picture>

### Share servers across all agents

Move a server into the Kitden gateway and every agent you use gets it. Set it up once,
not once per agent.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme/pick-dark.webp">
  <source srcset="docs/images/readme/pick-light.webp">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/readme/pick-light.webp" width="450" alt="Context7 from Cursor, memory from Claude Code and playwright from Codex go into the Kitden gateway together, to be shared by all three.">
</picture>

### Turn tools off

Every tool of a server has a switch, for all projects or one. A tool that is off is refused,
not just hidden.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme/tools-dark.webp">
  <source srcset="docs/images/readme/tools-light.webp">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/readme/tools-light.webp" width="860" alt="memory in the Kitden gateway shows its nine tools; its three delete tools are turned off on the map and applied for every agent.">
</picture>

## And more

- **Find and add.** Search the official MCP Registry, skills.sh, the Claude plugins marketplace
  and any public GitHub repository. Drag a result onto a client or the gateway.
- **Fill the gaps.** A plugin or skill one agent has goes to the others in one step.
- **Tokens and sign-in, once.** Checked before Apply, kept in the macOS Keychain, refreshed by
  the gateway.
- **Per project.** Turn a server or a tool on or off for one project only.
- **See what runs.** How often each tool is called, and which tools only read.
- **Instructions in view.** Which CLAUDE.md, AGENTS.md, rules, hooks, commands and agents each
  client loads, and where they come from.
- **Ask your agent.** "Show my setup" works from any agent, through Kitden's own read-only
  MCP server.
## Safe to use

- **Nothing is written until you press Apply.** Every change shows a preview first, with
  the exact edit under Show changes.
- **Apply keeps a backup, and Undo puts it back.** If a file changed since, Kitden stops
  instead of overwriting it.
- **Everything stays on your Mac.** The page runs at 127.0.0.1 behind a private link. No
  account, no telemetry. Kitden goes online only for the catalogs you open and the remote
  servers you add.
- **Secrets live in the macOS Keychain only.** The page shows no more than their first and
  last characters.
- **Kitden's agent tools only read.** Asking an agent to show your setup changes nothing.

Add only servers and plugins you trust: they run with your permissions.

## Get started

Needs **macOS**, [uv](https://docs.astral.sh/uv/getting-started/installation/) and at least
one of **Claude Code, Codex or Cursor**.

Try it on a sample first. Your own settings are not read or changed:

<!-- Release checklist: docs/readme-media.md -->
```bash
uvx --python 3.13 kitden demo
```

Install it and open it for your own setup:

```bash
uv tool install --python 3.13 kitden && kitden
```

Update later with `uv tool upgrade kitden`.

[Guide](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/guide.md) ·
[Roadmap](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md) ·
[Releases](https://github.com/KonstantinStarovoytov/kitden/releases) ·
[Issues](https://github.com/KonstantinStarovoytov/kitden/issues) ·
[Contributing](https://github.com/KonstantinStarovoytov/kitden/blob/main/CONTRIBUTING.md) ·
[Apache-2.0](https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE)
