# Data model: Kitden name and one-command page

Additions to the [feature 001 data model](../001-agent-setup-inventory/data-model.md).

## Page record

The running page for one home folder. File: `<data folder>/page.json`, mode 0600.

| Field | Type | Notes |
| --- | --- | --- |
| `pid` | integer | Process id of the page |
| `port` | integer | Loopback port, 47800 or the next free one |
| `token` | string | Start link token; never printed to logs |
| `started` | ISO time | When the page started listening |
| `background` | boolean | Started by `kitden open`; only these stop when idle |

Lifecycle: written after the server listens and holds `page.lock`; removed on shutdown. A record
without a held lock is stale and is replaced.

## Data folder

`~/Library/Application Support/kitden` (mode 0700): `settings.json` (gateways), `changes/`,
`changes.log`, `page.lock`, `page.json`, `page.log`.

| State at start | Action |
| --- | --- |
| Only the old folder (`.../agentsetup`) | Copy it once to the new folder; rewrite backup paths inside `changes/*/change.json`; leave the old folder unchanged |
| Both folders | Use the new folder; print that the old one was left |
| Only the new folder, or neither | Nothing to do |
| Copy fails | Remove the partial copy, keep the old folder, explain, start with an empty new folder |

## Setup server state (per client)

What the Agents place shows for Claude Code, Codex and Cursor. Returned by `/api/setup-server`.

| Field | Values | Notes |
| --- | --- | --- |
| `client` | client id | |
| `state` | `added`, `old`, `missing`, `not_installed` | `old`: an old Kitden entry exists and no `kitden` entry |
| `item` | item id or null | The old entry, for the update action |
| `command_exists` | boolean or null | For `old`: whether the old command file still exists |

An old Kitden entry: user-level MCP item named `agentsetup`, command ending in `/agentsetup`,
args `["mcp"]` ([research R8](research.md#r8-old-entries-and-cookies)). If a `kitden` entry also
exists, the state is `added` and the update only removes the old entry.

## Change action `setup_server.update`

| Field | Value |
| --- | --- |
| Targets | `[{"item": <old entry id>}]`, one or more clients |
| Steps per client | 1) remove `agentsetup` (unless already absent); 2) add `kitden` (unless already present) |
| Same file | Both steps edit one settings file; the engine applies them in order ([R2](research.md#r2-several-steps-on-one-file-in-one-change)) |
| Undo | Restores the file to the state before Apply |
