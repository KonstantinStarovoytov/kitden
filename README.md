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

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/walkthrough-dark.svg">
    <source srcset="docs/images/walkthrough.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/walkthrough.svg" width="880" alt="Move docs from Claude Code into Kitden: preview the connection, review which clients get access, then Apply. The server is now shared by Claude Code, Codex and Cursor.">
  </picture>
</p>

<p align="center">One shared gateway for your agents. Look at each change first. Apply keeps a backup for Undo.</p>

## Try it on a sample

Explore a sample setup without reading or changing your own settings.

<!-- Checked 2026-10-28: https://docs.astral.sh/uv/guides/tools/#requesting-different-sources -->
```bash
uvx --from git+https://github.com/KonstantinStarovoytov/kitden kitden demo
```

macOS · Requires [uv](https://docs.astral.sh/uv/) and Git · No account · No telemetry

This is a preview of the next release, run from source. Already in this checkout? Run `uv run kitden demo`.

## See what each agent loads

Compare plugins and skills across clients. See what is on, what is off, and what is missing.
Kitden also finds hooks, marketplaces and instruction files, and shows where they come from.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/compare-dark.svg">
  <source srcset="docs/images/compare.svg">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/compare.svg" width="880" alt="Library filtered to review: pr-review is off in Claude Code and Cursor. The code-review skill is on in Codex and Cursor, with an Add button for Claude Code.">
</picture>

## Change your mind? Undo.

Every applied change has a history and a backup. Undo restores the previous files.
If a file has changed since Apply, Kitden stops rather than overwriting your newer work.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/undo-dark.svg">
  <source srcset="docs/images/undo.svg">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/undo.svg" width="880" alt="The same change before and after Undo: first Applied with an Undo button, then crossed out and marked Undone.">
</picture>

## Use your own setup

Run the current source on your Mac:

```bash
uvx --from git+https://github.com/KonstantinStarovoytov/kitden kitden
```

Kitden opens in your browser at `127.0.0.1`. It reads your setup; changes wait for you to press Apply.
Linux and Windows are not supported yet.

<details>
<summary>Other ways to install</summary>

The published version is earlier than the preview above: `uvx kitden`.
Without uv, this installs uv and the earlier release, then opens the page:

```bash
curl -LsSf https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.sh | sh
```

</details>

<details>
<summary>Let your agent read your setup</summary>

In Kitden, choose **Let agents read this setup**. Then ask your agent **"show my setup"**.
Kitden's own tools only read. Servers moved into the gateway add their tools, which do what those servers do.

Already have the `kitden` command? [Add to Cursor](https://cursor.com/en/install-mcp?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=).
The plain link is `cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=`.

</details>

<details>
<summary>How changes, backups and secrets work</summary>

- Changes wait in one tray. **Show changes** shows the exact edit; Apply backs it up, writes it and checks it.
- Backups stay for 30 days, and the newest 100 changes always keep theirs. Changes also offers **Redo…** and **See it on the map**.
- Use **Add missing plugins and skills…** in Library to fill gaps. Project settings stay separate from the shared setup.
- Kitden writes only in your home folder and your known projects.
- Secrets stay on this Mac. They go only to the server they belong to, or to a gateway you move that server into.
- Secret values are never shown or logged. Kitden goes online to reach remote servers you add and to read a GitHub marketplace when you add its link.

</details>

[Roadmap](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md) · [Issues](https://github.com/KonstantinStarovoytov/kitden/issues) · [Releases](https://github.com/KonstantinStarovoytov/kitden/releases) · [Development](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/development.md) · [Apache-2.0](https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE)
