# Where to run Obot

Reviewed **2026-10-19** against Obot's docs (versioned v0.26.0), the obot.ai site and the GitHub
releases. Status: **research result** with two proposals at the end. Earlier notes:
[gateway trial](gateway-trial-2026-10-16.md), [gateway APIs](gateway-api-2026-10-19.md).
Feature: [007 Obot gateway](../../specs/007-obot-gateway/spec.md).

Vendor documentation shows a documented feature, not runtime behaviour. The only setup we ran
ourselves is Docker on the owner's Mac: the trial of 2026-10-16 (image of 2026-10-08) and, on
2026-10-19, v0.26.3 bound to `127.0.0.1:8080` with authentication on, GitHub sign-in,
`OBOT_SERVER_HOSTNAME=http://localhost:8080` and the volume `kitden-obot-data`.

## What Obot is today

| Fact | Source |
| --- | --- |
| Latest release v0.26.3 (2026-10-08). v0.26.2 is the first release that upgrades from v0.25.x; v0.26.0 and v0.26.1 say "do not upgrade" | [releases](https://github.com/obot-platform/obot/releases) |
| vMCPs replace standalone and composite servers: one gateway endpoint `https://host/mcp-connect/{vmcp-id}` exposes one or more servers | [virtual MCPs](https://docs.obot.ai/functionality/virtual-mcps/) |
| v0.26.2 removed the server-management REST routes under `/api/mcp-servers`, `/api/mcp-server-instances` and `/api/mcp-catalogs/{id}/servers`; read routes are back at v0.26.3, marked "Legacy" in the router | [v0.26.2 notes](https://github.com/obot-platform/obot/releases/tag/v0.26.2), [router.go at v0.26.3](https://github.com/obot-platform/obot/blob/v0.26.3/pkg/api/router/router.go) |
| Three editions in one container image: **Obot** (free, up to 100 users and 100 devices), **Obot Community** (free after a one-time registration; adds Entra, Okta, JumpCloud, Auth0 sign-in), **Obot Enterprise** (licence; unlimited). The "Business" tag seen in the trial is a catalog label, not an edition | [editions](https://docs.obot.ai/enterprise/overview/), [obot.ai](https://obot.ai/) |
| **Obot Cloud**: hosted, dedicated environment per company on Google Kubernetes Engine, 14-day free trial, converts to a paid plan without rebuild. No price is published | [cloud trial](https://obot.ai/obot-cloud-trial/), [hosted platform post, 2026-05-13](https://obot.ai/blog/introducing-the-obot-mcp-gateway-hosted-platform/) |
| Credentials are encrypted only with a provider: `OBOT_SERVER_ENCRYPTION_PROVIDER` is `aws`, `gcp`, `azure`, `custom` or `none`; default `none` | [server configuration](https://docs.obot.ai/configuration/server-configuration/) |
| Remote servers on `localhost`, private or link-local addresses are blocked by default (`OBOT_SERVER_DISALLOW_LOCALHOST_MCP`, `…_PRIVATE_IPMCP`, `…_LINK_LOCAL_MCP`, all `true`). An MCP tunnel (`obot tunnel` on a machine that reaches the server; created by an Admin or Owner) is the documented way around it | [MCP servers](https://docs.obot.ai/functionality/mcp-servers/), [MCP tunnels](https://docs.obot.ai/functionality/mcp-tunnels/) |
| API keys: `obot login --url … --scope api` makes `ok1-<userId>-<keyId>-<secret>`, sent as `Authorization: Bearer`; `/api/me` checks it; the `api` scope opens "Obot API endpoints allowed by your user role"; `all-mcp` lets the same key connect to MCP servers | [agent auth scopes](https://docs.obot.ai/functionality/agent-auth-scopes/) |
| Roles: Owner, Admin (full management), Power User+ (share servers), Power User (personal servers), Standard User (connect only). Only administrators can create a vMCP other users consume | [user roles](https://docs.obot.ai/configuration/user-roles/), [virtual MCPs](https://docs.obot.ai/functionality/virtual-mcps/) |

## The four places

### (a) Docker on the owner's Mac

The official command ([Docker deployment](https://docs.obot.ai/installation/docker-deployment/)):

```sh
docker run -d \
  --name obot \
  -v obot-data:/data \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -p 8080:8080 \
  -e OBOT_SERVER_ENABLE_AUTHENTICATION=true \
  -e OBOT_BOOTSTRAP_TOKEN=your-bootstrap-token \
  ghcr.io/obot-platform/obot:latest
```

Two things to change for a laptop (proposal, not in the docs):

- `-p 127.0.0.1:8080:8080`. The official `-p 8080:8080` listens on every interface, so Obot
  would be open to the local network. With a different host port, set
  `OBOT_SERVER_HOSTNAME=localhost:<port>`, or sign-in redirects and connection URLs break.
- The Docker socket mount is required: Obot runs MCP servers as sibling containers and exits
  without it (trial, finding 5). The docs call this "equivalent to host-level access on that
  machine" and limit it to "development, evaluation, or single-tenant use where all such users
  are trusted". On a Mac with OrbStack or Docker Desktop the socket belongs to the Docker VM,
  so "host" means every container on it. Acceptable for one owner; not for shared use.

Other facts: the image holds its own Postgres ("not recommended for production"); first login is
the bootstrap token from the logs, then an auth provider (the built-in Local provider is enough);
with `OBOT_SERVER_ENCRYPTION_PROVIDER=none` the stored credentials are plain text on the volume;
`custom` takes a local key (`OBOT_SERVER_ENCRYPTION_KEY`; not tested). Servers on the Mac are
reached through `host.docker.internal`, which resolves to a private address, so
`OBOT_SERVER_DISALLOW_PRIVATE_IPMCP=false` is needed; the docs allow this "only when
intentionally needed". Not tested.

### (b) Docker on a small VPS

Same command on a Linux VPS, plus what the docs leave to the operator: an HTTPS reverse proxy
(Caddy or nginx; it must pass WebSocket upgrades on `/tunnel/connect` if tunnels are used),
`OBOT_SERVER_HOSTNAME=https://obot.example.com`, an auth provider (Local, GitHub or Google
OAuth with the public callback URL), a backup of the `obot-data` volume, and an encryption
provider other than `none`. Minimum size from the Kubernetes page: 2 CPU, 4 GB. The Docker
socket warning is the same: everyone with Power User or above can run code on that VPS.
Servers on the owner's Mac are unreachable unless an `obot tunnel` process runs on the Mac.

### (c) Kubernetes with Helm

Chart at [charts.obot.ai](https://charts.obot.ai/); "sane defaults for a test cluster"
([Kubernetes deployment](https://docs.obot.ai/installation/kubernetes-deployment/)). Production
needs an external PostgreSQL 17+, object storage or a persistent volume, an ingress with TLS, an
auth provider, and a KMS encryption provider (AWS, GCP or Azure). Upgrades across v0.26.2 need
scaling to one replica and `--server-side=false`. MCP servers run as pods (no Docker socket).
Nothing on the owner's Mac is reachable without a tunnel.

### (d) Obot Cloud

Form on obot.ai, 14 days free, a dedicated cluster per company, enterprise SSO included, no user
limit, no published price, no statement about what is stored or where beyond "Google Kubernetes
Engine". Every credential a server needs lives in Obot's cloud. Local servers need a tunnel from
the Mac. The trust page ([trust.obot.ai](https://trust.obot.ai/)) did not render for us; not
checked.

## Comparison

Cost figures are estimates by us, not vendor prices.

| | (a) Docker on the Mac | (b) Docker on a VPS | (c) Kubernetes + Helm | (d) Obot Cloud |
| --- | --- | --- | --- | --- |
| Cost | 0 | ~5–10 €/month for 2 CPU, 4 GB | managed cluster from ~70 €/month plus Postgres and KMS | free 14 days, then an unpublished price |
| Setup time | 15 minutes | 1–2 hours (proxy, HTTPS, auth, backup) | half a day or more | minutes, after the form is answered |
| Who can reach it | the owner only, with `127.0.0.1` | anyone with an account; the whole internet sees the sign-in page | same as (b) | same as (b), run by Obot |
| Where secrets live | Postgres on a Docker volume on the Mac; plain text unless `custom` encryption is set | Postgres on the VPS disk; plain text unless an encryption provider is set | external Postgres, encrypted with a cloud KMS | Obot's cloud, terms not published |
| Local MCP servers on the Mac reachable | yes, through `host.docker.internal` after turning the private-address block off (not tested) | only through `obot tunnel` on the Mac | only through a tunnel | only through a tunnel |
| Upgrade effort | `docker pull` and re-run; read the release notes (v0.26.2 changed the API) | same, plus a backup first | `helm upgrade` with the replica steps | none |
| Docker socket exposure | the Docker VM; one trusted user | the VPS; everyone at Power User or above | none | not our concern |

## Proposals

**Solo developer who also wants to test the Kitden integration: (a) Docker on the Mac.** Zero
cost, no public surface, the same image as every other edition, and the only place where the
owner's local MCP servers can be reached without a tunnel. Bind to `127.0.0.1`, keep auth on,
use the Local provider, set `OBOT_SERVER_HOSTNAME`, and turn the private-address block off only
for the one test that needs it. Keep MetaMCP on port 12008 until Step A of feature 007 works
against Obot; both can run at once.

**Small team: (b) Docker on a VPS**, one per team, with Caddy for HTTPS, the Local or GitHub
provider, an encryption provider, nightly volume backups, and only trusted people at Power User
or above. Kubernetes is more than a small team needs to operate. Obot Cloud is the fastest way
to see the product, but its price is not published and the team's credentials leave the
team's machines; use the 14-day trial to evaluate, not as the plan.

## The CLI on a Mac

`brew install obot-platform/tap/obot` (the page Obot's UI links to). `obot login --url … --scope
api --print-token` makes the key Kitden needs; `api` is not offered in the UI or the CLI help
but is accepted. **Do not run `obot setup`**: it writes Cursor and Claude Code configs directly,
with no preview or backup. Kitden's connect flow does that part with review and Undo.

## Open points for the owner

- Whether servers that run on the Mac should stay direct entries (the Load map already flags them)
  or be reached from Obot through `host.docker.internal`.
- Whether the team version is wanted in 2026; it decides between (a) and (b).
