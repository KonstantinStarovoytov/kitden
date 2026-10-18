# Feature Specification: Kitden name and one-command page

**Feature Branch**: `002-kitden-rename`

**Created**: 2026-10-18

**Status**: Draft

**Input**: Owner: "Feature 002 through Spec Kit: rename to Kitden with a move of MCP entries and
the data folder, a `kitden open` command, one page per computer, stop when no tab is open."

## Why

The product is now called Kitden. The working name `agentsetup` is taken by another package,
so a public release needs the new name everywhere. The owner also wants to open the page from
a coding agent or a terminal with one command, without managing a server: today two pages can
run at once and log each other out, and a forgotten page keeps running for days.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Kitden everywhere (Priority: P1)

The developer installs Kitden and sees the new name everywhere: the command, the page, and the
read-only MCP server in their coding clients.

**Why this priority**: The old name collides with another package. Nothing can be published
until the product has one name.

**Independent Test**: Install from the repository, run `kitden --version`, open the page, and add
the MCP server to a sandbox client.

**Acceptance Scenarios**:

1. **Given** Kitden is installed, **When** the developer runs `kitden --version`, **Then** it
   prints `kitden` and the version.
2. **Given** the page is open, **Then** the page and the browser tab say Kitden.
3. **Given** the developer adds the read-only MCP server to a client, **Then** the entry is named
   `kitden` and starts the `kitden` command.

---

### User Story 2 - Nothing is lost when moving from the old name (Priority: P1)

A developer who used the working version keeps their gateways, change history and Undo. Old
MCP entries made by the working version are found and can be updated in one step.

**Why this priority**: The owner already has gateways, a change log and an old entry in Codex.
Losing them, or leaving a broken entry, breaks the main promise: safe changes.

**Independent Test**: Start Kitden on a sandbox home that has the old data folder and an old
MCP entry in each client.

**Acceptance Scenarios**:

1. **Given** the old data folder exists and the new one does not, **When** Kitden starts for the
   first time, **Then** the gateways and the change history appear unchanged, and Undo of a change
   made before the rename still restores the file.
2. **Given** both folders exist, **When** Kitden starts, **Then** it uses the new folder, leaves the
   old one untouched, and says so.
3. **Given** a client has an MCP entry made by the working version, **Then** the page marks it as
   an old Kitden entry and offers "Update to Kitden". Apply replaces it with a `kitden` entry,
   with the usual preview, backup, check and Undo.
4. **Given** the old entry's command no longer exists, **Then** the page still offers the update
   and says the old command is missing.
5. **Given** an entry named `agentsetup` that starts some other program, **Then** Kitden does not
   mark or change it.

---

### User Story 3 - Open the page with one command (Priority: P2)

From a terminal or a coding agent, `kitden open` opens the page and returns at once. If a page
already runs, the same page opens. Only one page runs per computer.

**Why this priority**: An agent can open the page without waiting for it to close, and the
developer never ends up with two pages that log each other out.

**Independent Test**: Run `kitden open` several times from different folders; check that one page
runs and that each call returns within seconds.

**Acceptance Scenarios**:

1. **Given** no page runs, **When** `kitden open` runs, **Then** the page starts in the background,
   the browser opens it, the link is printed, and the command returns.
2. **Given** a page already runs, **When** `kitden open` runs from any folder, **Then** the browser
   opens that page and no second page starts.
3. **Given** the page stopped without cleaning up, **When** `kitden open` runs, **Then** it notices
   and starts a fresh page.
4. **Given** a test page runs for another home folder, **Then** it does not log out or replace the
   developer's own page.
5. **Given** the developer runs `kitden` with no command, **Then** it behaves like `kitden open`.

---

### User Story 4 - The page stops when no tab is open (Priority: P3)

After the last tab closes, a page started by `kitden open` stops by itself after a short wait.
It never stops in the middle of a change.

**Why this priority**: No forgotten server in the background. It matters less than the first
three stories because a running page is harmless, only wasteful.

**Independent Test**: Open the page, close the tab, and check that the page process is gone after
the wait.

**Acceptance Scenarios**:

1. **Given** the last tab closed, **When** 10 minutes pass without a tab, **Then** the page stops
   and its record is removed.
2. **Given** a tab opens again within those 10 minutes, **Then** the page keeps running.
3. **Given** a change is being applied or undone, **Then** the page does not stop until it ends.
4. **Given** the page started but no tab ever opened, **Then** it stops after the same wait.

---

### Edge Cases

- The old data folder cannot be copied: Kitden deletes nothing, explains the problem, and runs
  with an empty new folder.
- An old page is still running: it keeps its own folder, because Kitden copies and never moves.
- A client has both an old entry and a `kitden` entry: the update only removes the old one.
- An `agentsetup` entry in a project file: the working version never wrote one, so it is left alone.
- The port is busy: the page uses the next free port, as today.
- The page record is left behind after a crash: `kitden open` detects that the page is gone.
- The page record holds the start link: only the developer's own account can read it.
- Remote sessions (SSH, containers, cloud agents): `kitden open` works on the machine it runs on
  and says nothing about another machine. Not supported beyond that.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The command, package, page, read-only MCP server name and data folder MUST use the
  name Kitden (`kitden`).
- **FR-002**: `kitden --version` MUST print `kitden` and the version.
- **FR-003**: When the old data folder exists and the new one does not, Kitden MUST copy it once,
  keeping gateways, change history and backups, and MUST leave the old folder as it is. Undo of
  earlier changes MUST keep working.
- **FR-004**: When both folders exist, Kitden MUST use the new one and MUST NOT change the old one.
- **FR-005**: The page MUST recognise an old Kitden entry: a user-level MCP entry named
  `agentsetup` in Claude Code, Codex or Cursor that runs the old command with the `mcp` argument.
- **FR-006**: For each old entry the page MUST offer "Update to Kitden": one change that removes the
  old entry and adds the `kitden` entry, with preview, backup, check and Undo.
- **FR-007**: Entries named `agentsetup` that run another program MUST NOT be marked or changed.
- **FR-008**: `kitden open`, and `kitden` with no command, MUST open the running page for this home
  folder if there is one, otherwise start one in the background and open it. It MUST print the
  link and return within 5 seconds.
- **FR-009**: At most one page MUST run for one home folder.
- **FR-010**: The record of the running page (address, process and start link) MUST be readable
  only by the developer's own account and MUST be removed when the page stops.
- **FR-011**: Pages for different home folders MUST NOT log each other out.
- **FR-012**: A page started in the background MUST stop after 10 minutes without an open tab and
  MUST NOT stop while a change is being applied or undone.
- **FR-013**: `kitden serve` MUST run the page in the foreground until Ctrl+C, for development and
  tests, under the same one-page rule.
- **FR-014**: Living documents (README, contracts, constitution, brief) MUST use the name Kitden.
  Feature 001 documents stay as history.

### Key Entities

- **Page record**: the running page for one home folder — its address, process and start link.
  Exists only while the page runs.
- **Old Kitden entry**: an MCP entry made by the working version, found in a client's user
  settings, with the client, the file and whether its command still exists.
- **Data folder**: gateways, change history and backups. Copied once from the old name to the new.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a copy of a real setup, all gateways and every change in the history are still
  listed after the update, and Undo of a change made before the rename restores the file exactly.
- **SC-002**: The owner's old entry in Codex is updated to Kitden with one review and one Apply,
  and Undo brings the old entry back exactly.
- **SC-003**: `kitden open` returns in under 5 seconds when no page runs and in under 2 seconds
  when one runs.
- **SC-004**: Five `kitden open` calls in a row leave exactly one page running.
- **SC-005**: After the last tab closes, the page process is gone within 11 minutes.
- **SC-006**: No user-facing text says "agentsetup", except where the page names old entries or
  the old folder during the move.

## Clarifications

### Session 2026-10-18

- Q: Move or copy the old data folder? → A: Copy once and leave the old folder, so a still
  running old page keeps working and nothing can be lost.
- Q: What does `kitden` with no command do? → A: The same as `kitden open`; `kitden serve` runs in
  the foreground for development and tests.

## Assumptions

- macOS only, as in feature 001.
- The wait before stopping is 10 minutes and is not configurable.
- No alias is kept for the old `agentsetup` command. The README explains how to remove it after
  updating the entries.
- The working version only added its MCP entry at user level.
- Out of scope: publishing to PyPI, client plugins, a domain, and accounts. These are separate steps.
