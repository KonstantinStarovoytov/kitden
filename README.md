<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/hero-dark.svg">
    <source srcset="docs/images/hero.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/hero.svg" width="640" alt="Kitden: Your AI coding tools, under one roof.">
  </picture>
</p>

<h3 align="center">Your AI coding tools, under one roof.</h3>

<p align="center">See and change what <b>Claude Code, Codex and Cursor</b> load.<br>
MCP servers, plugins and skills, with preview and Undo.</p>

## Requirements

- **macOS.** Linux and Windows are not supported yet.
- **[uv](https://docs.astral.sh/uv/)** to download and run Kitden. The commands below let uv get Python 3.13 if needed.
- **Internet for the download.** The demo itself stays offline. No account or API key is needed.

Git is not required. To use your own setup, have at least one of Claude Code, Codex or Cursor installed. The demo needs none of them.

If you do not have uv, install it with its official installer, then open a new Terminal window:

<!-- Checked 2026-10-28: https://docs.astral.sh/uv/getting-started/installation/ -->
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Try safely on a sample

Run this in Terminal. It downloads Kitden into a separate environment and opens a sample setup in your browser:

<!-- Checked 2026-10-28: https://docs.astral.sh/uv/concepts/projects/dependencies/#url -->
```bash
uvx --python 3.13 --from \
  https://github.com/KonstantinStarovoytov/kitden/archive/refs/heads/main.zip kitden demo
```

**Your real settings and secrets are not read or changed.** Even Apply and Undo work only on temporary sample files. The demo starts no MCP servers and uses no real client or Keychain. Press **Ctrl+C** in Terminal to stop it and delete the sample. The downloaded app stays in uv's cache.

Try **Library → List**: find **pr-review** and press **+ Add** in the **Codex** column. Inspect **Show changes**, close the panel, then press **Apply**. Open **Changes → Undo** to put it back. You can try Gateway in the same demo.

This is a preview of the next release, run from source. The ZIP comes from this project's GitHub repository. Already in this checkout? Run `uv run kitden demo`.

## Install and use your own setup

```bash
uv tool install --python 3.13 \
  https://github.com/KonstantinStarovoytov/kitden/archive/refs/heads/main.zip
kitden
```

Run `kitden` to open it again. If Terminal cannot find it, run `uv tool update-shell` and open a new Terminal window.

**Opening Kitden reads your setup. Changing it requires Apply.** The page runs on your Mac at `127.0.0.1`, with a private access link. It has no account and no telemetry.

## Manage plugins, skills and instructions

Open **Library**. Choose **All projects** or one project at the top. **List → Differences** shows what your clients load differently; click an item to open its **Details**.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/compare-dark.svg">
  <source srcset="docs/images/compare.svg">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/compare.svg" width="880" alt="Library filtered to review: pr-review is off in Claude Code and Cursor. The code-review skill is on in Codex and Cursor, with an Add button for Claude Code.">
</picture>

| What | What you can do in Kitden |
| --- | --- |
| **Plugins and skills** | Use **+ Add** to browse your marketplaces, or drag an installed item onto another client. Open **Details** to turn it on or off, choose its project scope, or remove a copy where the client supports it. |
| **Missing plugins and skills** | Choose **Add missing plugins and skills…**, pick what each client should get, review, then Apply. |
| **Marketplaces** | Browse what they offer. **+ Add → Add a marketplace…** adds a GitHub source. **Details → More → Commands…** shows commands you can copy to update or remove a marketplace or plugin yourself. |
| **Hooks** | See which client loads each hook and where it comes from. Hook settings are read-only here. |
| **Instruction files, commands and agents** | Open **Library → Instructions** to trace which files each client reads and what they pull in. Inspect them in Details; edit the files in your editor. Kitden only reads them. |

Available actions depend on the client. The preview names the clients and projects affected. Adds on the map apply to all projects; an Add in the List asks for a scope when that client supports it. Start a new client session after Apply to load the change.

## Share MCP servers through one gateway

Open **Gateway** to share a server between clients and turn its tools on or off for each project. It controls only servers you put into it. Library management works without moving servers into the gateway.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/walkthrough-dark.svg">
    <source srcset="docs/images/walkthrough.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/walkthrough.svg" width="880" alt="Move docs from Claude Code into Kitden: preview the connection, review which clients get access, then Apply. The server is now shared by Claude Code, Codex and Cursor.">
  </picture>
</p>

## Is it safe to use on my setup?

- **You choose each edit.** Look at each change first. Apply keeps a backup for Undo. **Show changes** shows the exact edit; Apply writes it and checks the result.
- **Changes has Undo.** If a file has changed since Apply, Kitden stops rather than overwriting your newer work. Undo does not reverse actions already run by a plugin or MCP tool.
- **Your data stays local unless a tool needs a connection.** Kitden reads local client settings. Secrets stay on this Mac. They go only to the server they belong to, or to a gateway you move that server into. Secret values are never shown or logged. Kitden goes online to reach remote servers you add and to read a GitHub marketplace when you add its link.
- **Trust what you add.** Kitden has access to change your client settings. Plugins and MCP servers may run code or reach services with your permissions; preview and backups do not make untrusted tools safe.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/undo-dark.svg">
  <source srcset="docs/images/undo.svg">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/undo.svg" width="880" alt="The same change before and after Undo: first Applied with an Undo button, then crossed out and marked Undone.">
</picture>

<details>
<summary>Backup limits and write access</summary>

- Backups stay for 30 days, and the newest 100 changes always keep theirs. Changes also offers **Redo…** and **See it on the map**.
- Undo of plugin removal installs the plugin again, but does not restore its saved options.
- Kitden writes only in your home folder and your known projects. Project settings stay separate from the shared setup.

</details>

<details>
<summary>Let your agent read your setup</summary>

In Kitden, choose **Let agents read this setup**. Then ask your agent **"show my setup"**.
Kitden's own tools only read. Servers moved into the gateway add their tools, which do what those servers do.

Already have the `kitden` command? [Add to Cursor](https://cursor.com/en/install-mcp?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=).
The plain link is `cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=`.

</details>

[Roadmap](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md) · [Issues](https://github.com/KonstantinStarovoytov/kitden/issues) · [Releases](https://github.com/KonstantinStarovoytov/kitden/releases) · [Development](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/development.md) · [Apache-2.0](https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE)
