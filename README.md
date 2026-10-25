<img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/logo.svg" width="100%" alt="Kitden">

<h1 align="center">Kitden</h1>

<p align="center"><b>See and safely change what your AI coding agents load.</b><br>
Claude Code, Codex and Cursor: every MCP server, skill, plugin, hook and marketplace on one local page.<br>
Look at each change first. Apply keeps a backup for Undo.</p>

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
and no telemetry. Secrets stay on this Mac. They go only to the server they belong to, or to a gateway you move
that server into.

## What you can do

### See what needs attention

**Overview** lists what needs attention, such as an item that loads twice, and what can improve,
such as servers that could move into your gateway. Each one has a button that opens its fix.
Notes, which need no fix, are grouped by item, with the clients each is about.
The clients Kitden found sit on the right, and a card says whether the Kitden gateway is set up.

### See what each client has, and add what it lacks

**Library** is one page for what each client loads and what you can add to it. Each row is an
item and each column is a client on this computer; the "−" on a column head hides that client,
and "Show" brings it back. Tabs split MCP servers, plugins, skills, hooks, marketplaces and
instructions (CLAUDE.md, AGENTS.md, rules, commands and agents; Details shows the first lines,
common secret shapes hidden). On plugins and skills, choose Installed, New (not on this computer
yet) or All, and filter by category. Pick a project at the top to see what loads in that folder.
All projects shows what every project shares. In a project, a cell carries "This project" when the
project's own settings decide it, and "Only this project" for an item only that project has; the
other cells follow what every project shares and carry nothing. How a client gets it,
such as "through Claude Code's folder", is in the cell's hover text. The address keeps the
project and the item you opened, so a link or Back returns to it.

A cell says "On" when the client has the item and "Off" when it has it turned off.
"Unknown" means Kitden could not read it, so it may or may not be available; it never means
missing. Either a file could not be read, or the client keeps the on/off state where Kitden
cannot see it, such as your Claude account. "Needs review" means another client has an item with
the same name from another source. That row offers no "+ Add", because an add would copy only one
side.

A row opens its **Details**. They say why each client loads the item, for example "One folder,
read by Codex and Cursor.", and which clients and projects its main action changes, before you
press it. Paths, commands and an instruction file's first lines wait under Technical details.
"Compare across clients" opens the same item in the Library, and "Manage tools" opens a server of
the Kitden gateway on the Gateway page.

The action sits in the client's cell. Where Kitden can add an item to that client, the cell says
"+ Add". "+ Add skills" copies the skills of a plugin that work on their own into a client that
cannot install the plugin itself. "+ Add the plugin" is for a skill that needs its plugin. On
plugins and skills, a cell with nothing to do says why. You can also add a marketplace from a
folder or a GitHub link.

Details of a plugin or a skill offer a Remove, with Undo. It names every client it reaches:
"Remove from Codex and Cursor…" for a skill in a folder both read. Undo installs a plugin again,
but not its saved options. "+ Add" on an MCP server copies its entry to another client; a
`${VAR}` reference stays a reference where that client can read one, and the review says when a
secret gets a second copy. With a project picked, "+ Add" on a skill or a Claude Code plugin asks
"Add to this project…" or "Add for all projects…"; a skill only this project has adds into this
project. "Add missing…" lists what one client loads in the project and another lacks, as one
review with checkboxes; an item with the same name from another source is listed as not the same
and left alone.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/library.jpg" alt="Library: plugins in rows, a column for each client, and a + Add button in the cells where a client can take one" width="860">
  </picture>
</p>

### Use one gateway for every client

**Gateway** is a tree, read from left to right: your clients, the Kitden gateway, the servers it
holds, and their tools. A link drawn means "on"; no link means "off". Click a server to see its
tools, and a tool to light its path from each client. A Map | List switch sits beside the title;
the page opens as a List past 15 servers, and the address keeps your choice. Details sit beside
the page (a drawer in a narrow window) and hold every action. A client's Details set up the
gateway in it and can open its app.

The Kitden gateway comes first: it runs on your Mac, with no deploy and no account.
[Obot](https://obot.ai) (with OAuth sign-in) and MetaMCP stay for teams that want a shared
service. Connect your clients, see what a gateway holds, and move servers into it one at a time
or all at once. Switch every client to another Obot or MetaMCP gateway in one review.

A server a client sets up on its own sits under "Outside the gateway · calls skip Kitden's
rules", joined to its client by a grey dotted line that turns amber under the pointer. Amber
here marks a call that skips the rules, not a fault. Drag one onto the servers ("Drop to add"
shows where it lands) and the Move preview appears on the map, with a bar to Apply, Cancel or
"Show changes", which opens the full review in Details. Without a mouse, use "Move in…" in the
List. Nothing changes until Apply, and a call already running is not stopped. A gateway controls
only the servers in it; direct entries and terminal tools stay outside it.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/gateway.jpg" alt="The Gateway map: Claude Code and Codex linked to the Kitden gateway and its two servers, with the servers outside the gateway below, each joined to its client by an amber line" width="860">
  </picture>
</p>

### The Kitden gateway: tools per project

The Kitden gateway is the `kitden` entry that already lets agents read your setup; the page adds
it to a client that lacks it. Move a server into it and every client that uses the Kitden gateway
reaches it. Pick a project at the top (the menu has a find box and counts each project's own
rules), open a server or a tool, and use its Details: "Turn off for all projects…" or "Turn off
in one project…", and the same to turn it on. "Use the shared rule…" drops a project's own rule.
A project's switches also apply in its folders and git worktrees, unless they have their own.
In a folder Kitden does not know as a project, the All projects switches apply. Claude Code and
Codex can turn a tool off in one project, Cursor cannot (checked 2026-10-21); the gateway gives
the same control in all three. A server in the gateway shows how many tools it has, once Kitden
has asked it. A held server's Details offer "Remove from the Kitden gateway…", which takes its
switches too and makes open sessions refuse its tools at once, and "Put back in <client>…",
which writes its entry into that client again.

It holds local servers (a command) and remote ones (an address). Each switch is a review with a
backup and Undo. Moving a server in for the first time keeps the tools Claude Code and Codex had
turned off; Cursor's own tool switches do not carry over. Moving a server the gateway holds again
updates it, for example with a new token, and keeps the gateway's switches for it; the clients'
own switches do not carry over then. A tool you turn off is refused at once, even in a session
that is already open; other changes apply to new sessions, so start a new one in your client.
A moved server's env values and headers that would be hidden go to your macOS Keychain, not
the gateway's settings file, which keeps only a reference. The review says so, and warns if an
item is already there and will be replaced. Undo removes only the items the move created. If a
server is removed from the gateway, its secrets stay in your Keychain under `kitden`.

For a server you do not trust with new tools, use "Turn strict mode on…" in its Details. It
applies to all projects: the server offers only the tools that are on, and a tool it adds later
waits as "New · waits" until you decide. Each tool says what it is reported to do, from the
server's own hint or a guess from the tool's name. "Turn off every writing tool…" turns them off
in one review. A tool's Details say how often it was called and when last ("12 calls · last today
14:02"); only the count and the time are kept, never what was sent. The words are a guess, so
check the list; for a real guarantee, give the server a token that can only read.

A few servers stay direct for now, and the page says why:

- servers that need an OAuth sign-in (one place for logins comes later);
- entries in a project's own files, such as `.mcp.json`: they are already per project;
- entries that read a value from your shell, such as `${TOKEN}`: a client such as Codex starts the
  gateway with almost no environment, and copying the value would make a new copy of a secret;
- entries that start in their own folder: the gateway starts every local server in the folder
  the session works in, such as the project or its worktree;
- SSE and WebSocket connections: the gateway does not support them yet.

### Check every change before it is written

Every change opens a review first. It starts with what will happen, where, and in which clients
(Cursor too, when an added plugin or skill reaches it), then shows the exact file change, with
secrets hidden. It says "Other projects are unchanged." only when that is sure, and it names
what Undo cannot bring back, such as a plugin's saved options. Apply keeps a backup, writes the
change and checks it. If the settings change while the review is open, it says "Settings changed
since this preview." and offers Preview again. Cancel goes back to the Details it came from.
Kitden writes only in your home folder and your known projects. **Changes** keeps the history,
with Undo and what to restart for a change to take effect.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/review-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/review.jpg" alt="The review for moving the github server into the gateway: Claude Code will reach it through the gateway, and what to restart" width="860">
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

1. Kitden reads your agents' settings files.
2. It shows them on one page in your browser, at `127.0.0.1` only. With a large setup (about 500
   items, like the sample `kitden demo --size large` opens) the page has its data in under a
   second; a slow answer comes after.
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
