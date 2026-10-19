# Research: Obot calls Kitden would rely on

Reviewed **2026-10-19** against Obot v0.26.3 (router and types at that tag) and the versioned
docs (v0.26.0). Status: R1–R3 are proposals for Step A; R4 is the gate for Step B.
Where to run Obot: [docs/research/obot-deploy-2026-10-19.md](../../docs/research/obot-deploy-2026-10-19.md).

## R1. Sign-in: one API key in an environment variable

- **Decision**: the record keeps `key_env_var`; the key is made with
  `obot login --url <obot> --scope api --print-token` and set in the shell before Kitden
  starts. `--scope` replaces the defaults, so `api` must be listed.
- **Why**: documented flow; the key is shown once and is checked with `/api/me`; the `api`
  scope opens "Obot API endpoints allowed by your user role", so a Standard User's key reads
  only what that user can see. Same shape as `GatewayAuth.ENV_KEY` today.
- **Live check (2026-10-19, Obot v0.26.3 in Docker on the Mac, GitHub sign-in)**: the web
  form "Agent Auth Scopes → Create Auth Scope" and `obot --help` offer only MCP servers, LLM,
  skills and device scans; `api` is a hidden scope that `obot login` still accepts, and the
  `ok1-` key it gives works. The CLI comes from `brew install obot-platform/tap/obot`. Kitden's
  docs must warn: **do not run `obot setup`**, it writes Cursor and Claude Code configs
  directly, with no preview or backup.
- **Alternatives**: email and password (rejected: Obot's Local provider is a browser flow, not a
  documented API; MetaMCP needed it because it has nothing else).
- **Source**: [agent auth scopes](https://docs.obot.ai/functionality/agent-auth-scopes/).

## R2. What the gateway holds: the vMCP behind the stored address

- **Decision**: parse `<id>` from `https://host/mcp-connect/<id>`, call `GET /api/vmcps/<id>`,
  show `components[].name`; kind from `catalogEntry.manifest.runtime`, address from
  `remoteConfig.fixedURL` when present.
- **Why**: the connection address *is* a vMCP; its components are what the clients get. One
  call, the same route the Obot UI uses. `GET /api/mcp-servers` (our 2026-10-19 note) was
  removed in v0.26.2 and is back only as "Legacy … manage connections through vMCPs"; not a
  base to build on.
- **Alternatives**: `GET /api/all-mcps/entries` (everything the user may add, not what the
  connection exposes); the MCP Registry API `/v0.1/servers` (servers, not vMCPs; a separate
  auth switch).
- **Sources**: [virtual MCPs](https://docs.obot.ai/functionality/virtual-mcps/),
  [router.go at v0.26.3](https://github.com/obot-platform/obot/blob/v0.26.3/pkg/api/router/router.go),
  [vmcp.go](https://github.com/obot-platform/obot/blob/main/apiclient/types/vmcp.go),
  [v0.26.2 notes](https://github.com/obot-platform/obot/releases/tag/v0.26.2).

## R3. Clients connect with OAuth

- **Decision (owner, 2026-10-19)**: clients use `oauth` (per-client browser login, as in the
  trial); `key_env_var` is for Kitden only. `env_key` stays possible for a key with the
  `all-mcp` scope but is not the default for Obot.
- **Source**: [agent auth scopes](https://docs.obot.ai/functionality/agent-auth-scopes/)
  ("Include the API key in the Authorization header when connecting to MCP servers"),
  [gateway trial](../../docs/research/gateway-trial-2026-10-16.md) (Codex OAuth).

## R4. Gate for Step B: can a move be done without admin-only, unstable surfaces?

What a move needs today, and what each call costs:

| Need | Call (v0.26.3) | Documented? | Role | Edition |
| --- | --- | --- | --- | --- |
| Make a remote server known | `POST /api/mcp-catalogs/{catalog}/entries` with `{manifest: {name, runtime: "remote", remoteConfig: {fixedURL}}}` | route only (no reference docs) | **Admin** (router comment "admin only") | any |
| Same, personal | `POST /api/workspaces/{ws}/entries` | route only | Power User or above | any |
| Put it on the connection | `PUT /api/vmcps/{id}` with `components` plus `{name, mcpCatalogID, mcpServerCatalogEntryID}` | route only | the vMCP's owner; shared vMCPs: administrators | any |
| Headers for the server | `manifest.config` (the old `remoteConfig.headers` is "Deprecated: retained only to migrate") | type only | — | — |
| Remove | `PUT /api/vmcps/{id}` without it, then `DELETE …/entries/{id}` | route only | as above | any |
| Reach a server on the Mac | blocked by `OBOT_SERVER_DISALLOW_*` unless turned off, or an MCP tunnel (Admin creates) | yes | Admin | any |

**Verdict today: not met.** The write routes have no reference documentation, v0.26.2 removed
a whole family of them without a deprecation period, the catalog route is admin-only, and the
header mechanism changed in the same release. Step B stays conditional: re-check this table
against the release of the day before writing its tasks. Minimum to pass: a documented way for
a Power User to add a remote server to their own vMCP, and a stable `PUT /api/vmcps` shape.

## Calls Kitden relies on (Step A)

| Call | Why | Documented? | Role | Edition |
| --- | --- | --- | --- | --- |
| `GET /api/me` | check the key | yes | any | any (free Obot, up to 100 users) |
| `GET /api/vmcps/{id}` | what the connection holds | route and types; the UI uses it | a user the vMCP's profile grants | any |
| `https://host/mcp-connect/{id}` | the clients' endpoint | yes | any granted user | any |

Nothing in Step A needs Community registration or an Enterprise licence.

Live check on 2026-10-19 (v0.26.3, Owner's key with the `api` scope): `GET /api/me` → 200
(`id`, `username`, `role`, `effectiveRole`, `groups`); `GET /api/mcp-servers` → 200
`{items: []}`; `GET /api/mcp-server-instances` → 200; `GET /api/mcp-catalogs` → 200 with one
catalog `default` holding 208 entries. `GET /api/vmcps/{id}` was not tried: the instance held
no vMCP yet. T003 must check it first.
