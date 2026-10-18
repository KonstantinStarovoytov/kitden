# Contract: local API changes

Additions to the [feature 001 local API](../../001-agent-setup-inventory/contracts/local-api.md).
Same security rules: session cookie, Host and Origin checks, `X-Tool-Request` on writes.

## Session cookie

Name: `kitden_session_<port>`. One cookie per page, so pages on different ports keep their own
login.

## `GET /api/setup-server`

Setup server state per client ([data model](../data-model.md#setup-server-state-per-client)).

```json
[{"client": "codex", "state": "old", "item": "a1b2…", "command_exists": false}]
```

## `POST /api/changes/preview` with `setup_server.update`

```json
{"action": "setup_server.update", "targets": [{"item": "a1b2…"}], "params": {}}
```

Returns the usual change preview. 422 "Install the tool first: uv tool install <this folder>" when
the `kitden` command is not installed; 422 "Choose an old Kitden entry." when a target is not an old
entry.

## Idle tracking

`GET /api/events` connections count as open tabs. Nothing else changes in the API.
