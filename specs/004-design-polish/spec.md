# Feature Specification: Overview and panel polish

**Feature Branch**: `004-design-polish`

**Created**: 2026-10-18

**Status**: Draft

**Input**: Part A of the [design review](../../docs/research/design-and-install-review-2026-10-18.md)
(2026-10-18). The review is the design input; this spec only fixes what "done" means.

## Why

The review scored the page 3/3/3/2/3 on simple, easy, intuitive, no noise and modern. The cards
explain problems with file paths, the panel's buttons do not match the warning, the review
shows raw diff headers, and counters repeat the same fact in several places. Every fix is a
wording or layout change; the data models already have what is needed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The Overview says what to do (Priority: P1)

The developer opens the page and reads one card per problem: a short title, one plain sentence
that says why it matters and what to do, and one filled button that names the action.

**Independent Test**: Open Overview on a sandbox home with duplicates and a gateway.

**Acceptance Scenarios**:

1. **Given** a skill loads twice in Codex and Cursor, **Then** there is one card
   "docker-expert loads twice in Codex and Cursor", one sentence, and a button "Keep one…"
   that opens the item in the side panel.
2. **Given** any card, **Then** it shows no file path. Paths stay in the side panel.

### User Story 2 - The side panel names the fix (Priority: P1)

The warning in the panel names the fix, and the button that does it is the primary one. Other
actions sit under "More". The row that wins uses a neutral tint, not the gateway blue.

**Independent Test**: Open a duplicated plugin and a direct MCP entry from the Load map.

**Acceptance Scenarios**:

1. **Given** "Cursor loads it twice", **Then** the warning ends with what to do and the
   primary button turns one copy off in Cursor.
2. **Given** a direct MCP entry with a gateway registered, **Then** the warning says to add it
   in the gateway and remove the direct entry, and the primary button removes it.

### User Story 3 - The review shows the result first (Priority: P2)

The review starts with the result in sockets ("After: Claude Code Off · Cursor loads once"),
folds the file change and the command under "Show file change", and has one Cancel.

**Independent Test**: Preview a plugin off, a remove and a gateway connect.

### User Story 4 - Less noise (Priority: P2)

The remove list from the review: rail item count and "6 around"; Clients pills; gateway
host:port and the empty bar; the "Recent changes" card; "State unknown" badges, "×2" and the
legend on the Load map; diff headers; the "Entry name" field; paths in "Can move" rows;
"Details" on every Changes row.

### User Story 5 - Gateway, Changes, Load map and words (Priority: P3)

Problems 4–7 of the review: "Remove direct entry…" with its note beside it, wires only for
connected clients, rows grouped by server with client marks, "Used" when there are two
gateways; greyed undone rows and a clickable row on Changes; "Loads · account" on the Load
map; the word changes of problem 7.

### Edge Cases

- A duplicate skill has no on/off control: the card still opens the panel, where both copies
  are listed with their paths.
- A gateway with nothing around it: no attention card and no gateway card.
- A direct entry in two clients: one row on Gateway, one review with one step per client.

## Requirements *(mandatory)*

- **FR-001**: Every Overview card MUST have a title, one sentence, and at most one button
  that names the action; no card MUST show a file path.
- **FR-002**: Duplicates MUST be one card per item, naming every client that loads it twice.
- **FR-003**: A warning flag MUST carry the fix in words and, where one exists, the action
  that fixes it; the panel MUST show that action as the primary button.
- **FR-004**: A change review MUST start with the state after the change per client, and MUST
  hide the diff and the command until asked.
- **FR-005**: Every item in the remove list (US4) MUST be gone from the page.
- **FR-006**: Gateway MUST list direct entries once per server with the clients that have it,
  and MUST draw a wire only for a connected client.
- **FR-007**: Changes MUST grey out undone rows, show Undo only on active rows, and open
  details from the whole row.
- **FR-008**: The design document MUST reflect every wording change.

## Success Criteria *(mandatory)*

- **SC-001**: On the sandbox home, no Overview card contains `/` or `~/`.
- **SC-002**: Every warning in the panel ends with a sentence that says what to do.
- **SC-003**: `uv run pytest -q` and `uv run ruff check .` stay green after every task.
- **SC-004**: The page keeps the strict CSP: no inline scripts or styles, no CDN.

## Assumptions

- Phones: unchanged (problem 8 is low priority in the review).
- The gateway side card stays only while no gateway is registered; with one, the attention
  card is the single place that mentions it.
- Connecting a second gateway from the page is not needed now: the entry name is always
  `gateway`.
