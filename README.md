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

## See what each agent loads

Compare plugins and skills across Claude Code, Codex and Cursor. Add what is missing,
choose what a project loads, and trace each item to its source.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/compare-dark.svg">
  <source srcset="docs/images/compare.svg">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/compare.svg" width="880" alt="Library filtered to review: pr-review is off in Claude Code and Cursor. The code-review skill is on in Codex and Cursor, with an Add button for Claude Code.">
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
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/walkthrough.svg" width="880" alt="Move docs from Claude Code into Kitden: preview the connection, review which clients get access, then Apply. The server is now shared by Claude Code, Codex and Cursor.">
  </picture>
</p>

## Review a change. Apply it. Undo it.

Look at each change first. Apply keeps a backup for Undo. **Show changes** shows the exact
edit; Apply writes it and checks the result. Open **Changes → Undo** to restore it.
If a file has newer edits, Kitden stops rather than overwriting them.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/undo-dark.svg">
  <source srcset="docs/images/undo.svg">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/undo.svg" width="880" alt="The same change before and after Undo: first Applied with an Undo button, then crossed out and marked Undone.">
</picture>

Kitden can change your client settings. Only add plugins and MCP servers you trust:
they can run code with your permissions. Undo does not reverse actions a tool already ran.

## Try safely on a sample

Explore the full page on temporary sample files. **Your settings and secrets are not read
or changed**, even when you press Apply. The demo stays offline and starts no real clients
or MCP servers.

Requires **macOS** and **[uv](https://docs.astral.sh/uv/)**. uv gets Python 3.13 if needed.
This is a preview of the next release, run from source.

<!-- Checked 2026-10-28: https://docs.astral.sh/uv/concepts/projects/dependencies/#url -->
```bash
uvx --python 3.13 --from \
  https://github.com/KonstantinStarovoytov/kitden/archive/refs/heads/main.zip kitden demo
```

In **Library → List**, find **pr-review** and press **+ Add** under **Codex**. Review,
Apply, then try Undo in Changes. Press **Ctrl+C** in Terminal to stop and delete the sample.

<details>
<summary>Install uv</summary>

Use uv's official installer, then open a new Terminal window:

<!-- Checked 2026-10-28: https://docs.astral.sh/uv/getting-started/installation/ -->
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

</details>

## Install for your own setup

Have Claude Code, Codex or Cursor installed, then run:

```bash
uv tool install --python 3.13 \
  https://github.com/KonstantinStarovoytov/kitden/archive/refs/heads/main.zip
kitden
```

Opening Kitden reads your setup; edits wait for Apply. Run `kitden` to open it again.
If the command is not found, run `uv tool update-shell` and open a new Terminal window.

<details>
<summary>Privacy and backup limits</summary>

- The page runs locally at `127.0.0.1`, with a private access link. No account or telemetry.
- Secrets stay on this Mac. They go only to the server they belong to, or to a gateway you move that server into. Secret values are never shown or logged. Kitden goes online to reach remote servers you add and to read a GitHub marketplace when you add its link.
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
