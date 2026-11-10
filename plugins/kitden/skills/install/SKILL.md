---
name: install
description: Use when the `kitden` command is not found or is too old for a kitden skill, or the user asks to install or update Kitden.
---

Kitden is a separate open-source program; the kitden skills run its command. It runs on macOS
and Linux. Install or update it only when the user says yes.

1. Run `kitden --version`. If it prints 0.7.2 or later, nothing is missing: go back to the task.
2. Ask the user first. Say that Kitden is not installed or is too old, and show the one line you
   would run. Without a yes, leave the line with them and stop.
3. Use the first way that fits this computer:
   - `uv` is there: `uv tool install --python 3.13 kitden`. To update: `uv tool upgrade kitden`.
   - Homebrew is there: `brew install konstantinstarovoytov/tap/kitden`. To update:
     `brew upgrade kitden`.
   - Neither: Kitden's own script installs uv and then Kitden:
     `curl -LsSf https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.sh | sh`.
     It downloads and runs a script: say so when you ask.
4. Run `kitden --version` again. If the shell still does not find it, ask the user to open a new
   terminal, or run `uv tool update-shell`.
5. If the user wants an answer without installing, and `uv` is there, run the command once as
   `uvx --python 3.13 kitden ...`, for example `uvx --python 3.13 kitden show findings`.

Installing changes nothing in Claude Code, Codex or Cursor.
