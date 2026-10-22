# Walkthrough script 1: today's page

Date: 2026-10-23  
Status: script, not run yet. The results go to `docs/research/walkthrough-<date>.md`.

The seven tasks of the [UX concept](visual-management-ux-concept-2026-10-22.md) (§12), on
today's page, before Part 2 changes it (spec 1.4). This is the baseline the concept asks for, and
it settles two words that are still a guess.

## Before

- About 15 minutes.
- Run `uvx kitden demo --size medium` (from the repository: `uv run kitden demo --size medium`).
  The page opens on a sample setup in a temporary folder. Nothing on this computer is read or
  changed, so Apply is safe. Ctrl+C at the end deletes the sample.
- A normal desktop window.
- Nobody explains the page first. Read each task's title aloud, nothing more. The observer only
  writes things down: no hints, no answers. After 3 minutes stuck, mark the task not done and go
  on.
- Time: from reading the task to the first correct explanation.

## The sample, for the observer

`~` is the sample's home folder. Details shows it with the temporary folder's full path.

| Name | What it is |
| --- | --- |
| `code-review` | One skill folder, `~/.agents/skills/code-review`, that Codex and Cursor both read |
| `brandkit` | A skill in `~/.claude/skills`; Cursor reads it too |
| `atlas` | The project `~/work/atlas`; the project `web` (`~/work/atlas/web`) sits inside it |
| `api-style` | A skill only in Atlas, `~/work/atlas/.agents/skills/api-style`: Codex and Cursor load it, Claude Code does not |
| `docs` | Two servers with one name: Claude Code's is an address (`https://docs.example.test/mcp`), Codex's runs `npx docs-mcp`. In Atlas, `~/work/atlas/.mcp.json` replaces Claude Code's with `http://localhost:9000/mcp` |
| `files` | In the Kitden gateway, with `read_file`, `write_file`, `delete_file` and `search_files`. Atlas turns `write_file` off, so `web` has it off too; `web` turns `search_files` off itself. `search_files` has no hint, so its kind is unknown |
| `files` in Cursor | Cursor does not use the gateway. It has its own direct `files` entry |
| `tracker` | In the gateway, strict: only tools turned on are offered, so the new tool `export_report` waits, off |
| `~/work/website/.cursor/mcp.json` | Cut short, so it cannot be read; Overview shows it |

## Task 1: Explain why Codex and Cursor both have the skill `code-review`

- Start from: Overview, project Global.
- Done when: names the one shared folder and does not say two copies.

## Task 2: Pick Atlas and find what differs between the clients there

- Start from: Overview, project Global.
- Done when: finds a real difference (`api-style` missing in Claude Code, or `docs` overridden in
  Atlas) and tells it from what comes from all projects.

## Task 3: Add the missing skill to Atlas only

- Start from: where task 2 ended.
- Done when: says the scope (this project, Atlas) before Apply.
- Watch for: Claude Code's cell of `api-style` shows "—", not "+ Add"; "Add missing…" lists it.
  That review ticks other items, for all projects, before anyone chooses. Note whether they look
  at the ticks before Apply.

## Task 4: Look at the two `docs` servers of Claude Code and Codex

- Start from: Overview, project Global.
- Done when: notices they come from different sources and does not treat them as one.

## Task 5: Turn off the tool `read_file` of `files` for Atlas

- Start from: Overview, project Global.
- Done when: says it applies to Atlas and its folder `web`, and to new calls, not to a call
  already running.
- Watch for: a Details panel keeps the project it was opened with ("Tools · atlas"), even when
  the project at the top changes.

## Task 6: Explain why Cursor still reaches `files` around the gateway

- Start from: Overview, project Global.
- Done when: says Cursor has its own direct entry, so the gateway's switches do not apply to its
  calls.

## Task 7: Undo the change from task 5

- Start from: where task 6 ended.
- Done when: finds Undo and says what it puts back.

## Words to settle

Ask after the seven tasks. Write down the answer and the reason.

- A cell says what a client has. Should it say "Loads" or "Available"?
- A tool in the gateway can be turned off. Should its switch say
  "On" and "Off" or "Allowed" and "Blocked"?

## Results

| Task | Done | Wrong turns | Time | What was confusing |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |

Any wrong belief about scope (which projects or clients a change reaches) or protection (what the
gateway blocks):

Words: for a cell … · for a tool … · why …
