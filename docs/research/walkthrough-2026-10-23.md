# Walkthrough 1: today's page

Date: 2026-10-23. Script: [walkthrough-script-1.md](walkthrough-script-1.md). Person: the owner.
Setup: `uv run kitden demo --size medium` from branch `visual-part1-demo`, dark theme, the
owner's own browser. The observer gave each task's title only and wrote down what happened.

## Results

| Task | Done | Wrong turns | What was confusing |
| --- | --- | --- | --- |
| 1 Why Codex and Cursor both have `code-review` | Partly | Overview notes, then the Clients card → Codex → "3 skills" → Library | Details says "Global settings" per client, not that one folder serves both. Only "Remove from Codex…", no "Remove from Cursor": looks wrong without a reason |
| 2 Pick Atlas, find what differs | Partly | — | Cannot tell what comes from all projects and what is Atlas's own, though cells say "global settings" / "this project". "Add missing…" shows the same list on Plugins, Skills and MCP servers |
| 3 Add the missing skill to Atlas only | No | Opened `api-style`'s Details | Most cells say "global settings", some "via Codex", "via plugin": two different facts in one place. Claude Code's `api-style` cell is "—"; its Details has no add button |
| 4 Look at the two `docs` servers | No | Stayed in Overview's notes | A third "docs · Set up in more than one client" row with no icon. Nothing says the two are different servers; that note says they are one thing set up twice |
| 5 Turn off `read_file` of `files` for Atlas | No (did it for all projects) | First moved Cursor's `files` into the gateway | The picker stayed on Global; the tools panel has no project choice of its own, and its scope words were not noticed |
| 6 (adapted) Why the gateway's switches do not affect `docs` | Yes | — | Said "local settings" for "each client's own settings"; the page's word "Direct" did not come up |
| 7 Undo the change from task 5 | Yes | — | Undo on Changes was found at once; pressed twice and checked |

Task 6 was adapted: task 5's extra move took Cursor's direct `files` entry into the gateway, so
the question moved to `docs`.

Wrong beliefs about scope or protection: in task 5 the owner believed the switch was for Atlas's
task while it was set for all projects (the owner then said correctly that it was for all
projects). Nothing else.

Words: for a cell **"Available"**; for a tool **"On" and "Off"**.

## Findings

| # | Finding | Goes to |
| --- | --- | --- |
| F1 | Details does not say that one folder serves two clients, nor that removing it removes it for both | Part 3 (Why and Affects; the Remove label names every client it reaches) |
| F2 | The Clients card counts ("3 skills") are a way in; they lead to the tab, not to the item | Part 2 (the count opens the tab with that client's items selected), Part 6 |
| F3 | In a project, "from all projects" and "this project's own" do not stand apart | Part 2 (every cell in a project view says where it applies), Part 4 (Differences) |
| F4 | "Add missing…" ignores the tab | Part 4 (it follows the tab: "Add missing skills…") |
| F5 | One quiet word mixes where an item applies with how the client gets it | Part 2 (the cell says only where; the route goes to Details and the hover text) |
| F6 | A dead "—" where Kitden could add; Details offers no add | Part 2 (a cell Kitden can fill says "+ Add"; Details offers the add) |
| F7 | "Set up in more than one client" for two different sources claims they are one | Part 2 (same name, another source = "Needs review"; a note row always shows its clients) |
| F8 | One name takes three note rows on Overview | Part 2 (notes are grouped by item) |
| F9 | First instinct: move everything into the gateway before looking at tools | Part 3 ("Manage tools" from the Library row), Part 5 (the Gateway page shows what is already held per client) |
| F10 | A tool switch follows the top picker; its scope is easy to miss | Part 5 (the tools panel has its own scope choice; the review leads with the scope) |
