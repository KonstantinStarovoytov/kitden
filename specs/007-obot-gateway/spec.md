# Feature 007: Obot as a gateway in Kitden

Date: 2026-10-19. Status: **proposal**, research and specification only; no code yet.
Research: [where to run Obot](../../docs/research/obot-deploy-2026-10-19.md),
[gateway APIs](../../docs/research/gateway-api-2026-10-19.md), [calls and their stability](research.md).
Feature 006 did the same for MetaMCP: [spec](../006-gateway-inside/spec.md).

## Problem

Kitden connects clients to any gateway URL, but it only *manages* MetaMCP. The owner is
considering Obot (active releases, a real REST API with keys, a team edition). Today an Obot
gateway on the Gateway page is a bare address: no list of what it holds, no move.

## Scope in two steps

| Step | What | When |
| --- | --- | --- |
| **A — read-only** | Register an Obot gateway, see what it holds, connect clients to it, open Obot | This feature |
| **B — move** | "Move into the gateway…" and "Move all N…" with review, Apply, verify, Undo | Later, only if Obot's API allows it without admin-only or unstable surfaces (see [research.md](research.md), R4) |

Step B is written here so the owner can judge the whole, but it is **not confirmed** and gets
its own tasks only after a re-check against the Obot release of that day.

## User stories

### US1 — Register an Obot gateway (Step A, P1)

The gateway form takes the Obot connection address (`https://host/mcp-connect/<id>`), the
optional interface link, and the **name** of the environment variable that holds an Obot API
key. The key itself never enters the form, the settings file, the page or the log. A saved
Obot gateway appears on the Gateway page with the name "Obot".

**Test**: saving a gateway with a key variable name stores the name; a value that looks like a
key is refused with one plain sentence.

### US2 — See what the gateway holds (Step A, P1)

The gateway card shows "In the gateway · N" with the names of the servers Obot exposes on that
connection address. Details opens the side panel with the server's kind and, when Obot gives
it, its address. When Obot cannot be reached, the key is missing or refused, or the answer has
an unexpected shape, the card says so in one line and the rest of the page keeps working.

**Test**: with a fake Obot that exposes two servers on the stored address, the page shows both
names; with the fake stopped, the card shows the one-line note.

### US3 — Connect clients to Obot (Step A, P1)

"Connect" works as for any gateway today: one entry per client pointing at the connection
address. Clients sign in with their own OAuth login (the owner's choice); the key variable is
for Kitden only and never reaches a client file.

**Test**: the existing connect round-trip tests pass with an Obot address.

### US4 — Open Obot (Step A, P2)

"Open Obot ↗" is a small secondary link on the gateway card, as "Open MetaMCP ↗" is today.
Everything Kitden does not do (tools on and off, access, catalog) happens there.

### US5 — Move one server into Obot (Step B, later, P2)

Each row in "Can move into the gateway" has "Move into the gateway…". The review lists the
gateway step first (make the server known to Obot and add it to the connection the clients use;
name and address shown, secrets hidden), then one step per client file. Apply, verify, Undo
and the Changes record follow feature 006. A server whose address is `localhost`, `127.0.0.1`,
a private or link-local address is refused before the review: "Obot cannot reach servers on
this computer. Keep the direct entry or set up an Obot tunnel."

### US6 — Move all (Step B, later, P3)

"Move all N…" on the group: one review, one Apply, one Undo. Rows that would be refused are
listed in the review as skipped, with the reason.

## Edge cases

| Case | Behaviour |
| --- | --- |
| The key variable is not set when the page starts | Card: "Set KEY_VAR before starting Kitden"; connect still works |
| The key has no `api` scope or the role does not allow the call | Card: "Obot refused the key (403)"; nothing else changes |
| The connection address is not an Obot connection address | Registration refused: "An Obot address looks like https://host/mcp-connect/<id>" |
| Obot answers in an unexpected shape or version | Card note; Step B preview refused; nothing written |
| Step B: the gateway step succeeds but a file step fails | The server is removed from Obot again, files restored, state `restored` |
| Step B: Undo after the server was removed from Obot by hand | Undo continues with the files and says the gateway side was already gone |
| Step B: the direct entry references `${VAR}` or has a header with a variable | Refused: Obot cannot read the shell's variables |
| Step B: the connection is a shared vMCP the key's user may not edit | Refused: "Only an Obot administrator can change this connection" |

## Requirements

- FR-001: A gateway record for Obot holds the connection address, the optional interface link,
  the client sign-in kind and the key variable's **name**; never a key.
- FR-002: The Gateway page shows, per Obot gateway, the names of the servers exposed on the
  stored address; kind and address stay behind Details.
- FR-003: Clients connect to an Obot gateway through the existing connect flow; a key reaches
  a client file only as a variable reference.
- FR-004: A gateway that cannot be reached, refuses the key, or answers unexpectedly never
  blocks the rest of the page and never writes anything.
- FR-005: Secrets (keys, header values, tokens) never appear on the page, in a diff, in the log
  or in error text.
- FR-006: Every Obot call Kitden makes is listed in [research.md](research.md) with the Obot
  version it was checked against, its documented stability and the role it needs.
- FR-007 (Step B): "Move into the gateway…" and "Move all N…" use the feature 006 contract:
  one review, gateway step first, verify by reading the list back, Undo removes the server and
  restores every file, the change is recorded on the Changes page.
- FR-008 (Step B): servers on `localhost`, `127.0.0.1`, `::1`, private or link-local addresses
  are refused before the review with a plain message that names the tunnel alternative.
- FR-009: Pages show name, client and action; paths, addresses and commands stay behind
  Details ([DESIGN.md](../../DESIGN.md), [motion](../../docs/MOTION_DESIGN.md)); nothing new
  animates.

## Success criteria

- SC-001 (Step A): on a fixture home with a fake Obot, the Gateway page shows the held names,
  the stopped-fake note, and connects every found client with one Apply and one Undo; the
  fixture files are back byte for byte.
- SC-002 (Step A): unit tests cover list, missing variable, 401/403, unexpected shape and
  "no secret in any message"; no test touches the network or the owner's files.
- SC-003 (Step A): the page passes the browser check in both themes and at 375 px, and the
  wording test; the key never appears in any response body.
- SC-004 (Step B): the feature 006 success criteria, run against the fake Obot.

## Assumptions

- The owner runs Obot where the research proposes: Docker on the Mac, bound to `127.0.0.1`,
  authentication on. A VPS works the same for Step A.
- Clients sign in to Obot with OAuth per client (owner's choice, 2026-10-19, GitHub as the
  provider). Kitden itself uses an API key with the `api` scope from the key variable; the key
  never reaches a client file.
- The key's user can read the vMCP behind the stored address (the user connects to it).

## Open question (owner)

Should Step B be built at all while MetaMCP is the owner's gateway? It is roughly the size of
feature 006 again.

Answered 2026-10-19: clients sign in with OAuth per client, not with the key.

## Exclusions

Running or installing Obot. Tunnels, catalogs, access policies, profiles, tools on and off:
Obot's own interface. Local (stdio) and plugin servers. Editing Obot's settings. MetaMCP stays
as in feature 006.
