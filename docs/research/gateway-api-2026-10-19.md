# Gateway APIs: can Kitden manage MetaMCP and Obot itself?

Reviewed **2026-10-19** from source code and vendor docs. Status: **research result** with one
proposal at the end. Feature: [006 gateway inside](../../specs/006-gateway-inside/spec.md).

## Why

On the Gateway page, "Open MetaMCP ↗" sends the person to another product. The owner wants to
move a direct MCP server into the gateway from Kitden: add it there, then remove the client entry.
This note checks what each gateway's API needs for list, add, remove and sign-in.

## MetaMCP v2.4.22

Source: [metatool-ai/metamcp at v2.4.22](https://github.com/metatool-ai/metamcp/tree/v2.4.22)
(the image on the owner's Mac; the trial note has the version). Checked files:
`apps/backend/src/index.ts`, `trpc.ts`, `routers/trpc.ts`, `trpc/*.impl.ts`,
`packages/trpc/src/routers/frontend/*.ts`, `packages/zod-types/src/*.zod.ts`, `auth.ts`.

**There is no public management API.** The web UI talks to a [tRPC](https://trpc.io/docs/rpc)
router at `/trpc/frontend/frontend.<group>.<procedure>`. Every procedure is `protectedProcedure`:
it needs a Better Auth **session cookie**. API keys (`sk_mt_…`) only open the MCP endpoints
(`/metamcp/<endpoint>/mcp`), never the management calls. Checked on the local instance: without
a cookie every call answers `401 UNAUTHORIZED`, with or without a Bearer key.

Sign-in is email and password: `POST /api/auth/sign-in/email` with `{email, password}` sets the
cookie `better-auth.session_token` ([Better Auth docs](https://www.better-auth.com/docs/authentication/email-password),
[cookies](https://www.better-auth.com/docs/concepts/cookies)); `POST /api/auth/sign-out` ends it.
Sessions last 7 days (`auth.ts`). With OIDC configured, email sign-in may be turned off by the
admin ("Basic email/password authentication is currently disabled").

Calls Kitden needs (queries are `GET …?input=<json>`, mutations `POST` with a JSON body; the
answer is `{"result": {"data": …}}`):

| Need | Procedure | Input | Answer |
| --- | --- | --- | --- |
| Which namespace the stored endpoint URL serves | `endpoints.list` | none | `[{uuid, name, namespace_uuid, …}]`; the endpoint name is the path segment after `/metamcp/` |
| Servers the gateway holds | `namespaces.get` | `{uuid}` | `{…, servers: [{uuid, name, type, url, status}]}` |
| Add a remote server | `mcpServers.create` | `{name, type: "STREAMABLE_HTTP" or "SSE", url, headers?, bearerToken?}` | `{success, data: {uuid, …}}` |
| Put it in the namespace | `namespaces.update` | `{uuid, name, description, mcpServerUuids: [all, plus the new one]}` | `{success}` |
| Remove it | `namespaces.update` without it, then `mcpServers.delete` | `{uuid}` | `{success}` |

Rules from the schemas: a server name matches `^[a-zA-Z0-9_-]+$` with no `__`; a URL server
needs a valid URL; `headers` is a string map. The local endpoint `local` runs with endpoint auth
off (`BOOTSTRAP_ENDPOINTS`), which does not change the management calls.

## Obot v0.26.x

Sources: [docs: CLI and APIs](https://docs.obot.ai/reference/cli-api), [agent authorization
scopes](https://docs.obot.ai/functionality/agent-auth-scopes), [add remote MCP servers](https://docs.obot.ai/mcp-gateway/register-remote),
`pkg/api/router/router.go` and `apiclient/types/mcpserver.go` on `main` (2026-10-19).

Obot has a REST API with API keys: `obot login --scope api` makes a key `ok1-…` that goes in
`Authorization: Bearer`; `GET /api/me` checks it. Listing is one call (`GET /api/mcp-servers`).
Adding a remote server is not: an **admin** creates a catalog entry
(`POST /api/mcp-catalogs/{catalog_id}/entries` with a manifest: `name`, `runtime: "remote"`,
`remoteConfig.fixedURL`, …), then the server is added to a vMCP that clients connect to, and
localhost or private addresses are blocked unless a tunnel is set up. The docs also say
"Internal Obot APIs are not all stable public integration surfaces."

## Comparison

| Question | MetaMCP 2.4.22 | Obot 0.26 |
| --- | --- | --- |
| Management API | tRPC used by its own web UI; not documented as public | REST; documented key flow, routes partly internal |
| Sign-in for management | Session cookie from email + password; API keys do not work | API key with the `api` scope in `Authorization: Bearer` |
| List servers | 2 calls (endpoint → namespace) | 1 call |
| Add a remote server | 2 calls (create, add to namespace) | Admin role, catalog entry, then vMCP; localhost blocked by default |
| Remove | 2 calls | Catalog entry delete plus vMCP edit |
| Secret handling | Headers and bearer token stored in Postgres (encryption not checked, trial note) | Needs an encryption provider; default `none` |
| Version churn | No release for 10 months; the tRPC names can change in any release | Active; routes marked as not all stable |

## Risks the owner should know

1. **MetaMCP has no stable API.** Kitden would call the same procedures the web UI calls. A new
   MetaMCP release can rename them without notice. Kitden must fail with a clear message and
   change nothing in the client files when a call does not answer as expected.
2. **A password, not a key.** Management needs the owner's MetaMCP email and password. Kitden
   stores only the email and the **name** of the environment variable that holds the password,
   signs in for one operation and signs out. The password never reaches a file, the log or the page.
3. **Secrets travel.** A direct entry with a header value (a token) is sent to the gateway over
   the local connection and stored there. Kitden never shows it. Entries that reference a
   variable (`${VAR}`) cannot be moved: the gateway cannot read the shell's variables.
4. **Obot is a later feature.** Its API needs an admin role, a catalog entry and a vMCP edit, and
   blocks localhost servers by default. That is three times the work for a product that was
   removed after the trial.

## Proposal (not a decision)

Build feature 006 for MetaMCP through its tRPC calls with a per-operation sign-in; verify every
write by reading the list back; record the version this was checked against; keep Obot for a
later feature with the same Kitden-side steps.
