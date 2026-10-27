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

## Why you want it

You use two or three AI coding tools. A few weeks in:

- a plugin loads twice, because Cursor quietly reads Claude Code's plugins;
- an MCP server you removed from one tool still runs in another;
- an agent edited its own settings, and you are not sure what changed.

The answers are spread over many JSON and TOML files. Kitden reads them all, shows them on one
page, and changes a file only after you have seen the exact edit.

Kitden is for one developer or a small team. It runs on your Mac at `127.0.0.1`, with no account
and no telemetry. Secrets stay on this Mac. They go only to the server they belong to, or to a gateway you move
that server into.

## What you can do

### See what needs you

**Overview** lists what needs your attention, such as an item that loads twice or a file Kitden
could not read, and what can improve, such as servers that skip your gateway. Most cards have
one button. Beside the cards a small map shows your clients, the Kitden gateway and the Library;
point at a card to see what it is about.

### Use one gateway for every client

**Gateway** is a map read from left to right: your clients, the Kitden gateway, the servers it
holds and their tools. A link means on; no link means off.

- Drag a server from "Outside the gateway" onto the gateway to move it in; "Drop to add" shows
  where it lands. Without a mouse, use "Move in…" in the List.
- Point at a link and press × to take it away: disconnect a client, take a server out, or turn a
  tool off.
- Connect a client with its "Connect…" card on Overview, by dragging it onto the gateway, or with
  "Connect to the gateway…" in its Details. Drag a server onto a client to move it out of the
  gateway, or use "Put back in Codex…".
- Pick a project at the top to turn a tool on or off there only. "Turn off in some projects…"
  ticks several at once, and "Use the shared rule…" drops a project's own rule.
- "+ Add" lists the MCP servers your marketplaces offer.
- Map | List switches to a list; past 15 servers the page opens as the List.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway.jpg" alt="The Gateway map: Claude Code and Codex linked to the Kitden gateway and its two servers; below, the servers outside the gateway, each joined to its client by a dotted line" width="860">
  </picture>
</p>

The Kitden gateway runs on your Mac, with no deploy and no account. It is the `kitden` entry that
already lets agents read your setup. Kitden also works with an [Obot](https://obot.ai) or MetaMCP
gateway, for teams that want a shared service: "Add another gateway…" adds one, servers move into
it, and "Use this gateway…" switches every client to it.

- A tool you turn off is refused at once, even in a session that is already open; other changes
  apply to new sessions, and a call already running is not stopped.
- A project's rules also apply in its folders and git worktrees. In a folder Kitden does not know
  as a project, the All projects switches apply. Cursor cannot turn a tool off in one project
  (checked 2026-10-21); through the gateway, all three clients can.
- "Turn strict mode on…" makes a server offer only the tools that are on; a tool it adds later
  waits until you decide. Each tool says whether it reads or may write, and how often it was
  called.
- A moved server's secrets go to your macOS Keychain, not the gateway's settings file.
- The gateway controls only the servers in it. Direct entries and terminal tools stay outside.

A few servers stay direct for now, and the page says why: servers that need an OAuth sign-in,
entries in a project's own files such as `.mcp.json`, entries that read a value from your shell
such as `${TOKEN}`, entries that start in their own folder, and SSE or WebSocket connections.

### See and add plugins, skills and instructions

**Library** has two tabs, "Plugins and skills" and "Instructions", each as a map or a List.

- The map shows your clients, then the plugins and skills they load under where they come from.
  Click a plugin to see what it holds.
- Drag a plugin or a skill onto a client to add it there. A link's × removes a plugin from a
  client or turns a skill off.
- "+ Add" lists the plugins and skills your marketplaces offer.
- The List has a row per item and a column per client. A cell says "On" when the client has the
  item and "Off" when it has it turned off. "Unknown" means Kitden could not read it, so it may or
  may not be available; it never means missing. Either a file could not be read, or the client
  keeps the on/off state where Kitden cannot see it, such as your Claude account. "Needs review"
  means another client has an item with the same name from another source.
- Differences shows only what differs between your clients, and "Add missing plugins and skills…"
  adds what one client has and another lacks.
- Pick a project at the top to see what loads in that folder. "This project" marks a cell the
  project's own settings decide, and "Only this project" an item only that project has. There a
  cell's "+ Add" asks "Add to this project…" or "Add for all projects…".
- Instructions shows CLAUDE.md, AGENTS.md, Cursor rules, Claude Code's commands and agents, and
  the files CLAUDE.md pulls in. Kitden only reads them.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library.jpg" alt="The Library map: Claude Code, Codex and Cursor linked to the plugins and skills they load, grouped by where they come from" width="860">
  </picture>
</p>

Click anything for its **Details**. They say in words where each client loads an item, for
example "Claude Code loads it in every project. Cursor gets it through Claude Code.", and hold
every action. A Remove names every client it reaches, such as "Remove from Codex and Cursor…". A
server in the gateway offers "Remove from the Kitden gateway…" and "Put back in Codex…".
"Commands…" shows the commands you run yourself, each with Copy. Paths, commands and an
instruction file's first lines wait under Technical details.

### Check every change before it is written

A button, a switch, a × or a drag never writes a file. It adds a row to the preview tray at the
bottom left, and the map shows it as a dashed preview. Click a preview, or its ×, to take it out.

- "Show changes" opens a row's exact file change, with secrets hidden. It says "Other projects are
  unchanged." only when that is sure, and names what Undo cannot bring back.
- Apply all writes every row as one change, all or nothing. It keeps one backup and checks the
  result. Undo all takes it all back.
- If the files change while a row waits, the tray says "Settings changed since this preview." and
  offers "Preview again".

Kitden writes only in your home folder and your known projects.

### Look back and undo

**Changes** lists every change by day. Its Details say the project, the backup and what to
restart for the change to take effect. Undo puts the old files back, "Redo…" previews an undone
change again, and "See it on the map" opens the item it changed.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/changes-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/changes.jpg" alt="The Changes page: three changes today, one of them undone; the Details of the newest show the project, the backup, what to restart and the history" width="860">
  </picture>
</p>

### Let your agents ask

**Agents** adds the Kitden MCP server to Claude Code, Codex or Cursor, so you can ask your agent
"show my setup" or "which instruction files does this project have". Kitden's own tools only read.
Servers moved into the gateway add their tools, which do what those servers do.

## Install

macOS. With [uv](https://docs.astral.sh/uv/):

```bash
uvx kitden
```

To try it first on a sample setup, with nothing on your computer read or changed: `uvx kitden demo`.

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

1. Kitden reads your agents' settings files. For a project in a subfolder of a git repository it
   also reads the repository root's `.claude/settings.local.json`, the same file Claude Code reads
   there.
2. It shows them on one page in your browser, at `127.0.0.1` only. With a large setup (about 500
   items, like the sample `kitden demo --size large` opens) the page has its data in under a
   second; a slow answer comes after.
3. You press Apply all. Kitden backs the files up, writes the change and checks it. Undo brings
   the old files back. Backups stay for 30 days, and the newest 100 changes always keep theirs.

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
