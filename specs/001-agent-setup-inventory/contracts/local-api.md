# Contract: local page API

The page and its API run on `127.0.0.1` only. This contract defines the interface between the
browser page and the local component that reads and writes client files, so a later team version
can reuse the component (constitution VI).

## Security rules for every request ([research R6](../research.md#r6-local-web-page-security))

- `Host` must be `127.0.0.1:<port>` or `localhost:<port>`; otherwise 403.
- A valid session cookie is required (issued after the one-time start URL token); otherwise 401.
- State-changing requests (`POST`) also require: exact same-origin `Origin`; `Sec-Fetch-Site:
  same-origin` when the header is present; and the header `X-Tool-Request: 1`. Otherwise 403.
- No CORS headers are ever sent. `GET` never changes state.
- Responses never contain secret values; secrets appear as `[secret]` or as `${VAR}` references.

## Read endpoints

| Method and path | Returns |
| --- | --- |
| `GET /api/clients` | Clients with status, version, `version_supported`, write capabilities |
| `GET /api/items?client=&kind=&scope=&project=` | Items with source, scope, enabled state, allowed actions |
| `GET /api/projects` | Projects with `known_by`, `exists`, trust |
| `GET /api/projects/{id}/effective` | Effective views per client for one project, with shadowed pairs |
| `GET /api/findings?project=` | Findings with severity and explanation |
| `GET /api/changes` | Change log entries (redacted), newest first |
| `GET /api/gateways` | Registered gateways |
| `GET /api/commands?item=&action=` | Without `action`: the show-only commands for a plugin or marketplace (install, update, uninstall, move, add a marketplace), with a note where there is no command (FR-029). `action=gateway.login`: the login step for an OAuth gateway entry |

## Change endpoints

| Method and path | Body | Result |
| --- | --- | --- |
| `POST /api/changes/preview` | `{action, targets, params}` | A Change in state `previewed` with masked diffs, mechanisms, restart notices, shared-file warning; nothing written |
| `POST /api/changes/{id}/apply` | none | Change in `verified`, `stale` (409) or `restored` (500 with reason) |
| `POST /api/changes/{id}/cancel` | none | Change in `cancelled` |
| `POST /api/changes/{id}/undo` | none | Change in `undone`, or `undo_blocked` (409) with the reason |
| `POST /api/rescan` | none | Starts a rescan; returns when finished |
| `POST /api/gateways` | `{url, ui_url?, auth, key_env_var?}` | Registers a gateway (no secret values accepted) |

Rules:

- `apply` fails with 409 if any target file's hash differs from the preview (FR-016).
- An action not in the item's `actions` list returns 422 (spike-gated writes stay unavailable,
  FR-028).
- Every applied, failed or undone change is appended to the redacted change log (FR-022).

## Events

`GET /api/events` (server-sent events, same cookie and Origin checks): `rescan_started`,
`rescan_finished`, `files_changed`, `change_state`. Events carry ids only, never item contents.
