<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/hero-dark.svg">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/hero.svg" width="100%" alt="Kitden: Your AI coding tools, under one roof.">
</picture>

<h3 align="center">Your AI coding tools, under one roof.</h3>

<p align="center"><b>See and safely change what your AI coding agents load.</b><br>
Claude Code, Codex and Cursor: every MCP server, skill, plugin, hook and marketplace on one local page.<br>
Look at each change first. Apply keeps a backup for Undo.</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/overview-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/overview.jpg" alt="Kitden Overview: a file Kitden could not read, servers to move into the gateway, Cursor to connect, and a small map of your setup" width="860">
  </picture>
</p>

```bash
uvx kitden
```

## Why

You use two or three AI coding tools. A few weeks in, a plugin loads twice, a server you removed
still runs in another tool, and an agent changed its own settings. Kitden reads all their settings
files, shows them on one page, and changes a file only after you have seen the exact edit.

It runs on your Mac at `127.0.0.1`, with no account and no telemetry. Secrets stay on this Mac.
They go only to the server they belong to, or to a gateway you move that server into.

## What you can do

- **Overview:** what needs your attention and what can improve, each with one button.
- **Gateway:** one Kitden gateway for every client. Drag a server into it, press × on a link to
  take it away, and turn a tool on or off for all projects or for one.
- **Library:** plugins, skills and instruction files for each client, as a map or a list. Drag a
  plugin onto a client to add it there; "Add missing plugins and skills…" fills the gaps.
- **Preview, then Apply:** every change waits in one tray, and "Show changes" shows the exact edit.
  Apply all writes it as one change with a backup; Undo all takes it back.
- **Changes:** the history, with Undo, "Redo…" and "See it on the map".
- **Ask your agent:** "show my setup" from Claude Code, Codex or Cursor. Kitden's own tools only
  read. Servers moved into the gateway add their tools, which do what those servers do.

Kitden writes only in your home folder and your known projects.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway.jpg" alt="The Gateway map: Claude Code and Codex linked to the Kitden gateway and its two servers; below, the servers outside the gateway, each joined to its client by a dotted line" width="860">
  </picture>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library.jpg" alt="The Library map: Claude Code, Codex and Cursor linked to the plugins and skills they load, grouped by where they come from" width="860">
  </picture>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/changes-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/changes.jpg" alt="The Changes page: three changes today, one of them undone; the Details of the newest show the project, the backup, what to restart and the history" width="860">
  </picture>
</p>

## Install

macOS. With [uv](https://docs.astral.sh/uv/):

```bash
uvx kitden
```

To try it on a sample setup first, with nothing on your computer read or changed: `uvx kitden demo`.

Without uv, one line installs uv and Kitden, then opens the page:

```bash
curl -LsSf https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.sh | sh
```

From inside your agent:

| | |
| --- | --- |
| **Claude Code** | `/plugin install kitden --marketplace KonstantinStarovoytov/kitden` |
| **Codex** | `codex plugin marketplace add KonstantinStarovoytov/kitden`, then `codex plugin add kitden@kitden` |
| **Cursor** | [![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=) |

Then ask your agent **"show my setup"**. Cursor also takes the plain link
`cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=`.

Linux and Windows are not supported yet.

## How it works

1. Kitden reads your agents' settings files and shows them in your browser, at `127.0.0.1` only.
2. You press Apply all. Kitden backs the files up, writes the change and checks it.
3. Undo brings the old files back. Backups stay for 30 days, and the newest 100 changes always keep
   theirs.

Secrets are never shown or logged. Kitden goes online only to reach the remote servers you add,
and to read a marketplace file from GitHub when you add a marketplace by its link.

## More

- [Roadmap](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md) and [issues](https://github.com/KonstantinStarovoytov/kitden/issues)
- [Release notes](https://github.com/KonstantinStarovoytov/kitden/releases)
- [Develop and release](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/development.md)
- [Visual and motion rules](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/design.md)
- License: [Apache-2.0](https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE)
