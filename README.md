<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/hero-dark.svg">
    <source srcset="docs/images/hero.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/hero.svg" width="640" alt="Kitden: Your AI coding tools, under one roof.">
  </picture>
</h1>

<p align="center"><strong>Your AI coding tools, under one roof.</strong></p>

<p align="center">See and change what <b>Claude Code, Codex and Cursor</b> load.<br>
MCP servers, plugins and skills, with preview and Undo.</p>

<p align="center">
  <a href="https://github.com/KonstantinStarovoytov/kitden/actions/workflows/release.yml"><img src="https://github.com/KonstantinStarovoytov/kitden/actions/workflows/release.yml/badge.svg?branch=main" alt="Checks on main"></a>
  <a href="https://github.com/KonstantinStarovoytov/kitden/releases/latest"><img src="https://img.shields.io/github/v/release/KonstantinStarovoytov/kitden?label=latest%20release" alt="Latest release"></a>
  <a href="https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0"></a>
</p>

<p align="center">
  <a href="https://github.com/KonstantinStarovoytov/kitden#try-safely-on-a-sample">Try the sample</a> ·
  <a href="https://github.com/KonstantinStarovoytov/kitden#install-for-your-own-setup">Install</a> ·
  <a href="https://github.com/KonstantinStarovoytov/kitden#contributing">Contribute</a>
</p>

## See what each agent loads

Compare plugins and skills across Claude Code, Codex and Cursor. Add what is missing,
choose what a project loads, and trace each item to its source.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/compare-dark.svg">
  <source srcset="docs/images/compare.svg">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/compare.svg" width="880" alt="Add Superpowers to Codex: drag the plugin onto Codex, review the preview, then Apply. The map shows its new connection.">
</picture>

Open **Library** and choose **All projects** or one project. **List → Differences** shows
what differs between clients. Click an item for its **Details**.

| What | How to manage it |
| --- | --- |
| **Plugins and skills** | Use **+ Add**, or drag an item onto another client. Turn it on or off, choose its scope, or remove a copy in **Details**, where the client supports it. **Add missing plugins and skills…** fills gaps across clients. |
| **Marketplaces** | Browse their plugins and skills. **+ Add → Add a marketplace…** adds a GitHub source. **Details → More → Commands…** has update and remove commands to copy. |
| **Hooks and instruction files** | See which client loads them and where they come from. **Library → Instructions** shows files and imports, plus commands and agents. Kitden only reads these; edit them in your editor. |

The preview names the clients and projects affected. Adds on the map go to all projects;
the List offers a project scope where supported. Start a new client session to load a change.

## Share a server between your agents

Open **Gateway** to share MCP servers and turn individual tools on or off for each project.
Its rules cover the servers you move into it. You can use Library on its own.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/walkthrough-dark.svg">
    <source srcset="docs/images/walkthrough.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/walkthrough.svg" width="880" alt="Share Context7: move it from Claude Code into Kitden, review the change, then Apply. Its two tools are available through the gateway.">
  </picture>
</p>

## Review a change. Apply it. Undo it.

Look at each change first. Apply keeps a backup for Undo. **Show changes** shows the exact
edit; Apply writes it and checks the result. Open **Changes → Undo** to restore it.
If Undo would overwrite newer edits, Kitden stops.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/undo-dark.svg">
  <source srcset="docs/images/undo.svg">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/undo.svg" width="880" alt="The same change before and after Undo: first Applied with an Undo button, then crossed out and marked Undone.">
</picture>

Kitden can change your client settings. Only add plugins and MCP servers you trust:
they can run code with your permissions. Undo does not reverse actions a tool already ran.

## Try safely on a sample

Explore the full page on temporary sample files. **Your settings and secrets are not read
or changed**, even when you press Apply. The demo starts no real clients or MCP servers.

Requires **macOS** and **[uv](https://docs.astral.sh/uv/)**. uv gets Python 3.13 if needed.
The first run downloads Kitden; the demo itself stays offline.

<!-- Release checklist: docs/readme-media.md -->
```bash
uvx --python 3.13 kitden demo
```

Kitden opens in your browser. If it does not, open the link printed in Terminal.

1. In **Library → List**, find **superpowers** and press **+ Add** under **Codex**.
2. Review and **Apply**. Codex now has a copy in the sample setup.
3. Open **Changes → Undo** to remove that copy again.

Press **Ctrl+C** in Terminal to stop and delete the sample.

<details>
<summary>Install uv</summary>

Use uv's official installer, then open a new Terminal window:

<!-- Checked 2026-10-28: https://docs.astral.sh/uv/getting-started/installation/ -->
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

</details>

## Install for your own setup

Requires **macOS**, **[uv](https://docs.astral.sh/uv/)** and at least one of **Claude Code,
Codex or Cursor**. Run once to install:

```bash
uv tool install --python 3.13 kitden
```

Then open Kitden whenever you need it:

```bash
kitden
```

Your setup opens in the browser. Changes to client settings wait for Apply.
If the command is not found, run `uv tool update-shell` and open a new Terminal window.

<details>
<summary>Privacy and backup limits</summary>

- The page runs locally at `127.0.0.1`, with a private access link. No account or telemetry.
- Credentials go to the server they belong to, or to a gateway you move that server into. Kitden masks secret fields and known token formats in its page and logs. It goes online to reach remote servers and read GitHub marketplaces you add.
- Backups stay for 30 days, and the newest 100 changes always keep theirs. Changes also offers **Redo…** and **See it on the map**.
- Undo of plugin removal installs the plugin again, but does not restore its saved options.
- Kitden writes to your home folder, its own data folder, known projects and detected client settings folders. The preview shows which files will change. Project settings stay separate from the shared setup.

</details>

<details>
<summary>Let your agent read your setup</summary>

In Kitden, choose **Let agents read this setup**. Then ask your agent **"show my setup"**.
Kitden's own tools only read. Servers moved into the gateway add their tools, which do what those servers do.

Already have the `kitden` command? [Add to Cursor](https://cursor.com/en/install-mcp?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=).
The plain link is `cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=`.

</details>

## Contributing

Bug reports, documentation fixes and small improvements are welcome. For a larger change,
open an issue first so we can agree on the scope.

See [Contributing](https://github.com/KonstantinStarovoytov/kitden/blob/main/CONTRIBUTING.md) for setup, checks and what to include in a pull request.
To report a bug, include your Kitden and client versions, steps to reproduce it, and what
you expected. Remove secrets and private paths from screenshots and logs.

## License

Kitden is licensed under [Apache-2.0](https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE).

[Roadmap](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md) · [Issues](https://github.com/KonstantinStarovoytov/kitden/issues) · [Releases](https://github.com/KonstantinStarovoytov/kitden/releases) · [Development](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/development.md)
