# Feature 006: Manage the gateway from inside Kitden

Date: 2026-10-19. Status: owner's direction (integrate directly from Kitden, not through a coding
agent), implemented for MetaMCP. Research: [gateway APIs](../../docs/research/gateway-api-2026-10-19.md).

## Problem

On the Gateway page, "Open MetaMCP ↗" opens a different product in a new tab. Moving a server
into the gateway takes two places: add it there, then come back and remove the direct entry.
The owner wants both steps as one Kitden change, with the same review, Apply, verify and Undo.

## User stories

### US1 — See what the gateway holds (P1)

The gateway card lists the servers the gateway already holds, names only. Details opens the
side panel with its address and type. When the gateway cannot be reached or the sign-in fails,
the card says so in one line and the rest of the page keeps working.

**Test**: with a fake MetaMCP that holds two servers, the Gateway page shows both names.

### US2 — Move one server into the gateway (P1)

Each row in "Can move into the gateway" has "Move into the gateway…". The review shows every
step in order: add the server to the gateway (name and address, secrets hidden), then remove
the direct entry from each client file. Apply runs the steps in order and verifies both sides:
the gateway's list holds the server and the client files read back as expected. Undo removes
the server from the gateway and restores each file from its backup. The change is recorded on
the Changes page.

**Test**: on a fixture home with a fake MetaMCP, one Apply moves the server, one Undo puts it
back; the fixture files equal the originals after Undo.

### US3 — Move all (P2)

The group heading "Can move into the gateway" has "Move all N…": one review with every server's
steps, one Apply, one Undo.

### US4 — Sign-in details stay in Kitden (P2)

The gateway form takes the MetaMCP sign-in email and the **name** of the environment variable
that holds the password. Kitden signs in for one operation and signs out. "Open MetaMCP ↗"
stays as a small secondary link for everything else.

## Edge cases

| Case | Behaviour |
| --- | --- |
| Gateway unreachable, sign-in fails, or the API answers in an unexpected shape | The preview is refused with one plain sentence; nothing is written |
| The gateway already holds a server with this name | The preview is refused: "MetaMCP already has X. Remove the direct entry instead." |
| The client's name is not valid in MetaMCP (`.`, spaces, `__`) | The gateway step uses a cleaned name; the review shows it |
| The direct entry references a variable (`${VAR}`) or a header with a variable name | Refused: the gateway cannot read the shell's variables |
| The gateway step succeeds but a file step fails | The server is removed from the gateway again, files are restored, state `restored` |
| Undo: the server was already removed from the gateway by hand | Undo continues with the files and says the gateway side was already gone |
| Undo: a client file changed after the change | Nothing changes, as today (`undo_blocked`) |
| The page was started without the password variable | The preview is refused: "Set KEY_VAR before starting Kitden" |

## Requirements

- FR-001: The Gateway page shows, per registered MetaMCP gateway, the names of the servers it
  holds; address and type stay behind Details.
- FR-002: "Move into the gateway…" on a row and "Move all N…" on the group open one review with
  every step in order: the gateway step first, then one file step per client entry.
- FR-003: Apply runs the gateway step through MetaMCP's API, then the file steps through the
  existing engine; it verifies by reading the gateway's list and each file back.
- FR-004: Undo removes the server from the gateway and restores every file from its backup.
- FR-005: Every move is recorded on the Changes page, including the gateway step, with the
  gateway's address as its place.
- FR-006: Secrets (header values, bearer tokens, the password) never appear on the page, in the
  diff, in the log or in error text.
- FR-007: A gateway record holds the sign-in email and the password variable's name, never a
  password; the settings file refuses a value that looks like a secret.
- FR-008: A gateway that cannot be reached or signed into never blocks the rest of the page.
- FR-009: An unexpected API answer refuses the preview and writes nothing.

## Success criteria

- SC-001: On a fixture home with a fake MetaMCP, "Move all" moves every direct remote server
  with one Apply; one Undo restores the fixture files byte for byte and empties the gateway.
- SC-002: Unit tests cover list, add, remove, sign-in failure, name clash, cleaned names,
  partial failure and undo; no test touches the network or the owner's files.
- SC-003: The page passes the browser check in both themes and at 375 px, and the wording test.

## Exclusions

Obot (its API needs an admin role, a catalog entry and a vMCP edit; a later feature). Local
(stdio) servers and plugin servers: a gateway cannot run them. Turning tools on or off in the
gateway. Editing the gateway's own settings.
