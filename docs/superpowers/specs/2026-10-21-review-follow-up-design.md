# Review follow-up: the whole picture, aligned clients, a gateway you can trust

Date: 2026-10-21. Baseline `d33bfaf`. Status: approved 2026-10-21; the plan follows it.

Sources, all in `docs/research/`: `vision-review-2026-10-21.md` (V), `product-review-2026-10-21.md`
(F1–F9 and sections P), `review-verdicts-2026-10-21.md` (R) and
`review-conclusions-2026-10-21.md` (C). The table at the end maps every recommendation in them to
a section here, so nothing is lost.

## Why

The owner wants Kitden to serve three groups, which overlap:

1. People on one coding agent who have lost track of what loads where: plugins, skills, MCP
   servers and hooks, global and per project. They want one place to see it all, turn things on
   and off, move things into a project, and tidy up.
2. People on several agents at once (Claude Code, Codex, Cursor) who want the same setup in each,
   managed from one place.
3. People who want one local MCP gateway that holds every server, lets them control single tools,
   restrict access in a smart way, and do all of that per project.

Three requirements hold for everything: the page must be simple and visual, so a person
understands at a glance and wants to press the buttons; it must open fast and never make a
person wait; and it must be secure, local, with secrets staying where they belong.

Two reviews and a cross-review (sources above) found that pillars 1 and 2 are largely built,
pillar 3 is half built, and a few claims on the page and in the docs are not true. This design
closes every gap they named.

## Goals

- The page tells the truth: Overview knows the Kitden gateway; an Add says its scope before the
  click; notes that help nobody stay out; the docs match the code.
- The gateway has an access contract a person can trust: a strict mode that allows only chosen
  tools, keeps new tools out until reviewed, refuses a switched-off tool at once in open sessions,
  and says plainly what it does not control.
- Management is complete: remove a plugin, a skill or a gateway server; add an MCP server to
  another client; add an item into one project; align a project across clients in one review.
- Opening is fast and measured: the first scan never waits for a client's version command, and
  a script reports two numbers on a large sandbox setup.
- Secrets have a lifecycle: gateway secrets live in the Keychain, backups say when they hold one,
  and OAuth servers can move into the gateway.
- The picture is whole: instruction files, commands and agents show in the Library.
- Linux and Windows work.

## Non-goals

- A live view of what a running session has in its context. Kitden reads saved settings and
  says so (F2). No "live context inspection".
- Proving that an allowed tool is harmless. An allowlist controls which tools can be called,
  not what their code does (C4).
- Sandboxing local server processes (P7).
- Stopping a tool call that is already running (F5).
- Teams and shared setups (roadmap, Later).
- Prompts and resources of gateway servers: tools only, as today.

## Anti-goals

- A success look before the server says `verified`. Every change keeps preview → Apply with a
  backup → verify → Undo. Nothing else ever writes a client's file.
- A secret on the page, in a review, in a log or in an error message.
- A promise the code cannot keep: "read-only" where it means "fewer tools", "one-time" where it
  means "while the page runs", "nothing leaves the Mac" where a remote server gets its own token.
- More text on the main pages. A name, the client and an action; the rest in Details.
- A speculative option. Each part below is the simplest mechanism that meets its goal.

## Constraints

- `AGENTS.md`: code, comments, UI text and docs in simple English; talk to the owner in Russian;
  `docs/design.md` for how the page looks and moves; tests on sandbox homes only; run
  `uv run pytest -q`, `uv run ruff check .` and `node --test tests/frontend/*.test.mjs` before
  each commit; `ROADMAP.md` updated in the same change; a release notes file per release; facts
  about other tools checked against their docs with the date written next to the claim.
- Python 3.13, Starlette, the official MCP SDK (2.3), tomlkit, watchfiles; plain ES modules and
  one CSS file; no framework, no bundler, nothing loaded from another site; strict CSP.
- No new runtime dependency unless a part says so. The Keychain is reached through the macOS
  `security` command, not a library.
- A part that touches a client's format first re-checks that client's current docs and writes
  the check date next to the fact, as the code does today.

## How it works

Parts are numbered. Each says what changes, how, and what "done" means. "My call" marks a
decision the owner did not make; the owner can change any of them.

### Part 1. Truth on the page

**1.1 Overview knows the Kitden gateway** (F8, V7, R1). `overview()` builds its gateway card
from the Kitden gateway first: the held servers (`held_servers`) and the clients whose `kitden`
entry is on (`setup_server_state`), then any registered Obot or MetaMCP gateway. The card says
"Kitden gateway · N servers · Claude Code, Cursor" and, when a found client lacks the entry,
one action "Set up in Codex…". "Can improve" counts the direct servers that can move into the
Kitden gateway (the Gateway page's "move" and "local" groups, each server once) with "Review".
Only without any gateway and no held servers does the card say "No gateway yet." Done: on the
sandbox with two held servers and two connected clients, Overview shows the gateway and never
offers "Set up" for a connected client.

**1.2 An Add says its scope before the click** (F1, C8, R1). When a project is picked in the
Library, one quiet line above the table says "Adding puts an item in all your projects." and
every "+ Add" button's accessible name ends with "for all projects". No new dialog. Part 3.6
adds the per-project choice; until then this line is the whole truth.

**1.3 Notes that help nobody stay out** (V11, C3). `SAME_IN_OTHER_CLIENTS` skips Kitden's own
`kitden` entries and items that go through the Kitden gateway: they are meant to be in every
client. Every other cross-client note stays (C3: do not hide meaningful differences).

**1.4 Words match the code** (C7, R1).
- `security.py` and any doc: the start link works while the page runs; it is not single-use.
  My call: keep it reusable, because `kitden open` reopens the page with it; fix the words.
- The Agents page and README: "Kitden's own tools only read. Servers moved into the gateway add
  their tools, which do what those servers do."
- The security promise: "Secrets stay on this Mac and go only to the server they belong to."
- The move review for a remote server adds one line: "Kitden asked <server> once whether it
  needs a sign-in." (`needs_sign_in`).
- The first move carries a client's tool switches; a later update keeps the gateway's rules.
  The review says which (already partly there; make it exact).
- "Loads" in a cell stays (F2): the subtitle "Based on saved settings" already qualifies it, and
  a longer word would fight the design. My call.

**1.5 The gateway says what it governs** (R5, P7). Under the Kitden gateway card, one quiet
line: "The gateway controls only the servers in it. Direct entries and terminal tools are
outside it." Strict mode's review (2.1) adds: "For a real guarantee, give <server> a token that
can only read."

**1.6 The Gateway page stays short** (V12). The "Can move" and "Run on this Mac" groups show
six rows and a "Show all N" line; "Move all" stays at the group head. My call on six.

### Part 2. The gateway's access contract

The rules file `gateway.json` keeps its shape (`servers`, `rules.global`, `rules.projects`),
read along the project chain, deepest first. This part adds one field and changes two
behaviors.

**2.1 Strict mode per server** (F4, P4, C4, R1). A server's global rule gains
`"mode": "strict"`. My call, after the builder check: strict is set for all projects, not per
project, so there is one place to look and no project can end up unable to opt out; project
rules keep their power, because an explicit `on` or `off` in a project wins over the global rule
along the chain, as today. In strict mode a tool with no rule of its own along the chain is
off; only tools with an explicit `on` are offered. Outside strict mode nothing changes: a tool
without a rule is on. On the page, a held server's Details gets one switch "Strict: only tools
you turned on" above the tool list, live with "All projects" picked and shown read-only with a
project picked ("Set for all projects"). Turning it on opens a review that writes the mode and
an explicit global `on` for every tool offered right now, so the first effect is "nothing new
gets in", never "everything goes dark". Turning it off removes the mode; the explicit rules
stay. Each is one change with Undo. A move that carries a Codex `enabled_tools` list (an
allowlist) turns strict on for that server, so the list keeps its meaning; the review says so.

**2.2 New tools wait** (F4). In strict mode a tool that appears in the tool cache (after Refresh
tools or a session's first list) has no rule, so it is off, and its row says "New · off" with
its switch. Outside strict mode a new tool is on, as today, and the row says nothing. My call:
no "new" marking outside strict mode.

**2.3 A switched-off tool is refused at once** (F5, P5, C5). `call_tool` in the proxy reads
`gateway.json` again on every call (a small file; cheap), recomputes whether the server and the
tool are on for the session's chain, and answers an error result "`<tool>` is turned off in
Kitden." when they are not. The session's offered list stays as it was (clients cache it;
Codex for up to 30 minutes). Best effort, my call: when the rules file's modification time
changed and the offered set differs, the gateway sends `notifications/tools/list_changed`.
The rule review's note changes from "Applies to new sessions." to "A tool turned off is refused
at once. The client shows the new list in a new session."

**2.4 An unknown project** (F6, P6). Owner decision; the default here is my call: in a folder
Kitden does not know, or when the known projects cannot be read, the global rules apply, as
today, and the page says so where "All projects" is picked: "These switches also apply in
folders Kitden does not know." Cursor sessions started from the home folder count as unknown
(`project.py`). The alternative, "nothing in strict mode for an unknown folder", would blank
every such Cursor session; it is not taken unless the owner wants it.

**2.5 Reads and writes, as a helper** (V6, C4, R1). `tools_view` returns for each tool a
`hint`: `reads` when the server's annotations say `readOnlyHint: true`; `writes` when they say
`readOnlyHint: false` or `destructiveHint: true`; `may write` when there are no annotations and
the name holds a verb from a fixed list (write, create, delete, remove, update, set, send, post,
put, patch, move, rename, upload, execute, run); `unknown` otherwise. The row shows the hint as
one quiet word, with "(from the server)" or "(by its name)" in the hover text. Details gets one
button "Turn off every writing tool…": a review with one rule step per tool whose hint is
`writes` or `may write`, listing them, with two lines: "Hints come from the server and names
are a guess; check the list." and the token line from 1.5. The helper never changes a rule by
itself.

**2.6 Calls are counted** (V10). The gateway keeps `gateway-calls.json` in the data folder
(mode 600): per server and tool a count and the time of the last call, no arguments, no results.
Written atomically after each call; a lost count in a race is acceptable (found data). A tool
row's hover text says "Called 12 times, last today 14:02". My call: counts only, no log.

Done for Part 2: strict mode on with two tools on, a third tool added to the cache, a new
session offers two tools; the third is refused when called; a tool turned off in a running
session is refused on its next call; all of this on the fake echo server in tests, and once by
hand in Claude Code, Codex and Cursor on a throwaway project (`docs/development.md`).

### Part 3. Complete management

Every action here is a change: preview, Apply with a backup, verify, Undo.

**3.1 Remove a plugin** (V4, C3). Claude Code: `claude plugin uninstall <id> -s <scope> --json`
(the command the install step already uses for Undo); Undo installs it again. Codex:
`codex plugin remove`; Undo adds it again. Cursor keeps installs in its database, so the cell
says "Remove it in Cursor: Customize → Plugins." A plugin row's Details gets "Remove from
<client>…" per client. A duplicate plugin's "Keep one…" opens that row with Remove in view.
Check both CLIs' current flags and write the date.

**3.2 Remove a skill** (V4). A skill folder in a client's own skills folder (user or project),
never inside a plugin cache: the change copies the folder into the change's backup folder,
removes it, and verifies it is gone; Undo copies it back when the target does not exist. A
duplicate skill's "Keep one…" becomes a real fix.

**3.3 Remove a server from the Kitden gateway** (V4). One change: the server entry, its global
rule and every project rule for it, each a step; Undo restores them all. The tool cache entry
stays (found data). The review says the server is then in no client, and that Undo brings it
back. A held server's Details also gets "Put back in <client>…", my call after the builder
check: the held entry translated into that client's format with the same translation as 3.4,
a Keychain reference (5.1) resolved to its value at Apply, and the review saying that a secret
is then written into that client's file. It does not remove the server from the gateway; 3.3
does that.

**3.4 Add an MCP server to another client** (V3, C2, R3). In the Library's MCP tab, a direct
server one client has (user scope, not via a gateway, not from a plugin, not in a project file)
gets "+ Add" in a found client's empty cell. Each adapter gains `add_server_step(name, entry)`
on its existing `_add_entry`, translating the entry to that client's format (type, url,
headers, command, args, env); the review shows the translated entry with secrets hidden. A
`${VAR}` reference stays a reference where the target client supports one, else the add is
refused with "Cursor cannot read `${TOKEN}` from your shell; put the value in." A literal secret
is copied, and the review says "This makes a second copy of a secret in <file>." Project
entries are refused: "It is already per project; copy the file into the project instead." My
call: user scope only.

**3.5 Align a project across clients** (V5, P3, C10). In a project view the Library's head gets
"Add missing…": a review that lists every plugin, skill and MCP server that one found client
loads for this project and another compatible client lacks, each with a checkbox (all on),
grouped by client, built from the same steps as the single adds (3.4, the existing plugin and
skill adds, 3.6 when a project place exists). Apply is one change. Items with the same name but a
different source are listed under "Not the same; not touched" (P3). Nothing is overwritten.

**3.6 Add into one project** (F1, owner's "move into a project"). When a project is picked, a
"+ Add" that can go to a project place offers two choices, like the move choice: "Add to this
project…" (primary) and "Add for all projects…". Project places, to be re-checked against each
client's docs with the date: a skill folder in `<project>/.claude/skills` (Claude Code),
`<project>/.agents/skills` (Codex, and Cursor with third-party folders on), `<project>/.cursor/skills`
(Cursor); a Claude Code plugin with `claude plugin install -s project`. Cursor's "Add to Project"
and Codex's per-project plugins have no file Kitden may write; the cell says where to do it. My
call: skills and Claude Code plugins only; MCP servers stay user scope (project MCP files belong
to the project's own repository).

Done for Part 3: each action has a unit test on a sandbox home with Undo, and a real-client
check in `docs/development.md`.

### Part 4. Fast to open, and measured

**4.1 Versions in the background** (V13, C1). `detect()` no longer runs `--version` during a
scan. The Claude Desktop Code tab keeps its version from the folder names under its bundled
`claude-code` folder: no command runs for it, so it stays as it is. It reads `versions.json` in the data folder (mode 600): per client the binary's path, its
modification time and the version. A missing or stale entry (path or mtime changed) is read by a
background task after the first scan, with the same 20-second timeout, and the page gets an
event so the Clients card updates. The version always comes from the binary Kitden would run
(`version_command`), never from an app bundle (C1). `kitden scan` keeps reading it directly.

**4.2 Two numbers, measured** (P10, C9). `scripts/measure-start.py` builds a sandbox home with
the test helpers, adds 40 MCP servers, 10 plugins and 20 skills across the three clients and one
slow source (a fake `codex plugin list` that takes 10 seconds), starts the page, and prints two
numbers from two runs: the time to the first usable answer (`/api/overview`) with the slow
source taking 10 seconds, and the time to complete data (`partial` false) with the slow source
answering at once. Budgets, my call: first usable ≤ 2 s even with the slow source, complete
≤ 5 s without it, excluding `uvx` cold start. The numbers go into `docs/development.md` with
the date.

**4.3 The page shows what is still loading**: the start line and the "still reading" note stay;
the measurement checks they appear for the slow source.

### Part 5. Secrets have a lifecycle

**5.1 Gateway secrets in the Keychain** (V14, F7, P7, C6). When a server moves into the gateway,
each env value and header value that `redact` would hide goes into the macOS Keychain
(`security add-generic-password -s kitden -a <server>/<key>`), and `gateway.json` keeps
`{"keychain": "<server>/<key>"}` in its place. The proxy resolves references when it starts
that server. The review says "The token goes to your Keychain; the settings file keeps a
reference." Undo of the move removes the Keychain item. A held server with plain values gets
"Move secrets to the Keychain…" in Details; no automatic migration, my call. Backups of
`gateway.json` then hold no secrets. The value that goes to the Keychain lives in memory between
preview and Apply; the change record keeps only the reference, and a recorded command is
stored masked. The record still keeps what Undo needs, including a removed client entry's
original values, as today: it is as private as the client file (mode 600).

**5.2 Backups say when they hold a secret** (F7, C6). At backup time, `redact` on the original
bytes tells whether a secret is inside; the change record keeps the flag, and the Changes page
shows "The backup and record hold a secret" on that change. Retention stays 30 days or the newest 100; the
README says so in one line. My call: no new retention option.

**5.3 Logins in one place** (V8, roadmap Later). The page signs in to a remote server that
answers 401 with the MCP authorization flow (dynamic client registration where offered, the
browser opened on a `127.0.0.1` callback) when the move is applied, and keeps the tokens in the
Keychain under the server's name. The gateway process only refreshes, under a lock file in the
data folder so that two client sessions never refresh at once, and answers an error result
"Sign in to <server> again on the Kitden page." when a refresh fails; it never opens a browser. `local_move_steps` then no longer refuses OAuth servers; the
review says "Kitden will open your browser to sign in to <server>." Clients that reached that
server with their own OAuth keep nothing. A throwaway spike against one real OAuth server comes
first, because the MCP authorization spec changes; the spike's findings go into the plan with the
date. The server is the owner's choice (open decisions below); the default is the GitHub remote
MCP server, which documents OAuth. The share of remote servers that need OAuth is unknown (C7); this part removes the
question.

### Part 6. The whole picture: instructions

**6.1 An Instructions tab** (F9, V1, P9). A new `ItemKind` for instruction files, read-only.
Per client, global and per project, re-checked against each client's docs with the date:
Claude Code `~/.claude/CLAUDE.md`, `<project>/CLAUDE.md`, `<project>/.claude/CLAUDE.md`,
`CLAUDE.local.md`, `~/.claude/commands/*.md`, `<project>/.claude/commands/*.md`,
`~/.claude/agents/*.md`, `<project>/.claude/agents/*.md`; Codex `~/.codex/AGENTS.md` and
`<project>/AGENTS.md`; Cursor `<project>/.cursor/rules/*.mdc`, `<project>/.cursorrules`, and
`AGENTS.md` if Cursor reads it. One row per file with a quiet category word (instructions,
command, agent); a cell says "Loads" or "—"; Details shows the path and the first lines, passed
through `redact`. No actions on this kind for now. The Library's search includes them.

**6.2 Weight** (V2). The gateway card's server rows show "12 tools"; a direct server's Details
shows the count when its tools are known (after a move) and nothing otherwise. My call: no
"ask a direct server for its tools" button.

### Part 7. Linux and Windows

**7.1** Each client's paths per OS, from its docs with the date; the data folder
(`$XDG_DATA_HOME/kitden` or `~/.local/share/kitden`; `%APPDATA%\kitden`); file modes where the
OS has them; the version commands; the install scripts; app detection. The Keychain (5.1) gets
an OS twin: `secret-tool` on Linux where present, else a mode-600 file with a plain warning. My
call. Linux first; the CI matrix grows with each OS. Contract tests stay macOS unless a client's
CLI is present.

**7.2 Windows**, its own part after Linux: `page.py` locks with `fcntl`, so Windows gets
`msvcrt.locking`; file modes are no-ops there, and the docs say so; `start_new_session` becomes
a new process group; paths and the data folder as above; the Keychain's twin is the file with
the plain warning, because the Credential Manager is not scriptable for values. My call on the
fallback.

### Part 8. Docs, roadmap, releases, checks

- Each part updates `README.md`, `ROADMAP.md` and the release notes file in the same change
  (`AGENTS.md`). The roadmap's "Under review" section goes once this design is in the roadmap.
- `docs/development.md`'s hand check grows: strict mode, a refusal in an open session, remove,
  add a server to another client, add into a project, Keychain, OAuth sign-in.
- Housekeeping: `docs/research/` and `docs/superpowers/` are committed; `.impeccable/` and
  `.specify/` go into `.gitignore`. My call.

## Order

Parts in the order above: 1, 2, 3, 4, 5, 6, 7, with 8 inside each. Reasons: 1 is small and
removes false claims; 2 is the owner's main scenario on a sound footing; 3 completes management;
4 is measurement plus one fix; 5.1 is the prerequisite of 5.3; 6 and 7 widen scope. Whether 5
comes before 3 and 4 is an open decision below. Each part ships on its own and is a release
candidate on its own.

## Decisions the owner made (2026-10-21)

1. **Order:** Part 5 (Keychain and logins) comes after Part 4, as above.
2. **The spike's OAuth server** (5.3): the owner left it to the builder; it is the GitHub remote
   MCP server, which documents OAuth.
3. **An unknown folder** (2.4): the global rules apply, and the page says so.

The owner approved this design on 2026-10-21; the plan is
`docs/superpowers/plans/2026-10-21-review-follow-up.md`.

## Left to the builder

- Exact wording of new page text (tested in `tests/unit/test_page_words.py` and
  `tests/frontend/`), within `docs/design.md`.
- File layout of new modules, fixture files under `tests/fixtures`, and test names.
- The final verb list for `may write` and the hover texts.
- How the background version task and the measurement script are wired, as long as the
  behavior above holds.
- Whether `list_changed` (2.3) is worth keeping after a real-client check.

## Acceptance, per part

| Part | On a sandbox home | In real clients (throwaway project) |
| --- | --- | --- |
| 1 | Overview shows the Kitden gateway with held servers; project view shows the scope line; `kitden` makes no cross-client note; docs tests for the changed words | — |
| 2 | Strict mode keeps new tools out; a tool turned off is refused on the next call; hints come from annotations, then names; batch review lists only writing tools; counts increase | New session sees only allowed tools; same session gets the refusal; Undo restores |
| 3 | Remove plugin, skill, gateway server with Undo; add a server to another client with a reference kept or refused; Add missing builds one change; Add to this project writes the project place | Each action once per client, with a new session seeing the result |
| 4 | First scan runs no version command; versions arrive by event; the script prints both numbers under budget | — |
| 5 | Move writes a Keychain item and a reference; proxy resolves it; backups flagged; OAuth spike notes with the date | Sign in once, the server moves in, tools work |
| 6 | Instructions rows per client and project; Details redacted | — |
| 7.1 | Tests pass on Linux CI; paths per OS checked with dates | A Linux machine opens the page |
| 7.2 | Tests pass on Windows CI; the page lock and process start work there | A Windows machine opens the page |

## Every recommendation, and where it lives

| Source | Recommendation | Here |
| --- | --- | --- |
| V1, F9, P9 | Instruction files in the inventory | 6.1 |
| V2 | Sense of weight (tool counts) | 6.2 |
| V3, C2, R3 | Copy an MCP server to another client | 3.4 |
| V4, C3 | Remove a plugin, a skill, a gateway server | 3.1–3.3 |
| V5, P3, C10 | Align a project across clients | 3.5 |
| V6, C4, R1 | Read-only as a helper, not a guarantee | 2.5, 1.5 |
| V7, F8, R1 | Overview knows the Kitden gateway | 1.1 |
| V8, C7 | OAuth servers into the gateway | 5.3 |
| V9, P11 | Entries that stay direct, with reasons | unchanged; 5.3 removes the OAuth reason |
| V10 | A record of calls (counts, no arguments) | 2.6 |
| V11, C3 | Notes noise | 1.3 |
| V12 | Gateway page length | 1.6 |
| V13, C1, C11 | Version commands at start; version source identity | 4.1 |
| V14, F7, P7, C6 | Keychain; secret lifecycle; backups | 5.1, 5.2 |
| V15 | Say that the move review asks the server once | 1.4 |
| V17 | Linux and Windows | 7.1 |
| V18, C12 | Untracked folders; roadmap "Under review" | Part 8 |
| V19, C11 | Name heuristic as a guess; versions not from bundles | 2.5, 4.1 |
| F1, C8, R1 | Scope before the click; project-scoped install | 1.2, 3.6 |
| F2, C7 | Saved settings are not live context | Non-goals; 1.4 |
| F3, P3 | Name is not equivalence; no overwriting | 3.5 |
| F4, P4, C5 | New tools off in strict mode | 2.1, 2.2 |
| F5, P5, C5 | Refuse current denials in open sessions | 2.3 |
| F6, P6, C5 | Unknown project policy | 2.4 |
| P7, R5 | What the gateway governs; local is not offline; no sandboxing | 1.5, Non-goals |
| P10, C9 | Measure first usable and complete data | 4.2, 4.3 |
| P12, C4 | Annotations are untrusted; service-side read-only token | 2.5, 1.5 |
| P13, R2 | Real-client checks | Part 8, Acceptance |
| C7 | One-time link; MCP server wording; promise wording; first-move nuance | 1.4 |
| C10 | Priorities | Order |
