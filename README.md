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
plugins and skills, choose Installed, New (not on this computer yet) or All, and filter by
category. Pick a project at the top to see what loads in that folder.

The action sits in the client's cell. "+ Add" adds a plugin or skill to that client. "+ Add
skills" copies the skills of a plugin that work on their own into a client that cannot install the
plugin itself. "+ Add the plugin" is for a skill that needs its plugin. On plugins and skills, a
cell with nothing to do says why. You can also add a marketplace from a folder or a GitHub link.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library.jpg" alt="Library: plugins in rows, a column for each client, and a + Add button in the cells where a client can take one" width="860">
  </picture>
</p>

### Use one gateway for every client

**Gateway** shows the gateways your clients use. The Kitden gateway comes first: it runs on your
Mac, with no deploy and no account. [Obot](https://obot.ai) (with OAuth sign-in) and MetaMCP stay
for teams that want a shared service. Connect your clients, see what a gateway holds and which
servers go around it, and move direct servers into it one at a time or all at once. Switch every
client to another Obot or MetaMCP gateway in one review. Click a client in the diagram to open its
app.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway.jpg" alt="Gateway: the Kitden gateway first, with Claude Code and Cursor linked to it and one server it holds, then an Obot gateway below" width="860">
  </picture>
</p>

### The Kitden gateway: tools per project

The Kitden gateway is the `kitden` entry that already lets agents read your setup; the page adds
it to a client that lacks it. Move a server into it and every client that uses the Kitden gateway
reaches it. Pick a project at the top, open a server in the gateway, and turn the whole server or
one tool on or off for that project, or for all projects. A project's switches also apply in its
folders and git worktrees, unless they have their own. Claude Code and Codex can turn a tool
off in one project, Cursor cannot (checked 2026-10-21); the gateway gives the same control in all
three.

It holds local servers (a command) and remote ones (an address). Each switch is a review with a
backup and Undo. Moving a server in for the first time keeps the tools Claude Code and Codex had
turned off; Cursor's own tool switches do not carry over. Moving a server the gateway holds again
updates it, for example with a new token, and keeps the gateway's switches for it; the clients'
own switches do not carry over then. A change applies to new sessions, so start a new one in your
client. A moved server's env values and headers are kept in the gateway's settings file, which only
you can read and which stays on this Mac.

A few servers stay direct for now, and the page says why:

- servers that need an OAuth sign-in (one place for logins comes later);
- entries in a project's own files, such as `.mcp.json`: they are already per project;
- entries that read a value from your shell, such as `${TOKEN}`: a client such as Codex starts the
  gateway with almost no environment, and copying the value would make a new copy of a secret;
- entries that start in their own folder: the gateway starts every local server in the folder
  the session works in, such as the project or its worktree;
- SSE and WebSocket connections: the gateway does not support them yet.

### Check every change before it is written

Every change opens a review first: the clients it reaches (Cursor too, when an added
plugin or skill reaches it) and the exact file change, with secrets hidden. Apply keeps a backup,
writes the change and checks it. **Changes** keeps the history, with Undo and what to restart for
a change to take effect.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/review-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/review.jpg" alt="The review for moving the github server into the gateway: Claude Code will reach it through the gateway, and what to restart" width="860">
  </picture>
</p>

### Let your agents ask

**Agents** adds the Kitden MCP server to Claude Code, Codex or Cursor, so you can ask your agent
"show my setup". Kitden's own tools only read.

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

Secrets are never shown or logged. Kitden goes online only to reach the gateways and remote
servers you add, and to read one marketplace file from `raw.githubusercontent.com` when you add a
marketplace from a GitHub link.

## Roadmap

What is done and what comes next: [ROADMAP.md](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md).
Ideas and bugs: [open an issue](https://github.com/KonstantinStarovoytov/kitden/issues).

## More

- [Release notes](https://github.com/KonstantinStarovoytov/kitden/releases)
- [Develop and release](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/development.md)
- [Visual and motion rules](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/design.md)
- License: [Apache-2.0](https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE)
