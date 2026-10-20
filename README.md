<img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/logo.svg" width="100%" alt="Kitden">

<h1 align="center">Kitden</h1>

<p align="center"><b>See and safely change what your AI coding agents load.</b><br>
Claude Code, Codex and Cursor: every MCP server, skill, plugin, hook and marketplace on one local page.<br>
Look at each change first, Apply it with a backup, Undo it any time.</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/overview-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/overview.jpg" alt="Kitden Overview: two things need attention, one thing can improve, and the four clients found" width="860">
  </picture>
</p>

```bash
uvx kitden
```

## Why you want it

You use two or three AI coding tools. A few weeks in:

- a plugin loads twice, because Cursor quietly reads Claude Code's plugins;
- an MCP server you removed from one tool still runs in another;
- an agent edited its own settings, and you are not sure what changed.

The answers are spread over many JSON and TOML files. Kitden reads them all, shows them on one
page, and changes a file only after you have seen the exact edit.

Kitden is for one developer or a small team. It runs on your Mac at `127.0.0.1`, with no account
and no telemetry.

## What you can do

### See what needs attention

**Overview** lists what needs attention, such as an item that loads twice, and what can improve,
such as servers that could move into your gateway. Each one has a button that opens its fix.
The clients Kitden found sit on the right.

### See what each client has, and add what it lacks

**Library** is one page for what each client loads and what you can add to it. Each row is an
item and each column is a client on this computer; the "−" on a column head hides that client,
and "Show" brings it back. Tabs split MCP servers, plugins, skills, hooks and marketplaces. On
plugins and skills, choose On this Mac, Can add or All, and filter by category. Pick a project at
the top to see what loads in that folder.

The action sits in the client's cell. "+ Add" adds a plugin or skill to that client. "Add
skills" copies the skills of a plugin into a client that cannot install the plugin itself. "Add
the plugin" is for a skill that needs its plugin. A cell with nothing to do says why. Each button
opens a review first. You can also add a marketplace from a folder or a GitHub link.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library.jpg" alt="Library: plugins in rows, a column for each client, and a + Add button in the cells where a client can take one" width="860">
  </picture>
</p>

### Use one gateway for every client

**Gateway** works with [Obot](https://obot.ai) (with OAuth sign-in) and MetaMCP. Connect your
clients, see what the gateway holds and which servers go around it, and move direct servers into
it one at a time or all at once. Switch every client to another gateway in one review. Click a
client in the diagram to open its app.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway.jpg" alt="Gateway: Claude Code, Codex and Cursor linked to an Obot gateway, what the gateway holds, and servers that can move into it" width="860">
  </picture>
</p>

### Check every change before it is written

Every change opens a review first: the clients it reaches (Cursor too, when it loads Claude
Code's plugins) and the exact file change, with secrets hidden. Apply keeps a backup, writes the
change and checks it. **Changes** keeps the history, with Undo and what to restart for a change
to take effect.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/review-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/review.jpg" alt="The review for moving the linear server into the gateway: Claude Code and Codex will both reach it through the gateway, and what to restart" width="860">
  </picture>
</p>

### Let your agents ask

**Agents** adds a read-only MCP server to Claude Code, Codex or Cursor, so you can ask your agent
"show my setup". It cannot change anything.

## Install

macOS. With [uv](https://docs.astral.sh/uv/):

```bash
uvx kitden
```

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

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/how-it-works-dark.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/how-it-works.svg" alt="Kitden reads the settings of Claude Code, Codex and Cursor, shows them on one local page, and writes a change back with a backup you can undo" width="860">
  </picture>
</p>

1. Kitden reads your agents' settings files.
2. It shows them on one page in your browser, at `127.0.0.1` only.
3. You press Apply. Kitden backs the file up, writes the change and checks it. Undo brings the old
   file back. Backups stay for 30 days, and the newest 100 changes always keep theirs.

Secrets are never shown or logged. Kitden goes online only to reach the gateways you add, and to
read one marketplace file from `raw.githubusercontent.com` when you add a marketplace from a
GitHub link.

## Roadmap

What is done and what comes next: [ROADMAP.md](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md).
Ideas and bugs: [open an issue](https://github.com/KonstantinStarovoytov/kitden/issues).

## More

- [Release notes](https://github.com/KonstantinStarovoytov/kitden/releases)
- [Develop and release](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/development.md)
- [Visual and motion rules](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/design.md)
- License: [Apache-2.0](https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE)
