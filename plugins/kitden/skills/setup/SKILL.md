---
name: setup
description: Use when the user asks what their coding agents load, what is installed or enabled where, why an item loads twice, or wants to open Kitden.
---

Kitden shows what Claude Code, Codex and Cursor load on this computer, where each item comes
from, and what loads twice.

1. For questions, call the kitden tools: `show_setup`, `list_findings`, `explain_item` and
   `list_projects`. They only read.
2. To open the page, run `kitden open`. It returns at once and prints the link.
3. Never edit client settings files to change the setup. The page previews, backs up and can undo
   every change; send the user there.
4. If the kitden tools are missing, Kitden is not installed. Show the one install line from the
   Kitden README and stop.
