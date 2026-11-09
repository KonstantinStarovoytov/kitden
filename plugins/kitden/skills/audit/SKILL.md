---
name: audit
description: Use when the user asks what to turn off, wants less context or fewer tools in this project, or asks to audit, review or clean up what their coding agents load.
---

Find what this project loads and does not need. You suggest; the user makes the changes.

1. Call the kitden tool `list_findings` with `project_path` set to the current folder. Then call
   `show_setup` with the same path and `client` set to the client you run in: the whole setup is
   too large for one answer. Look at another client only if the user asks. If the tools are
   missing, follow the kitden `setup` skill and stop.
2. Learn what the project is: read its README and its manifest (`package.json`,
   `pyproject.toml` and the like), and use what the user asked for in this session. Read no more
   than that.
3. Go through the MCP servers, skills and plugins whose `enabled` is `on`. Judge a plugin as one
   item, not each skill inside it. Skip hooks and instruction files. If a name tells you nothing,
   call `explain_item`. If it is still unclear, write "not sure"; do not guess.
4. Show one short table: item, what to do, why in one line. List only items with no clear use
   here, and duplicates or overrides from `list_findings`. Put similar items in one row. Leave
   out what fits the project.
5. Take "what to do" from the item's `actions`. Suggest turning an item off before removing it.
   If it can only be removed, say that this removes it for every project. If it has a
   `change_hint`, pass the hint on: only the client itself can change that item.
6. Say what you judged by. Kitden's tools do not tell how often an item is used, so the list
   comes from what the project is, not from use.
7. Never edit client settings files. Run `kitden open` and send the user to the page, which
   previews, backs up and can undo every change.
