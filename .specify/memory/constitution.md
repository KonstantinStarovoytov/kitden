# Kitden Constitution

## Core Principles

### I. Clear communication

Discuss work with the owner in simple Russian until they request another language.
Write code identifiers, comments, UI text, specifications, and documentation in simple English.
Explain unfamiliar terms when first used. Use diagrams for system boundaries and data flows,
and tables for comparisons. Every visual must have a short text explanation.

### II. Specify before building

Define the problem, user scenarios, acceptance criteria, and exclusions before implementation.
Use Spec Kit for specifications, plans, and tasks. Keep confirmed requirements, proposals,
and open questions visibly separate. Record important technical choices and alternatives
in decision records. Research claims must link to primary sources and carry a review date.
Vendor documentation is evidence of a documented feature, not proof of runtime behavior.
Before claiming that something is new or missing in the market, search for existing tools
and record what was checked and when.

### III. Safe changes to client setups

Reading is the default. The product MUST NOT change any client configuration without an
explicit action by the owner. Every write MUST:

- prefer the client's own command-line interface; otherwise use documented configuration keys;
- never target undocumented storage until a recorded experiment shows the write is reliable,
  survives a restart, and is not overwritten by the client or its account sync;
- back up the affected files first, verify the result after writing, and offer undo;
- preserve settings the product does not understand.

Rationale: a broken or silently changed client setup is the worst failure of this product.

### IV. Honest and private inventory

Every item shown MUST state where it comes from: client, file or source, and scope.
State the product cannot read MUST be labeled "unknown", never omitted or guessed.
Secret values MUST NOT be displayed, logged, or copied as plain text into another file.
Inventory and usage data MUST NOT leave the machine without explicit opt-in.
Treat configuration files, plugin manifests, and MCP metadata as untrusted input.

### V. Verify against real clients

Pin and record the supported version of each client. Test reading against fixtures copied from
real configurations, with secrets removed. Every write path needs a round-trip test:
write, read back, undo, and compare with the original. Test that unknown state is labeled.
When a client release changes a file format, detect it and fail safely instead of guessing.
Documentation-only changes need consistency and link checks, not application tests.

### VI. Keep it local and simple

Design first for one developer on their own computer. Local use MUST NOT require a server,
an account, or a login. Prefer existing maintained tools over rebuilding them: vendor CLIs for
changes, existing MCP gateways for traffic control, existing observability tools for telemetry.
Keep the component that reads and writes client files separate from the user interface, so a
team version can reuse it later. Add servers, background processes, or new dependencies only
for a recorded need.

## Product boundaries

The product shows what AI coding clients load on a developer's computer and changes that setup
safely. First supported clients: Claude Code (including the Claude Desktop Code tab), Codex,
and Cursor. Items in scope: MCP servers, skills, plugins, hooks, marketplaces, and their scopes.

MCP tools are managed in an existing MCP gateway (gateway first). The product connects the gateway
to every client, shows MCP servers that bypass it, and may remove old direct entries; it does not
add or toggle individual MCP servers in client files.

Not in scope: building or running an MCP gateway or proxy, carrying agent traffic, managing
account-side state, public SaaS, and billing. A team server is a later option, not a requirement.

The product name is Kitden (decided by the owner on 2026-10-18). The implementation language,
framework, storage, and the choice between an own tool and a contribution to an existing
open-source tool are settled per feature in specification and planning.
The [project brief](../../docs/project-brief.md) holds the approved scope.

## Development workflow

Use research -> constitution -> specify -> clarify -> plan -> checklist -> tasks -> analyze
-> implement -> converge. Revisit earlier artifacts when evidence changes a decision.
For small changes, keep the artifacts proportional to the change.

Before implementation, check that the relevant specification, plan, and tasks agree.
Before completion, report what changed, what was verified, and material unresolved limits.
Ask the owner only for decisions that materially change scope or cannot be inferred.
Continue authorized, reversible work without repeated confirmation.

## Governance

This file is the source of project engineering principles. AGENTS.md provides short
working instructions and links here. Explicit owner instructions govern project direction.
Amend this constitution when those instructions change a principle; record the reason,
date, and affected artifacts. Use a major version for incompatible principle changes,
a minor version for added principles, and a patch version for wording fixes.
Plans and reviews must check compliance and explain any intentional exception.

**Version**: 2.1.1 | **Ratified**: 2026-10-16 | **Last Amended**: 2026-10-18

Amendment 2.1.1 (2026-10-18): the product name is Kitden (feature 002). Wording only.
