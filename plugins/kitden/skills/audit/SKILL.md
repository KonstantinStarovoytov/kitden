---
name: audit
description: Use when the user asks what to turn off, wants less context or fewer tools in this project, or asks to audit, review or clean up what their coding agents load.
---

Find what this project loads and does not need. You suggest; the user makes the changes.

1. In the project's folder run `kitden show findings`, then `kitden show setup --client CLIENT`
   with the client you run in (`claude_code`, `codex` or `cursor`): the whole setup is too large
   for one answer. Look at another client only if the user asks. If `kitden` is not found or the command fails as unknown, follow the kitden `install` skill.
2. Learn what the project is: read its README and its manifest (`package.json`,
   `pyproject.toml` and the like), and use what the user asked for in this session. Read no more
   than that.
3. Go through the MCP servers, skills and plugins whose `enabled` is `on`. Judge a plugin as one
   item, not each skill inside it. Skip hooks and instruction files. If a name tells you nothing,
   run `kitden show item NAME`. If it is still unclear, write "not sure"; do not guess.
4. Show one short table: item, what to do, why in one line. List only items with no clear use
   here, and duplicates or overrides from the findings. Put similar items in one row. Leave out
   what fits the project.
5. Take "what to do" from the item's `actions`. Suggest turning an item off before removing it.
   If it can only be removed, say that this removes it for every project. If it has a
   `change_hint`, pass the hint on: only the client itself can change that item.
6. Say what you judged by: what the project is. Kitden does not tell how often an item is used.
7. Do not edit client settings files. Run `kitden open` and send the user to the page, which
   previews, backs up and can undo every change.
