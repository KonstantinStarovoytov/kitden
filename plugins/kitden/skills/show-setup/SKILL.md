---
name: show-setup
description: Use when the user asks which MCP servers, skills, plugins, hooks or instruction files (CLAUDE.md, AGENTS.md) Claude Code, Codex or Cursor load, where one comes from, why one loads twice, wants to turn one on or off or remove it, or wants to open Kitden.
---

Kitden shows what Claude Code, Codex and Cursor load on this computer, where each item comes
from, and what loads twice.

1. For questions, call the kitden tools: `show_setup`, `list_findings`, `explain_item` and
   `list_projects`. They only read.
2. To open the page, run `kitden open`. It returns at once and prints the link.
3. Do not edit client settings files to change the setup. The page previews, backs up and can undo
   every change; send the user there.
4. If the kitden tools are missing, run `kitden --version`. If it fails, Kitden is not installed:
   show `uv tool install --python 3.13 kitden` and stop. If it works, ask the user to turn the
   kitden server on in the client.
