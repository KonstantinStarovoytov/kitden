# Kitden against the owner's vision

Date: 2026-10-21. Reviewed at commit `d33bfaf` (version 0.2.0 plus the unreleased Library and
Kitden gateway work). Written for a second reviewer: every claim names the file to check.

Follow-up: [conclusions from both reviews](review-conclusions-2026-10-21.md), including
agreements, corrections and open questions. The original assessment below is preserved.

## The vision

The owner wants three things:

1. **One picture of everything an agent loads.** Per client (Claude Code, Codex, Cursor), what is
   global and what is per project: plugins, skills, MCP tools, and what reaches the context.
2. **Several agents at once.** See what loads twice, what is set up in one client and missing in
   another, and move or add items between clients so one project is the same everywhere.
3. **One local MCP gateway.** All MCP servers behind one entry, with per-tool control, including
   "read only": keep read tools, block write, edit and delete tools.

Three requirements: super simple and visual, with little text; fast to open; local and secure,
so tokens and headers never leave the Mac.

## How this review was done

- Read the code under `src/kitden/`, `README.md`, `ROADMAP.md`, `docs/design.md`,
  `docs/development.md` and `docs/research/ux-audit-2026-10-19.md`.
- Ran the page on a sandbox home built from `tests/fixtures` (never the real home), with 13 MCP
  servers across the three clients and a Kitden gateway holding two servers, one with
  `readOnlyHint` and `destructiveHint` on its tools. Looked at Overview, Library, Gateway, a held
  server's tool switches and a move review.
- Ran the checks: `uv run pytest -q` (787 passed, 9 contract tests deselected),
  `uv run ruff check .` (clean), `node --test tests/frontend/*.test.mjs` (91 passed).

## Verdict in one paragraph

Pillars 1 and 2 are largely there. Pillar 3 is half there: the gateway works, per tool and per
project, but has no read-only mode. The requirements are met well, security best of all. The
biggest holes are: no read-only mode, no instruction files in the picture, Overview does not know
the Kitden gateway, OAuth servers cannot move into the gateway, macOS only.

## Pillar 1: one picture

**Done.**

- The Library (`src/kitden/views/library.py`, `src/kitden/web/static/js/library.js`) has one row
  per item and one column per client found, with a project picker. Tabs: MCP servers, plugins,
  skills, hooks, marketplaces.
- What really loads is computed per client and project with scope ranks and overrides
  (`src/kitden/views/effective.py`), so "loads twice" means it does.
- Overview (`src/kitden/views/overview.py`) shows only what needs attention, each with one fix.

**Missing.**

- Instruction and rule files are not read: `CLAUDE.md`, `AGENTS.md`, `.cursor/rules`,
  `.cursorrules`, Claude Code commands and subagents. `ItemKind` in `src/kitden/model.py` has
  five kinds and none of these. For "what reaches the context" this is half the answer.
- No sense of weight: how many tools a server adds, or how many skills a project loads. The
  gateway keeps a tool list per held server (`gateway-tools.json`); direct servers have none.

## Pillar 2: several agents

**Done.**

- Findings (`src/kitden/views/findings.py`): duplicate in one client, cross-loaded from another
  client's folder, the same item set up separately in several clients, scope overrides.
- "+ Add" puts a plugin or a skill into another client in one review with Undo; "+ Add skills"
  copies a plugin's standalone skills into a client that cannot install the plugin.
- A project picker shows what each client loads in that folder.

**Missing.**

- An MCP server cannot be copied from one client to another. The only answer is "move it into
  the gateway" (`README.md`, Library section). A user who does not want a gateway has no way to
  align servers.
- No removal: a plugin cannot be removed, only turned off (`ROADMAP.md`, Later). "Keep one…" for a
  duplicate leads to the Library, where the fix is a switch.
- No "make this project like Claude Code" action; alignment is one item at a time.

## Pillar 3: the gateway

**Done.**

- `kitden mcp` is the gateway (`src/kitden/local_gateway/proxy.py`): local servers (a command)
  and remote ones (streamable HTTP). Tools are offered under stable unique names.
- Rules per server and per tool, global or per project, with folders and git worktrees following
  the project (`src/kitden/local_gateway/settings.py`, `project.py`). Each switch is one review
  with a backup and Undo.
- Moving a server in carries the tool switches Claude Code and Codex already had
  (`local_move_steps` in `src/kitden/changes/actions.py`).

**Missing.**

- **No read-only mode.** Servers send `readOnlyHint` and `destructiveHint`; the cache keeps them
  (`save_tools` in `settings.py`) and the proxy passes them on (`_tool` in `proxy.py`), but
  `tools_view` in `src/kitden/local_gateway/views.py` returns only name, description and state,
  and `toolRows` in `src/kitden/web/static/js/panel.js` draws one switch per tool. In the sandbox,
  `read_file` and `delete_file` looked the same. Needed: a "reads" / "writes" mark per tool and one
  button "Turn off every writing tool" for a server or for the whole gateway. Where a server
  sends no hints, a name heuristic (write, create, delete, update, send, remove) can fill in,
  shown as a guess.
- **Overview ignores the Kitden gateway.** `overview()` builds the gateway card only from
  registered gateways (`if gateways:`), which are Obot and MetaMCP. With two servers held and two
  clients connected, the sandbox Overview said "No gateway yet" and offered "Set up". Listed in
  `ROADMAP.md` under Later.
- **OAuth servers stay direct.** `local_move_steps` refuses a server whose `initialize` answers
  401 or 403 (`needs_sign_in`). GitHub, Notion and Linear remote servers mostly use OAuth today,
  so most remote servers cannot move in until "logins in one place" exists (`ROADMAP.md`, Later).
- Also refused: entries with `${VAR}` references, entries in a project's own files, entries with
  their own `cwd`, SSE and WebSocket. `README.md` lists them with reasons.
- No removal of a server from the gateway (Later).
- No record of calls. Even a count per tool would help the "secure" story; arguments must not be
  logged.

## Requirement: simple and visual

Met. The page is calm, with little text; actions sit in the cell; paths and commands stay in
Details. `docs/design.md` is followed. Small things seen in the sandbox:

- The "Show N notes" list had 27 entries, many of them "set up in more than one client",
  including the `kitden` entry itself. Notes about Kitden's own entries and gateway items should
  stay out (`SAME_IN_OTHER_CLIENTS` in `findings.py`).
- The Gateway page gets long with 13 servers: "Can move into the gateway" and "Run on this Mac"
  are two full lists. Folding the groups or putting "Move all" at the top would help.
- The sandbox stubbed the clients' version commands, so every client said "version unknown"; on a
  real Mac the version shows. Not a product issue.

## Requirement: fast to open

Met for the reading itself: `build_inventory` on the sandbox home (54 items, 5 projects) took
0.01 s. What costs time is outside the files:

- Each client's `--version` command runs in `detect()` (`read_command_version` in
  `src/kitden/clients/base.py`): a 20 s timeout and a 10-minute cache in memory only. Cursor
  starts Electron for this. Reading the version from the app bundle or package files, and caching
  it on disk, would remove this from every start.
- `codex plugin list --json` is slow and already runs in the background.
- `uvx kitden` has its own cold start.

## Requirement: local and secure

The strongest part. Checked:

- `src/kitden/web/security.py`: only `127.0.0.1` or `localhost` with the right port, a one-time
  start link that sets an HttpOnly SameSite=Strict cookie, same-origin and a custom header on
  every state change, no CORS, a strict CSP with no inline code. `tests/security/` covers it.
- `src/kitden/redact.py` is the one place secrets are removed; `test_no_secrets.py` checks every
  output for fixture sentinels.
- The gateway starts servers with a minimal environment (HOME, USER, LANG, PATH and the server's
  own env) and silences the HTTP library's logs, which print addresses (`proxy.py`).
- The MCP server for agents is read-only, with `readOnlyHint` on every tool
  (`src/kitden/mcp_server.py`).

Points for the reviewer:

- `gateway.json` holds env values and headers in plain text, mode 600. Same as the clients' own
  files, so no worse, but a keychain is the right next step (Later in `ROADMAP.md`).
- The move review sends one POST to the remote server's own address with its own headers to
  detect OAuth (`needs_sign_in`, no redirects, no proxy). Fine, but the review text could say so.
- The background page keeps its start token in `page.json`, mode 600, and stops after 10 idle
  minutes (`src/kitden/page.py`).

## Platform

macOS only. Install scripts stop elsewhere; paths are macOS paths. For an audience that runs
several agents, Linux and Windows matter. `ROADMAP.md` lists them under Next.

## Suggested order

1. Read-only mode in the Kitden gateway: reads/writes marks per tool, one button to turn off every
   writing tool, name heuristic where hints are missing. Small, and exactly the owner's scenario.
2. Overview knows the Kitden gateway: the card and "N servers can move into the gateway".
3. An Instructions tab in the Library: `CLAUDE.md`, `AGENTS.md`, Cursor rules, commands, agents.
4. Logins in one place: OAuth through the gateway, secrets in the keychain. Big, but it unlocks
   moving most remote servers.
5. "+ Add" for an MCP server into another client without a gateway.
6. Linux and Windows.
7. Remove a plugin; remove a server from the gateway.

## Housekeeping

`docs/research/`, `docs/superpowers/`, `.impeccable/` and `.specify/` are not in git. Decide to
commit or ignore them.

## Questions for the second reviewer

- Is a name heuristic for "writing" tools acceptable when a server sends no hints, if the page
  marks it as a guess?
- Should an MCP server be copyable between clients at all, given that the entry may hold a token
  and the copy makes a second secret?
- Is reading versions from app bundles reliable enough across Claude Code, Codex and Cursor?
