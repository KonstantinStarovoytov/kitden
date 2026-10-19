<img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/logo.svg" width="100%" alt="Kitden">

<h1 align="center">Kitden</h1>

<p align="center"><b>One calm page for everything your AI coding agents load.</b><br>
Claude Code, Codex and Cursor — every MCP server, plugin, skill and hook, in one place.<br>
See what loads twice. Fix it in one click. Undo anytime.</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/overview-dark.jpg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/overview.jpg" alt="The Kitden page: three things need attention, each with one button to fix it" width="800">
  </picture>
</p>

<p align="center">

```bash
uvx kitden
```

</p>

## Why you want it

You use two or three AI coding tools. A few weeks in:

- a plugin loads twice, because Cursor quietly reads Claude Code's plugins;
- an MCP server you removed from one tool still runs in another;
- an agent edited its own settings, and you are not sure what changed.

The answers are spread over six JSON and TOML files. Kitden reads them all and shows **one page**.

## What you get

| | |
| --- | --- |
| **See everything** | Every MCP server, plugin, skill, hook and marketplace, for every client, side by side. Nothing to configure. |
| **Know what needs attention** | Things that load twice, servers that skip your gateway, files that could not be read. Each with one button to fix it. |
| **Change without fear** | Turn a plugin off, remove an old entry, move servers into your gateway. You see the exact change first; Apply keeps a backup; Undo puts it back. |
| **One gateway for all clients** | Connect [Obot](https://obot.ai) or MetaMCP to every client at once, switch all of them to another gateway in one review, see what each holds and which servers go around it. |
| **Jump straight in** | Click a client on the gateway map to open Claude, ChatGPT (Codex) or Cursor; click the gateway to open it. |
| **Agents can ask too** | A read-only "show my setup" server lets Claude Code, Codex or Cursor answer "what do you load here?". |
| **Private by design** | Runs on your Mac only (`127.0.0.1`). No account, no telemetry, secrets never shown or logged. |

## Install

macOS. With [uv](https://docs.astral.sh/uv/):

```bash
uvx kitden
```

Without uv — one line installs uv and Kitden, then opens the page:

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

## How it works

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/how-it-works-dark.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/how-it-works.svg" alt="Kitden reads the settings of Claude Code, Codex and Cursor, shows them on one local page, and writes a change back with a backup you can undo" width="860">
  </picture>
</p>

1. Kitden reads your agents' settings files. Nothing leaves your Mac.
2. It shows them on one page in your browser.
3. You press Apply. Kitden backs the file up, writes the change and checks it. Undo brings the old
   file back.

## Roadmap

| Status | What |
| --- | --- |
| ✅ Done | One page for Claude Code (with the Desktop Code tab), Codex and Cursor; duplicates; safe on/off with Undo |
| ✅ Done | Obot as your gateway: OAuth sign-in, see what it holds, connect or switch every client in one review |
| ✅ Done | MetaMCP: the same, plus moving direct servers into it with one Apply and one Undo |
| 🔨 Now | Move servers into Obot from Kitden |
| ⏭ Next | Copy any command with one click |
| ⏭ Next | Linux and Windows |
| 💭 Later | A living map: clients → config files → servers, plugins, skills → gateways |
| 💭 Later | A shared setup for a small team |

Ideas and bugs: [open an issue](https://github.com/KonstantinStarovoytov/kitden/issues).

## More

- [Develop and release](docs/development.md)
- [Visual and motion rules](docs/design.md)
- License: [Apache-2.0](LICENSE)
