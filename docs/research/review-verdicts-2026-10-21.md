# Verdicts on the product brief

Date: 2026-10-21, baseline `d33bfaf`. This file answers section 9 of
[product-review-2026-10-21.md](product-review-2026-10-21.md) (the second agent's brief). The
first review by this reviewer is [vision-review-2026-10-21.md](vision-review-2026-10-21.md).

Method: read the code behind every finding; ran the full checks (`uv run pytest -q`: 787
passed, 9 contract tests deselected; `uv run ruff check .` clean;
`node --test tests/frontend/*.test.mjs`: 91 passed); ran the page on a sandbox home with 13
servers and a Kitden gateway holding two. Nothing in the repository changed.

## Verdict on each finding

| Finding | Verdict | What it is | Evidence |
| --- | --- | --- | --- |
| F1 Add in a project view goes global | Confirmed | UX gap | `PROJECT_NOTE = "Adds for all your projects."` and the comment above `projectNote()` in `src/kitden/web/static/js/offer.js`; `install_steps` and `skill_steps` in `src/kitden/changes/actions.py` write `Scope.USER`. The note comes in the review, after the click. |
| F2 Saved settings are not live context | Partly confirmed | Wording | The Library says "Based on saved settings"; a rule's review says "Applies to new sessions." (`src/kitden/views/after.py`). Only the word "Loads" is left. Low priority. |
| F3 A matching name is not equivalence | Confirmed as a limit | Product boundary | `row_key()` in `src/kitden/views/load_map.py`: plugins by full id, the rest by name. Not a bug. |
| F4 New tools are on by default | Confirmed | Design gap for a strict mode | `_is_on()` in `src/kitden/local_gateway/settings.py` returns on without a rule; `test_a_rule_for_a_missing_tool_is_ignored_and_a_new_tool_is_on` pins it. |
| F5 No revocation in an open session | Confirmed | Documented limit that blocks the access-control goal | `_Gateway.__init__` loads the settings once, `_offered()` finds the tools once, `call_tool()` uses that set (`src/kitden/local_gateway/proxy.py`). Codex keeps a tool list for up to 30 minutes anyway (`docs/development.md`), so refusing at call time is the only enforcement that works. |
| F6 Unknown project gets global rules | Confirmed as behavior | Owner decision | `project_chain()` returns an empty chain for an unknown folder (`project.py`); `_known()` returns none on an error (`proxy.py`). A defect only when global rules are wider than a project's. |
| F7 Local files are not a full boundary | Confirmed | Documented limit | `src/kitden/changes/backup.py`: a backup holds the original bytes, mode 600 in a 700 folder, kept 30 days or the newest 100. `gateway.json` is plain text, mode 600. Same as the clients' own files; Kitden adds copies. |
| F8 Overview says there is no gateway | Confirmed | Bug | `overview()` in `src/kitden/views/overview.py` builds the card from registered gateways only. Reproduced on the sandbox. |
| F9 Instructions are not in the inventory | Confirmed | New scope | `ItemKind` in `src/kitden/model.py` has five kinds. |

## Where the brief is weak

- Most proposals say "evaluate" or "review whether", and section 9 asks the next reviewer for
  six deliverables. For a tool for one person this is heavy, and `AGENTS.md` asks for the
  simplest mechanism, no speculative options.
- It ran 155 of 787 tests and did not measure speed. The reading itself takes 0.01 s on the
  sandbox (`build_inventory`, 54 items). What costs time at start is `read_command_version` in
  `src/kitden/clients/base.py`: each client's `--version` with a 20 s timeout and a 10-minute
  cache in memory only; Cursor starts Electron for it. The brief does not name this.
- OAuth is the main reason most remote servers cannot move into the gateway today; the brief
  keeps it in section 5 as a limit. Linux and Windows are not mentioned.
- The design-detector paragraph in section 4 adds nothing, as the brief itself says.
- `ROADMAP.md` has an uncommitted "Under review" section that links the brief. The roadmap
  changes when what Kitden does or plans changes; a review does not. Revert it.

## The gateway boundary, in short

What holds: the local page (host, token, cookie, origin, CSP), one redaction path with a
sentinel test, a minimal environment for started servers, a read-only MCP server for agents.
What the gateway does not do, and the page should say: it governs only servers that go through
it, not direct entries, terminals or other routes; it does not sandbox a local server process;
it does not revoke in an open session; it keeps secrets in files (`gateway.json` and backups).
Rules follow a project only when the session names its folder; otherwise the global set
applies. A server's read-only and destructive hints are untrusted input, not a guarantee.

## Smallest useful next release

1. Overview knows the Kitden gateway (F8).
2. A strict mode per held server: an allowlist of tools; a tool the server adds later waits for
   review; hints and a name heuristic (write, create, delete, update, send, remove) only
   pre-fill the list; `call_tool` reads the rules again and refuses a tool that is off now
   (F4, F5). The current switches stay as they are outside strict mode.
3. In a project view, the Add cell says "all projects" before the click (F1). No project-scoped
   install yet.

Left for later, on purpose: the instructions tab (F9), logins in one place and the keychain
(F7), the unknown-project policy (F6), Linux and Windows, removal of plugins and servers.

## Acceptance checks

On a sandbox home (`tests/fixtures`, never the real home):

- With servers in `gateway.json` and a client's `kitden` entry, Overview shows the Kitden
  gateway and no "Set up".
- Strict mode on a server, then a new tool in the tool cache: the gateway does not offer it
  (`tests/unit/test_local_gateway_settings.py`).
- A tool turned off after a session's first `tools/list`: the next call is refused with one
  plain sentence (`tests/unit/test_local_gateway_proxy.py`, with the echo server).
- Add from a project view: the cell names "all projects" before the review opens
  (`tests/unit/test_page_words.py`, `tests/frontend/`).

In real clients, on a throwaway project as `docs/development.md` describes: move a server in,
turn strict mode on, start a new session and see only the allowed tools; turn one off and call
it in the same session, see the refusal; Undo both and see the server direct again.

## Questions only the owner can answer

1. Unknown project: the global rules, or nothing at all in strict mode?
2. Project-scoped install: wanted, or is global with clear wording enough?
3. Is it acceptable that the gateway governs only what goes through it, and should the page
   say so?
