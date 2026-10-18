<img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/src/kitden/web/static/brand/kitden.svg" width="48" height="48" alt="Kitden house">

# Kitden

**See what your coding agents load. Change it with confidence.**

Claude Code, Codex and Cursor each keep their own MCP servers, plugins, skills and hooks, in
their own files. Kitden shows all of them on one page and lets you change them safely.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/overview-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/overview.jpg" alt="The Kitden page: three things need attention, each with one button to fix it" width="800">
  </picture>
</p>

## The problem

You use more than one AI coding tool. After a few weeks:

- you do not know what loads where, or what loads twice;
- one tool quietly picks up another tool's plugins;
- settings get edited by hand, and sometimes by the agents themselves.

Nobody wants to open six JSON and TOML files to find out.

## What Kitden gives you

- **One page for all your agents.** Every MCP server, plugin, skill, hook and marketplace, with the
  file it comes from. Nothing to configure.
- **What needs attention.** Items that load twice, and MCP servers that go around your gateway.
- **Safe changes.** Turn a plugin off, remove an old entry, connect a gateway: you see the change
  first, Apply writes it with a backup, Undo puts it back.
- **Agents can ask too.** A read-only "show my setup" server answers "what do you load here?"
  without changing anything.

## How it works

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/how-it-works-dark.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/how-it-works.svg" alt="Kitden reads the settings of Claude Code, Codex and Cursor, shows them on one local page, and writes a change back with a backup you can undo" width="860">
  </picture>
</p>

1. Kitden reads the settings files of your agents. Nothing leaves your Mac.
2. It shows them on one page in your browser.
3. You press Apply. Kitden backs the file up, writes the change, and checks it. Undo brings the
   old file back.

## Install

macOS. If you have [uv](https://docs.astral.sh/uv/), nothing to install:

```bash
uvx kitden
```

No uv yet? Paste one line into the Terminal:

```bash
curl -LsSf https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.sh | sh
```

It installs uv, then `kitden`, and opens the page. It changes nothing in your agents. Run the same
line again to update. From then on:

```bash
kitden
```

Linux and Windows are not supported yet.

## From inside your agent

| | Do this | You get |
| --- | --- | --- |
| **Claude Code** | `/plugin install kitden --marketplace KonstantinStarovoytov/kitden` | A skill plus the read-only server |
| **Codex** | `codex plugin marketplace add KonstantinStarovoytov/kitden`, then `codex plugin add kitden@kitden` | The same plugin |
| **Cursor** | [![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=) | The read-only server |

Then ask: **"show my setup"**. The agent answers from Kitden, and opens the page with `kitden open`
when you want to change something. (The `kitden` command must be installed; see above. Cursor also
takes the plain link `cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=`.)

## Safe and private

- Every change is shown before it is written, and written only after Apply.
- Each write keeps a backup (30 days or the last 100 changes). Undo restores it exactly.
- The page answers only on your computer (`127.0.0.1`) and needs its start link.
- Secret values are never shown or logged, and Kitden makes no network calls of its own.

## More

- [Develop, release, and the project documents](docs/development.md)
- Supported clients: Claude Code 2.1.283 (and the Claude Desktop Code tab), Codex 0.163, Cursor 3.25
- License: [Apache-2.0](LICENSE)
