# Feature Specification: Agent setup inventory and safe controls

**Feature Branch**: `001-agent-setup-inventory`

**Created**: 2026-10-17

**Status**: Draft

**Input**: User description: "Approved project brief (docs/project-brief.md, 2026-10-17): one local
page that shows what Claude Code, Codex and Cursor actually load, where each item comes from, and
what loads twice, with safe on/off changes, a read-only 'show my setup' tool for agents, and a way
to connect an existing MCP gateway to all clients."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See every client's setup in one place (Priority: P1)

The developer starts the tool with one command and opens a local page. Without changing anything,
the page lists every MCP server, skill, plugin, hook and marketplace that Claude Code (including the
Claude Desktop Code tab), Codex and Cursor have on this computer. For each item the page shows the
client, where the item comes from (which file, or which other client's folder), its scope (user-wide,
project or local) and whether it is enabled. Anything the tool cannot read is shown as "unknown"
with a reason.

**Why this priority**: This is the main pain: "I cannot see what is installed and enabled where".
On its own it already removes the need to open each client's settings just to look.

**Independent Test**: On a computer with all three clients configured, start the tool, compare the
page against each client's own settings screens, and confirm every item appears with the right
source and scope or is labeled "unknown". Confirm no file changed.

**Acceptance Scenarios**:

1. **Given** Claude Code, Codex and Cursor are installed and configured, **When** the developer
   starts the tool, **Then** the page lists the items of all three clients, grouped by client, with
   source, scope and enabled state for each.
2. **Given** a client is not installed, **When** the page loads, **Then** that client is shown as
   "not found" and the other clients are listed normally.
3. **Given** an MCP server entry contains a secret, **When** it is shown, **Then** the page says a
   secret is present but never shows its value.
4. **Given** some plugins exist only in the vendor account (for example Claude chat or Cowork
   plugins), **When** the page loads, **Then** they are represented as "unknown: stored in the
   account" rather than silently missing.
5. **Given** the tool has only read files, **When** the developer closes it, **Then** no client
   configuration file has changed.
6. **Given** the page is open, **When** the developer looks at a client, **Then** the detected client
   version is shown.
7. **Given** the tool is running, **When** another computer on the network tries to open the page,
   or network traffic is observed, **Then** the page is not reachable from outside and no inventory
   data leaves the computer.

---

### User Story 2 - Understand what loads in a project, and what loads twice (Priority: P2)

The developer picks a project. The page shows, for each client, what that client actually loads
in this project after combining user-wide, project and local settings. The page points out items
configured more than once, and items one client takes from another client's folders, and explains
why with the source of each copy.

**Why this priority**: Since 2026 the clients read each other's skills, plugins, hooks and
marketplaces, so the same item can load twice or appear without the developer knowing where it
came from. This turns the inventory into an explanation.

**Independent Test**: Prepare a project where one skill exists in two folders that Cursor reads and
one MCP server is defined both user-wide and in the project. Open the project view and confirm both
are flagged with their sources.

**Acceptance Scenarios**:

1. **Given** a project known to the clients, **When** the developer selects it, **Then** the page
   shows, per client, the items that client loads there.
2. **Given** Cursor loads a skill from a Claude Code or Codex folder, **When** the project view is
   shown, **Then** the skill is marked as cross-loaded with the folder it comes from.
3. **Given** the same item would load twice in one client, **When** the project view is shown,
   **Then** it is marked as a warning listing both sources.
4. **Given** the same item is set up in two different clients, **When** the view is shown, **Then**
   it is marked as information, not a warning.

---

### User Story 3 - Bring MCP tools under the gateway (Priority: P3)

MCP tools are managed in an existing MCP gateway (Obot or MetaMCP), not in each client's files.
The developer enters the gateway address once and adds it to the chosen clients in one action. The
page then shows every MCP server that does not go through the gateway (servers bundled in plugins,
local servers that must run on the laptop, old direct entries), with its source. After the
developer has moved a server's tools into the gateway, the page can remove the old direct entry.
Turning tools on and off happens in the gateway's own interface, which the page links to. Every
write is shown as a preview first, happens only after "Apply", is backed up, verified, and can be
undone.

**Why this priority**: The owner chose gateway first: one place for MCP tools, one entry per
client. What remains for the page is connecting the gateway and showing what goes around it.

**Independent Test**: Start a local gateway, connect it to Claude Code, Codex and Cursor, confirm
each client lists the gateway entry, confirm the page lists the remaining direct MCP servers as
"bypasses the gateway", remove one old direct entry, then undo both changes and confirm the
settings are exactly as before.

**Acceptance Scenarios**:

1. **Given** a gateway address and three selected clients, **When** the developer previews the
   connection, **Then** the page shows the change for each client and writes nothing until "Apply".
2. **Given** the developer applies, **When** the write finishes, **Then** the tool re-reads each
   client's settings, confirms the gateway entry, and records the change in a local change log.
3. **Given** the gateway requires a key, **When** the entry is created, **Then** the key is stored
   as an environment variable reference, not as plain text.
4. **Given** the gateway requires an OAuth login, **When** the entry is created, **Then** the page
   shows each client's login command.
5. **Given** a client has MCP servers that do not use the gateway, **When** the page loads, **Then**
   each one is flagged "bypasses the gateway" with its source (plugin, local server, direct entry).
6. **Given** an old direct entry whose tools are now in the gateway, **When** the developer removes
   it and applies, **Then** the entry is removed, and undo restores the settings exactly.
7. **Given** a client must be restarted for a change to take effect, **When** the change is applied,
   **Then** the page says so.
8. **Given** the developer wants to turn a gateway tool on or off, **When** they open the gateway
   entry, **Then** the page links to the gateway's interface and does not change tools itself.

---

### User Story 4 - Turn plugins on and off (Priority: P4)

The developer turns a plugin on or off in Claude Code or Codex from the page, with the same preview,
apply, verify and undo flow as every other change. For Cursor, plugins are shown but cannot be changed until
a recorded check has proved that writing Cursor's plugin state is reliable. For actions the tool does
not perform (install, update, move between clients, add a marketplace), the page shows the exact
command of the client that does it.

**Why this priority**: Plugins are part of the owner's success criteria, but writes depend on each
client's storage. Claude Code and Codex document their on/off state; Cursor needs verification first.

**Independent Test**: Disable a plugin in Claude Code from the page, restart Claude Code, confirm it
is disabled, undo, and confirm it is enabled again with settings identical to before.

**Acceptance Scenarios**:

1. **Given** an installed plugin in Claude Code or Codex, **When** the developer turns it off and
   applies, **Then** the client treats it as disabled after the change takes effect, and undo
   restores it.
2. **Given** Cursor plugin writes are not yet verified, **When** the developer views a Cursor plugin,
   **Then** the on/off control is unavailable and the page explains why.
3. **Given** the developer wants to install a plugin in another client, **When** they open that
   action, **Then** the page shows the client's own command to do it and does not run it.

---

### User Story 5 - Ask the agent "show my setup" (Priority: P5)

The developer can add a read-only MCP server to any client. In an agent session, the developer asks
"what do you have here?" and the agent receives the same inventory and project view as the page. The
server cannot change anything. The page offers to add it to each client, shows the command, and runs
it only after the developer confirms.

**Why this priority**: It answers the question where it comes up, inside the agent session, and it
helps in moments like the original incident when time is short.

**Independent Test**: Add the server to Codex, ask Codex in a session to list its setup for the
current project, and compare the answer with the page.

**Acceptance Scenarios**:

1. **Given** the read-only server is added to a client, **When** the agent calls it for the current
   project, **Then** it returns the items, sources, scopes and findings shown on the page.
2. **Given** any request to change settings through this server, **When** it is called, **Then** it
   refuses, because it has no change actions.
3. **Given** the developer has not confirmed, **When** the page offers to add the server, **Then**
   nothing is written to the client.

---

### Edge Cases

- A client's configuration file is malformed or in a format the tool does not recognize: affected
  items are shown as "unknown", and writes to that file are blocked.
- A client rewrites its whole configuration file on its own (reordering sections, dropping
  comments): the tool detects the change on rescan and does not treat it as an error.
- A client changes its settings between the preview and "Apply": the tool detects that the file
  changed, cancels the apply, and asks the developer to review again.
- A write succeeds but the verification read shows a different result: the tool restores the backup
  and reports the failure.
- A client is running during a change: the page says whether a restart is needed.
- A project folder known to a client no longer exists: the project is listed as missing.
- The same MCP server name has different settings in two scopes: both are shown, and the one that
  wins is marked.
- Skills are reached through symbolic links or shared folders: the real location is shown.
- The tool lacks permission to read a file: the items are shown as "unknown: no access".
- A new client version changes a known format: affected items become "unknown" until support is
  updated; nothing is guessed.
- The gateway entry exists in a client but the client's gateway login has expired: the page shows
  the entry and the client's login command; it does not store or refresh tokens.
- No gateway is registered yet: every MCP server is shown as "bypasses the gateway" and the page
  explains how to connect one.

## Requirements *(mandatory)*

### Functional Requirements

**Discovery and inventory**

- **FR-001**: The system MUST detect which supported clients are present: Claude Code (including the
  Claude Desktop Code tab), Codex (command line and desktop app), and Cursor, and show clients that
  are not found.
- **FR-002**: The system MUST list, for each client, its MCP servers, skills, plugins, hooks and
  marketplaces.
- **FR-003**: For each item, the system MUST show the client, the source (file or other origin,
  including another client's folder), the scope (user-wide, project, local) and the enabled state.
- **FR-004**: The system MUST list the projects each client knows.
- **FR-005**: The system MUST label anything it cannot read as "unknown" with a reason (for example:
  stored in the account, no access, unrecognized format) and MUST NOT omit it silently when its
  existence is known.
- **FR-006**: The system MUST NOT display, log or return secret values; it MUST indicate that a
  secret is present.
- **FR-007**: The system MUST NOT write anything during discovery.
- **FR-008**: The system MUST rescan when client configuration files change and when the developer
  asks.
- **FR-009**: The system MUST record the detected version of each client and show it.

**Project view and findings**

- **FR-010**: For a selected project, the system MUST show what each client loads there, combining
  the client's user-wide, project and local settings according to that client's documented rules.
- **FR-011**: The system MUST flag an item that one client would load more than once as a warning,
  listing every source.
- **FR-012**: The system MUST flag an item that a client loads from another client's folders as
  cross-loaded, showing the folder.
- **FR-013**: The system MUST show the same item set up in different clients as information, not as
  a warning.
- **FR-014**: When the same name is defined in several scopes, the system MUST mark which definition
  takes effect.

**Safe changes**

- **FR-015**: Every change MUST be shown as a preview and applied only after an explicit "Apply".
- **FR-016**: Before applying, the system MUST check that the affected files did not change since the
  preview; if they did, it MUST cancel and ask for a new review.
- **FR-017**: The system MUST back up the affected settings before writing.
- **FR-018**: After writing, the system MUST read the settings again and confirm the result; on a
  mismatch it MUST restore the backup and report the failure.
- **FR-019**: Every applied change MUST be undoable, restoring the exact previous content.
- **FR-020**: The system MUST keep settings it does not understand unchanged.
- **FR-021**: The system MUST use the client's own command when that command keeps settings it does
  not understand (FR-020). Otherwise it MUST edit only documented settings and leave the rest of the
  file unchanged.
- **FR-022**: The system MUST keep a local log of applied changes without secret values.
- **FR-023**: The system MUST tell the developer when a client needs a restart for a change to apply.
- **FR-024**: The default target for new entries MUST be the private user or local scope; writing to
  a project file usually shared through git MUST show a warning.

**MCP servers (gateway first)**

- **FR-025**: The system MUST NOT add, enable or disable individual MCP servers in client settings;
  MCP tools are managed in the gateway. The only MCP writes are the gateway entry (FR-033) and the
  removal of an old direct entry (FR-026).
- **FR-026**: The developer MUST be able to remove a direct MCP entry from a chosen client and scope,
  using the same preview, apply, verify and undo flow.

**Plugins**

- **FR-027**: The developer MUST be able to enable and disable installed plugins in Claude Code and
  Codex.
- **FR-028**: For Cursor, plugin on/off controls MUST stay unavailable until a recorded verification
  shows the write is reliable, survives a restart, and is not overwritten by the client or account
  sync; the page MUST explain why the control is unavailable.
- **FR-029**: For installing, updating, moving plugins between clients and adding marketplaces, the
  system MUST show the client's own command and MUST NOT perform the action itself.

**Agent tool**

- **FR-030**: The system MUST provide a read-only MCP server that returns the same items, sources,
  scopes and findings as the page, for a client named in the request (all clients if none) and a
  project path (the current folder if none).
- **FR-031**: The read-only server MUST have no actions that change settings.
- **FR-032**: The page MUST offer to add the read-only server to each client, show the exact command,
  and act only after the developer confirms.

**Gateway connection**

- **FR-033**: The developer MUST be able to add one MCP gateway address to several selected clients
  in one action, using the same preview, apply, verify and undo flow.
- **FR-034**: The system MUST mark MCP entries that point to a registered gateway address.
- **FR-035**: When a gateway needs a key, the system MUST store it as an environment variable
  reference; when it needs an OAuth login, the system MUST show each client's login command.

**Local operation and privacy**

- **FR-036**: The tool MUST start with one command and MUST NOT require an account or a login.
- **FR-037**: The page MUST be reachable only from the local computer.
- **FR-038**: Inventory and usage data MUST NOT leave the computer.

**Gateway findings**

- **FR-039**: The system MUST flag every MCP server that does not go through a registered gateway as
  "bypasses the gateway", saying whether it comes from a plugin, is a local server, or is a direct
  entry, with its source.
- **FR-040**: For turning gateway tools on or off, the system MUST link to the gateway's interface
  when the developer has given its address, and MUST NOT change gateway tools itself.

**Untrusted input and unknown formats**

- **FR-041**: Everything read from client files and MCP metadata MUST be treated as untrusted and
  shown as plain text only, never run as HTML or script.
- **FR-042**: When a file's format is not recognized, its items MUST be shown as "unknown" and every
  write to that file MUST be refused.

### Key Entities

- **Client**: a supported AI coding client on this computer; has a name, a detected version, and a
  found or not-found status.
- **Source**: where an item comes from: a settings file, a folder, another client's folder, or the
  vendor account (unreadable).
- **Scope**: user-wide, project or local; decides where an item applies.
- **Item**: an MCP server, skill, plugin, hook or marketplace; belongs to a client, has a source, a
  scope, an enabled state, and may be "unknown".
- **Project**: a folder that one or more clients know; has an effective view per client.
- **Finding**: a duplicate, cross-loaded item, scope override, MCP server that bypasses the gateway,
  or unknown state, with the sources that explain it.
- **Change**: a pending or applied edit to one client's settings; has a preview, a backup, a
  verification result, and an undo.
- **Gateway**: an MCP address the developer marks as a gateway, optionally with a link to its
  interface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any project the clients know, the developer sees what each client loads there
  within 30 seconds of opening the page.
- **SC-002**: In a manual audit of the owner's computer, every item present in the clients' own
  settings appears either with the correct source and scope or labeled "unknown"; none is silently
  missing.
- **SC-003**: Every supported change can be undone, and after undo the affected settings are
  identical to the original in 100% of round-trip checks across the supported clients.
- **SC-004**: An audit of the page, the change log and the agent tool output finds zero secret
  values.
- **SC-005**: Connecting a gateway to all three clients, including preview and apply, takes under
  two minutes of the developer's time, not counting each client's own login step.
- **SC-006**: First results appear within 10 seconds of the start command on the owner's computer.
- **SC-007**: Asking the agent "show my setup" in a client with the read-only server returns the same
  items and findings as the page for that project.
- **SC-008**: During two weeks of daily use, the owner does not need to open a client's own settings
  screen to view items or to turn Claude Code and Codex plugins on or off; MCP tools are changed
  only in the gateway.
- **SC-009**: After connecting the gateway, every MCP server that bypasses it is listed with its
  source; a manual audit finds none missing.

## Assumptions

- First release targets macOS and one developer; clients are installed in their default locations.
- Codex command line and desktop app share the same settings; the Claude Desktop Code tab shares
  Claude Code settings. Claude Desktop chat and Cowork plugins and connectors live in the vendor
  account and are shown only as "unknown".
- Backups and the change log are kept locally for at least 30 days or the last 100 changes,
  whichever is larger.
- Clients may need a restart before some changes take effect; this is reported, not prevented.
- Cursor plugin writes depend on a verification task that comes first in planning.
- Out of scope for this feature: installing, updating or moving plugins, adding marketplaces,
  adding or turning individual MCP servers on or off in client files, moving MCP servers into the
  gateway automatically, Langfuse or LangSmith export, a team server, explaining a folder missing
  from a client's `@` list, and building an MCP gateway.
- Gateway first (owner decision, 2026-10-17): MCP tools are managed in an existing MCP gateway
  (Obot or MetaMCP) that is installed and run separately. MCP servers that cannot go through a
  remote gateway (bundled in plugins, or needing the laptop) stay direct and are flagged.
- Whether this is built as an own tool or as a contribution to Cross-Code Organizer is decided
  during planning; this specification applies either way.
- Visual design is a separate task.
