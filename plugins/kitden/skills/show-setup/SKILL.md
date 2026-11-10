---
name: show-setup
description: Use when the user asks which MCP servers, skills, plugins, hooks or instruction files (CLAUDE.md, AGENTS.md) Claude Code, Codex or Cursor load, where one comes from, why one loads twice, or wants to turn one on or off or remove it.
---

Kitden shows what Claude Code, Codex and Cursor load on this computer, where each item comes
from, and what loads twice. Its command `kitden show` only reads and prints JSON.

1. Run it in the project's folder, or add `--project PATH`:
   - `kitden show setup --client CLIENT`: what one client loads (`claude_code`, `codex`,
     `cursor`). Without `--client` the answer is every client's and is large.
   - `kitden show findings`: problems, such as an item that loads twice.
   - `kitden show item NAME`: every place a name is set, which one loads, and `why`.
   - `kitden show projects`: the projects the clients know.
2. If `kitden` is not found or the command fails as unknown, follow the kitden `install` skill.
3. Do not edit client settings files to change the setup. Run `kitden open` and send the user to
   the page: it previews, backs up and can undo every change.
