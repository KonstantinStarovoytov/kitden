<h1 align="center">
  <img src="docs/images/hero.svg#gh-light-mode-only" width="640" alt="Kitden: Your AI coding tools, under one roof.">
  <img src="docs/images/hero-dark.svg#gh-dark-mode-only" width="640" alt="Kitden: Your AI coding tools, under one roof.">
</h1>

<p align="center"><strong>See what Claude Code, Codex and Cursor actually load, and which skills got cut.</strong></p>

```bash
uvx --python 3.13 kitden scan
```

Needs [uv](https://docs.astral.sh/uv/getting-started/installation/). Or with Homebrew:
`brew install konstantinstarovoytov/tap/kitden`, then `kitden scan`. The scan reads your
agents' settings and changes none of them.

It prints what each agent loads, for example:

```text
Claude Code 2.1.311
  In your last chat on Oct 1, 3 of 19 skills showed only a name. The agent may
  not have used them.
    brandkit, release-notes, superpowers:planning
    That chat was in ~/work/atlas.
  On this computer: 2 plugins, 4 skills, 2 MCP servers, 2 instruction files,
  1 marketplace
  A chat lists only one project's skills, and Claude Code's own too.

Codex 0.171.0
  On this computer: nothing yet
…

6 notes (nothing to fix): kitden show findings
Your agents' settings were not changed: scan only reads them.
To make the skills fit, turn off the ones you do not use: kitden open
```

<p align="center">One local page for their MCP servers, plugins, skills and instruction files.<br>
It changes nothing until you press Apply, and every change can be undone.</p>

<p align="center">
  <a href="https://github.com/KonstantinStarovoytov/kitden/actions/workflows/release.yml"><img src="https://github.com/KonstantinStarovoytov/kitden/actions/workflows/release.yml/badge.svg?branch=main" alt="Checks on main"></a>
  <a href="https://github.com/KonstantinStarovoytov/kitden/releases/latest"><img src="https://img.shields.io/github/v/release/KonstantinStarovoytov/kitden?label=latest%20release" alt="Latest release"></a>
  <a href="https://pypi.org/project/kitden/"><img src="https://img.shields.io/pypi/v/kitden?label=PyPI" alt="Kitden on PyPI"></a>
  <a href="https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0"></a>
</p>

### See whether your skills fit

Every chat starts with the list of your skills, and that list has a small budget: 1% of the context window in Claude Code (or the share you set in its settings), 2% in Codex. Past it, Claude Code sends some skills by name
only and Codex shortens or drops them, so the agent may never reach for them. Kitden reads the
last chat's log and shows which skills went in whole, and says how the list stands now if you added or turned off skills since. Turn off the ones you do not use, or drag the limit line to give the list more room. A skill's Details shows its description, with the part the agent did not get in grey. A
guess for another window is marked Estimate. Cursor gets no verdict: Kitden cannot see what it
sends.

<img src="docs/images/readme/context-light.png#gh-light-mode-only" width="860" alt="Context for Claude Code on the sample. In the last chat, in a 200K window, 4 of 20 skills showed only a name; in a 1M window all 20 would fit. A bar shows the skill list against its limit of 8,000 characters. Under it the skills stand in groups by source: Built into Claude Code, 15 skills, 7,604 characters; the plugin superpowers, 2 skills, 1 showed only a name, with its Turn off switch; Your skills, 3 skills, all 3 showed only a name.">
<img src="docs/images/readme/context-dark.png#gh-dark-mode-only" width="860" alt="Context for Claude Code on the sample. In the last chat, in a 200K window, 4 of 20 skills showed only a name; in a 1M window all 20 would fit. A bar shows the skill list against its limit of 8,000 characters. Under it the skills stand in groups by source: Built into Claude Code, 15 skills, 7,604 characters; the plugin superpowers, 2 skills, 1 showed only a name, with its Turn off switch; Your skills, 3 skills, all 3 showed only a name.">

### Everything your agents load, on one map

Claude Code, Codex and Cursor each keep their own settings. Kitden puts their plugins, skills,
MCP servers and instruction files on one map, so what one agent has and another lacks shows
at a glance. Pick an agent to see just what it loads. Add what an agent is missing, turn an item off or remove it, on the same page.

<img src="docs/images/readme/library-light.png#gh-light-mode-only" width="470" alt="The Library map: Claude Code and Cursor load the superpowers plugin. Codex and Cursor load four skills, folded as a stack: frontend-design, pdf, skill-creator and one more.">
<img src="docs/images/readme/library-dark.png#gh-dark-mode-only" width="470" alt="The Library map: Claude Code and Cursor load the superpowers plugin. Codex and Cursor load four skills, folded as a stack: frontend-design, pdf, skill-creator and one more.">

### Add what is missing

Search the official MCP Registry, skills.sh, the Claude plugins marketplace and any public
GitHub repository without leaving the page. Tick the agents a plugin or skill goes to. An MCP
server goes to the gateway, and says first whether it needs a sign-in or a token.

<img src="docs/images/readme/find-light.png#gh-light-mode-only" width="860" alt="Two add panels side by side. A search for mcp in skills.sh lists six skills with their installs; mcp-builder is open, with Claude Code and Codex ticked under Add to. A search for linear in the MCP Registry lists six servers; Linear's own is open with a Sign in button, and others say Needs token or Unavailable.">
<img src="docs/images/readme/find-dark.png#gh-dark-mode-only" width="860" alt="Two add panels side by side. A search for mcp in skills.sh lists six skills with their installs; mcp-builder is open, with Claude Code and Codex ticked under Add to. A search for linear in the MCP Registry lists six servers; Linear's own is open with a Sign in button, and others say Needs token or Unavailable.">

### One gateway for your MCP servers

Move a server into the Kitden gateway and every agent you use gets it: set it up once, not
once per agent. Every tool has a switch, for all projects or one, and a tool that is off is
refused, not just hidden. A token or sign-in is given once and checked before Apply.

<img src="docs/images/readme/tools-light.webp#gh-light-mode-only" width="860" alt="memory in the Kitden gateway shows its nine tools; its three delete tools are turned off on the map and applied for every agent.">
<img src="docs/images/readme/tools-dark.webp#gh-dark-mode-only" width="860" alt="memory in the Kitden gateway shows its nine tools; its three delete tools are turned off on the map and applied for every agent.">

### Every change can be undone

- **Nothing is written until you press Apply.** Every change shows a preview first, with
  the exact edit under Show changes.
- **Apply keeps a backup, and Undo puts it back.** Changes keeps the history of what you
  did. If a file changed since, Kitden stops instead of overwriting it.
- **Everything stays on your computer.** The page runs at 127.0.0.1 behind a private link. No
  account, no telemetry. Kitden goes online only for the catalogs you open (also on
  **Rescan**), the remote servers you add, and a check for a newer Kitden, at most once a day.
- **Secrets live in the macOS Keychain or your Linux keyring only.** The page shows no more
  than their first and last characters.
- **Kitden's agent tools only read.** Asking an agent to show your setup changes none of your settings.
- **Leaving is easy.** Plugins and skills you add live in each agent's own settings, and a server
  in the gateway moves back out. [How to stop using Kitden](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/guide.md#stop-using-kitden).

Add only servers and plugins you trust: they run with your permissions.

## And more

| Feature | What it does |
| --- | --- |
| **Per project** | Turn a server or a tool on or off for one project only. |
| **See what runs** | How often each tool is called, and which tools only read. |
| **Instructions in view** | Which CLAUDE.md, AGENTS.md, rules, hooks, commands and agents each client loads, and where they come from. |
| **MCP server** | `kitden mcp` lets any agent read your setup, so "show my setup" or "why does this load twice" gets a true answer. Its own tools only read. |
| **Plugin** | For Claude Code and Codex. `/plugin install kitden --marketplace KonstantinStarovoytov/kitden` adds six skills and no server. `/kitden:audit` lists what to turn off in the project you are in, and `/kitden:context` says whether your skills fit. The skills only read, and offer to install Kitden when it is missing; you change things on the page. [More](https://github.com/KonstantinStarovoytov/kitden/blob/main/plugins/kitden/README.md). <!-- Checked 2026-11-05: https://code.claude.com/docs/en/discover-plugins --> |

## Get started

Needs **macOS or Linux**, [uv](https://docs.astral.sh/uv/getting-started/installation/) and at
least one of **Claude Code, Codex or Cursor**. On Linux, install `libsecret-tools` (Debian,
Ubuntu) or `libsecret` (Fedora, Arch) so Kitden can keep server secrets in your keyring.

The scan at the top of this page needs no install. To try the page on a sample instead, with
your own settings not read or changed:

<!-- Release checklist: docs/readme-media.md -->
```bash
uvx --python 3.13 kitden demo
```

Install it and open it for your own setup:

```bash
uv tool install --python 3.13 kitden && kitden
```

Or with Homebrew: `brew install konstantinstarovoytov/tap/kitden`, then `kitden`.
Update later from the page, or with `uv tool upgrade kitden` or `brew upgrade kitden`.

## Help build Kitden

<p align="center">
  <a href="https://konstantinstarovoytov.github.io/kitden-sdlc/desk/"><img src="https://img.shields.io/badge/Open_the_desk-C85835?style=for-the-badge" alt="Open the desk"></a>
</p>

<p align="center">Reviews, tests and releases for Kitden run from
<a href="https://github.com/KonstantinStarovoytov/kitden-sdlc">kitden-sdlc</a>.</p>

Want to help? [Pick a good first issue](https://github.com/KonstantinStarovoytov/kitden/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22).

[Guide](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/guide.md) ·
[Roadmap](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md) ·
[Releases](https://github.com/KonstantinStarovoytov/kitden/releases) ·
[Issues](https://github.com/KonstantinStarovoytov/kitden/issues) ·
[Contributing](https://github.com/KonstantinStarovoytov/kitden/blob/main/CONTRIBUTING.md) ·
[Apache-2.0](https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE)

<p align="center"><sub>Listed on</sub><br><a href="https://glama.ai/mcp/servers/KonstantinStarovoytov/kitden"><img src="https://glama.ai/mcp/servers/KonstantinStarovoytov/kitden/badges/score.svg" alt="Kitden on Glama"></a> <a href="https://mcprush.com/to/kitden-mcp?ref=badge"><img src="https://mcprush.com/badge/kitden-mcp/score.svg" alt="Kitden MCP on mcprush"></a> <a href="https://m8ven.ai/mcp/konstantinstarovoytov-kitden-14dddz?s=readme"><img src="https://m8ven.ai/badge/mcp/konstantinstarovoytov-kitden-14dddz" alt="M8ven Score"></a></p>

<!-- mcp-name: io.github.KonstantinStarovoytov/kitden -->
