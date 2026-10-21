# Kitden gateway: MCP tools per project, on this Mac

Date: 2026-10-21. Part 1 of 3 (2: one place for logins, 3: skills per project).

## Why

Kitden is a complete product: a person downloads it and manages everything on their Mac. Today
a gateway means Obot or MetaMCP: a separate service to deploy and keep running, and Obot cannot
hold local (stdio) servers. The owner wants to choose a project and turn single MCP tools on or
off for that project, for all clients, from one place, including local servers.

The clients cannot do this alone (checked 2026-10-21; reports in the session's
`gateway-research/`):

| | Claude Code | Codex | Cursor |
|---|---|---|---|
| Turn one tool off in one project | yes (`deny` rule in project settings) | yes (`disabled_tools` in a trusted project's `.codex/config.toml`) | no: tool toggles of a user server are global |
| Tells a server its project | `CLAUDE_PROJECT_DIR` env, MCP roots | only the start folder; env is cleared | IDE: roots, `WORKSPACE_FOLDER_PATHS` (undocumented); CLI: start folder |

So one Kitden gateway that knows the project gives the same control in every client.

## Goals

- A local gateway, `kitden gateway`: one stdio entry in each client, set up by Kitden through
  preview → Apply with a backup → verify → Undo.
- It holds local servers (command, args, env) and remote servers (URL, headers) and shows their
  tools to the client as one server.
- It finds the project of the client session and shows only the tools turned on for it.
- On the page: pick a project, open a server, turn its tools on or off for that project or for
  all projects. Every change has a review and Undo, like any other Kitden change.
- No deploy, no Docker, no account. Obot and MetaMCP stay supported for teams.

## Non-goals (this part)

- Remote servers that need OAuth sign-in. They stay direct in the clients; Kitden says why. That
  is part 2.
- Skills per project (part 3).
- Prompts and resources of the servers: part 1 passes tools only.
- Reaching the gateway from another computer; teams; Windows and Linux specifics.

## Anti-goals

- A client that cannot start because a server is slow or broken.
- Secrets on the page, in logs or in the review.
- A change to tools that the review does not show, or that cannot be undone.

## How it works

### The entry in each client

The gateway is the `kitden mcp` server that clients already know (the read-only "show my setup"
entry named `kitden`, also shipped in the kitden plugin). It keeps its read-only tools and, once
servers are moved in, also offers their tools. So there is one entry per client, no new name and
nothing to migrate; Kitden's existing "add / update the setup server" review sets it up where it
is missing. It reads Kitden's data folder, so it needs nothing but HOME (Codex clears the rest
of the env).

### Finding the project

The gateway decides once, at start, in this order:

1. `CLAUDE_PROJECT_DIR` (Claude Code).
2. The client's MCP roots (Claude Code, Cursor IDE): the first root.
3. `WORKSPACE_FOLDER_PATHS` (Cursor IDE), the first path.
4. Its start folder (Codex, Cursor CLI), unless it is the home folder or `/`.

A git worktree maps to its main checkout. A folder that is not one of Kitden's known projects
(for example a Codex chat folder) gets the global set. Codex keeps a tool list for up to 30
minutes and ignores "list changed", so the set is fixed for the session; a change applies to new
sessions, and the review says to start one.

### Servers in the gateway

A server moves into the gateway with Kitden's existing "Move into the gateway" flow: its entry
is added to the gateway's own settings and removed from each client, in one review with Undo.
The gateway page shows the Kitden gateway ("On this Mac") beside any remote gateway.

The gateway's settings are one JSON file in Kitden's data folder, readable only by the user
(mode 600): servers and rules. Env values that are written in a client's file move there as they
are; the page and the review never show them.

What can move in part 1:

- Entries at user level, and Claude Code's local scope (one user, one project). A local-scope
  server becomes "on only in its project".
- Not entries in a project's own files (`.mcp.json`, `.cursor/mcp.json`, `.codex/config.toml`):
  they are already per project and may be shared through git. Kitden says they stay.
- Not entries whose values come from elsewhere: `${VAR}` / `${env:VAR}`, `envFile`, Codex
  `env_vars`, `bearer_token_env_var`, `env_http_headers`, header helpers. Under Codex the gateway
  runs with almost no env, so these would break; copying the values would make a new copy of a
  secret. Kitden says why they stay; part 2 brings secrets in the keychain. (On this Mac on
  2026-10-21 only one plugin server used such a reference.)
- Project placeholders in args (`${workspaceFolder}`, `${CLAUDE_PROJECT_DIR}`) are filled with
  the project the gateway found.

Each local server gets the same env in every client: HOME, USER, LANG, the PATH Kitden saved
from the user's shell when the server moved, and the server's own env.

### Tools

- Kitden asks each server for its tool list when it is added and on Rescan, and keeps that list
  in the settings, so the gateway answers `tools/list` at once and starts a local server only
  when one of its tools is first called. A server whose list is not known yet is started at
  gateway start, within the clients' start time (Claude Code 30 s; set Codex's timeouts in the
  entry).
- Tool names stay as the server gives them; on a clash the later server's tool gets
  `<server>_` in front. Names are kept within Cursor's 60 characters for server plus tool.
- A server that fails to start or answer: its tools return a plain error; the gateway and the
  other servers keep working; the page shows the problem on the next Rescan.

### Rules

For each server: on or off, and a list of tools turned off. Global rules apply everywhere; a
project's rules change them for that project only. A tool is offered when its server is on and
the tool is not off, after the project's rules. A tool a server adds later is on, as it would be
without the gateway.

Moving a server carries over the rules Kitden can read, in the same review: Codex's `enabled`,
`enabled_tools`, `disabled_tools` of the moved entry, and Claude Code `deny` rules for that
server in user settings and in the settings of Kitden's known projects. Cursor's own tool
switches live in its database and do not carry over; the review says so for each Cursor client.

The list of each server's tools is found data, not a setting: Rescan and the gateway write it to
a separate cache file, outside the review. Only the settings file (servers and rules) changes
through review and Undo.

### On the page

- Library, MCP servers tab: servers in the gateway show "Via Kitden gateway" in each connected
  client.
- A server's Details lists its tools with a switch each. With Global picked the switches are the
  global rules; with a project picked they are that project's, and a tool that differs from
  global says so.
- Each switch opens the review: what changes, for which project, "applies to new sessions".
  Apply writes the gateway settings with a backup; Undo puts them back.

## Constraints

- Every change: preview → Apply with a backup → verify → Undo, also for the gateway settings.
- Main pages: name, client, action. Commands, paths and env stay in Details.
- Built on the MCP Python SDK Kitden already uses for `kitden mcp`; no new service.
- Tests use sandbox homes and fake servers; one manual check per client on a test project
  before release.
- docs/design.md, README and ROADMAP updated with the feature.

## Calls I made

- The gateway is the existing `kitden mcp` entry, not a second entry.
- One gateway process per client session (stdio), no shared background process. Simple; each
  session starts its own local servers, as it does today. A shared process can come later.
- The project is decided once per session.
- Tools only in part 1.
- OAuth servers, project-file servers and servers with env references stay direct in part 1.
- New tools of a server are on; tool lists live in a cache file outside the review.
- Moving carries over Codex and Claude Code tool rules; Cursor's switches are only named in the
  review.

## Left to the builder

- The settings file's exact shape and how it is edited (the engine's JSON edits).
- How the gateway entry and "Move into the gateway" reuse today's gateway code (`gateways.py`,
  `changes/actions.py`), and how the Kitden gateway shows on the Gateway page.
- Timeouts and the log file for the gateway.
