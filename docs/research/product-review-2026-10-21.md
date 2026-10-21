# Kitden: product brief and independent review

Date: 2026-10-21  
Source baseline: `d33bfaf1c88187f23c1935e6654307f438bbcbac`  
Status: review brief. The proposals below are not an approved implementation plan.

Follow-up: [conclusions from both reviews](review-conclusions-2026-10-21.md), including
agreements, corrections and revised priority proposals. The original brief below is preserved.

This document combines the owner's product goals with a review of the current code and UI.
It is meant for another agent to challenge and verify. Do not assume that the first review's
conclusions are correct. No application behavior or real client settings changed during it.

## 1. What the owner wants

Kitden should be a simple local manager for what AI coding agents load and can use. Its audience
is one developer or a small team using several coding clients, often on the same project.

The problem is fragmented setup. A user installs a plugin, skill or MCP server in a client,
but cannot easily tell where it was installed, whether it is global or project-specific,
which other clients load it, or what reaches an agent's context.

### Goal A: see the whole setup

Show, in one place:

- What each client has installed.
- What is global and what belongs to a project.
- What a selected project can use, including inherited items.
- Where an item comes from, including plugins and shared folders.
- What loads twice, is overridden, is disabled, or cannot be verified.
- What is missing and can be added.

The owner describes this as visibility into the agent's whole harness. The exact scope of that
promise needs review: extensions alone do not cover instructions, rules and client permissions.

### Goal B: keep several clients aligned

A user may work on one project in Claude Code, Codex and Cursor at the same time. They should
see differences and make the useful parts of those setups consistent without editing files
by hand.

The desired flow is:

1. Pick a project.
2. See what each client has and what differs.
3. Choose the missing or conflicting items to address.
4. Review the combined change and the clients it reaches.
5. Apply it with a backup, verify the result, and retain Undo.

Useful actions include adding missing items to several clients and moving eligible MCP servers
into a common gateway. Alignment must respect client compatibility and intentional differences.

### Goal C: manage MCP tools through one local gateway

The gateway should hold several MCP servers and control which of their tools clients can call.
The owner should be able to allow reading from a service while blocking creation, editing and
deletion, globally or for a project.

Example: allow reading files from Dropbox or a remote office service, but prevent calls that
change those files. Dropbox here is an example use case, not a verified integration claim.

### Product requirements

| Requirement | What success means |
| --- | --- |
| Simple | Clear actions, little text, few decisions, useful bulk operations. |
| Visual | A user can understand the setup and the effect of a change at a glance. |
| Pleasant | Calm, consistent UI with feedback that reflects verified state. |
| Fast | Opening the app and moving between projects should not wait for every slow source. |
| Local and secure | Setup and policy stay local; secrets do not appear in UI or logs or go to unrelated destinations. |
| Reversible | Every client-setting change uses Preview → Apply with a backup → verify → Undo. |

## 2. What exists today

The current implementation targets macOS and has adapters for Claude Code, Codex and Cursor.
It also represents the Claude Desktop Code tab. This is the repository's current scope, not a
claim of support for every ChatGPT, Claude or editor surface.

| Area | Existing behavior | Main gap against the brief |
| --- | --- | --- |
| Inventory | MCP servers, plugins, skills, hooks and marketplaces; scopes, sources and unknown states. | No complete inventory of instructions, rules and permissions; no live context inspection. |
| Comparison | One Library row per item and a column per client; project selection; duplicate and override findings. | No complete flow to align a project's setup across clients in one review. |
| Installation | Add compatible plugins or skills; copy standalone skills from some plugins; some multi-client actions. | These additions go to user-level settings even from a project view. |
| Local gateway | Local and remote servers; whole-server and individual-tool switches; global and project rules; worktree handling. | No strict read-only workflow, immediate policy revocation or central OAuth support. |
| Change safety | Preview, masked diff, backup, verification, history and Undo. | Review still needs to establish the full security boundary. |
| UI | Overview, Library, Gateway and Changes; technical detail in a drawer; restrained light and dark themes. | Some states and actions do not match the user's likely expectation. |
| Startup | Parallel reads, background loading of slow sources, cached views and a small frontend. | No new measurement of cold startup on a large real setup was made in this review. |

Sources: [README](../../README.md), [roadmap](../../ROADMAP.md),
[inventory adapters](../../src/kitden/views/inventory.py),
[item model](../../src/kitden/model.py), and [Library model](../../src/kitden/views/library.py).

## 3. Findings to verify

### F1. Project selection and installation scope do not match

**Observed:** selecting a project changes the Library view, but Add for plugins and skills
still targets global settings. The review shows `Adds for all your projects.`

**Impact:** a user can reasonably expect an action taken in a project view to affect only that
project. The warning comes after that expectation has formed.

**Evidence:** `projectNote()` in [offer.js](../../src/kitden/web/static/js/offer.js),
`previewFor()` and `noteFor()` in [library.js](../../src/kitden/web/static/js/library.js), and
[installation actions](../../src/kitden/changes/actions.py).

**Proposal:** make the target scope clear before the action. Offer project or global scope
where supported. If only global installation is available, say so at the action itself.
Check each client's current official docs before choosing an implementation.

### F2. Saved settings are not proof of live session context

**Observed:** Kitden computes an effective view from saved settings. Library says
`Based on saved settings`, but item states also use `Loads`.

**Impact:** users may read this as confirmation that an existing session already has an item.
Installed, available to a project, and loaded into a running session are distinct states.

**Evidence:** [effective_view()](../../src/kitden/views/effective.py),
[load map](../../src/kitden/views/load_map.py), and
[Library UI](../../src/kitden/web/static/js/library.js).

**Proposal:** keep these distinctions clear without adding noise. Show what is known from
settings, what requires a new session, and what cannot be observed. Do not promise live context
visibility without a reliable source for it.

### F3. Comparison does not establish full equivalence

**Observed:** the load map groups plugins by full plugin ID, including marketplace, and other
items by kind and name. This comparison is useful, but it does not prove equal versions,
contents, server destinations or permissions across clients.

There are existing bulk actions, including adding one item to multiple clients and moving
eligible servers. The missing flow is broader: compare a project's setup, choose a set of
differences, and resolve that set in one review.

**Evidence:** `row_key()` in [load_map.py](../../src/kitden/views/load_map.py),
[Library model](../../src/kitden/views/library.py), and
[offer UI](../../src/kitden/web/static/js/offer.js).

**Proposal:** first support adding selected missing, compatible items. Show conflicts and
intentional exceptions. Avoid treating a matching name as proof of identical behavior or
automatically overwriting a client's setup.

### F4. Gateway policy is permissive for newly discovered tools

**Observed:** when no rule exists, a server or tool is on. A newly discovered tool becomes
eligible when its metadata enters the known tool list and a session uses that list. This does
not mean it appears immediately in an already cached session.

**Impact:** disabling today's write tools does not preserve a strict read-only policy after
the server adds another write tool.

**Evidence:** `_is_on()` and `allowed_tools()` in
[settings.py](../../src/kitden/local_gateway/settings.py), and
`test_a_rule_for_a_missing_tool_is_ignored_and_a_new_tool_is_on` in
[the policy tests](../../tests/unit/test_local_gateway_settings.py).

**Proposal:** evaluate an explicit allowlist for strict access control. New tools should wait
for review in that mode. The UI can help select tools, but server-provided hints alone cannot
prove that a tool only reads.

### F5. Policy changes do not revoke access in existing sessions

**Observed:** a gateway instance reads settings once and keeps the offered tool set for its
session. Calls use that set. Turning a tool off applies to new sessions; the preview says so.

**Impact:** an existing session may still call a tool after the owner has switched it off.
This is documented behavior, but it limits the owner's intended access-control use case.

**Evidence:** `_Gateway.__init__()`, `call_tool()` and `_offered()` in
[proxy.py](../../src/kitden/local_gateway/proxy.py).

**Proposal:** review the smallest way to enforce current denials before forwarding subsequent
calls. A client may retain a stale tool list while the gateway still refuses a forbidden call.
Stopping a call that is already running is a separate capability and must not be implied.

### F6. An unknown project falls back to global rules

**Observed:** an unmatched or unavailable project produces an empty project chain. Global
rules then apply. If reading known projects fails, the gateway logs that it will use the
global tool set.

**Impact:** if global rules are broader than the intended project's rules, failure to identify
the project can grant more access than the user expects.

**Evidence:** [project_chain()](../../src/kitden/local_gateway/project.py), `_known()` in
[proxy.py](../../src/kitden/local_gateway/proxy.py), and
[project tests](../../tests/unit/test_local_gateway_project.py).

**Proposal:** define an explicit safe policy for unknown projects. Review whether it should
block tools in a strict mode, use a restricted baseline, or require the user to resolve the
project. These are alternatives to assess, not a request to implement all three.

### F7. Local storage is a useful foundation, not a complete security boundary

**Observed:** moved servers' environment values and headers are stored in a private local
settings file. Backups can hold the original secret-bearing bytes. Keychain storage and
central OAuth support are planned, not implemented for the Kitden gateway.

The implementation already has local binding, session authentication, request-origin checks,
a strict Content Security Policy, redaction and private file permissions.

**Evidence:** [security middleware](../../src/kitden/web/security.py),
[backup storage](../../src/kitden/changes/backup.py),
[gateway settings](../../src/kitden/local_gateway/settings.py),
[redaction](../../src/kitden/redact.py), and [development notes](../development.md).

**Proposal:** review keychain-backed secret references, backup handling and the lifecycle of
credentials. Do not describe a file readable by its owner as protection from every process
running as that owner.

The product promise must also distinguish:

- Local management and storage from offline operation. A remote MCP service still receives
  the requests and authentication intended for it.
- Gateway policy from agent-wide policy. A direct MCP connection, terminal tool or other
  route can operate outside this gateway.
- Tool selection from isolation of server code. A local server process needs a separate
  security assessment; hiding its write tools does not sandbox that process.

### F8. Overview incorrectly says there is no gateway

**Observed in the test UI:** Overview showed `No gateway yet` while Library showed a server
through the Kitden gateway and Gateway showed that gateway connected to two clients.

**Cause found:** the Overview model sets its gateway state from registered external gateways.
The UI shows the setup card when that state is absent. The local gateway is not included in
that decision.

**Impact:** the first page contradicts the rest of the app and suggests repeating setup.

**Evidence:** `overview()` in [overview.py](../../src/kitden/views/overview.py) and
`renderOverview()` in [overview.js](../../src/kitden/web/static/js/overview.js).

**Proposal:** make Overview use the actual local gateway state and show the relevant next
action, such as connecting a missing client or reviewing eligible direct servers.

### F9. Whole-harness coverage needs a clear boundary

**Observed:** `ItemKind` covers MCP servers, skills, plugins, hooks and marketplaces.
Instructions such as `AGENTS.md`, `CLAUDE.md`, project rules and client permissions are not
represented as a complete part of that inventory.

**Impact:** the phrase "whole harness" can promise more than the app currently shows.

**Evidence:** [ItemKind](../../src/kitden/model.py) and
[client adapters](../../src/kitden/clients/).

**Proposal:** decide which of these inputs belong in the product's next scope. Start with
read-only visibility if included. Do not expand into every possible client feature at once.

## 4. UI and performance assessment

Keep the existing visual direction. The useful parts are the client matrix, concise rows,
technical details in the drawer, explicit previews, and reversible changes. The main missing
value is completing the user's project and alignment tasks with fewer decisions.

The browser inspection covered Overview, Library, Gateway and a tool-change preview on fake
data in the dark theme. It did not establish full accessibility compliance, large-data
usability, responsiveness at every size, or real-client behavior.

A design detector ran in its reduced regex mode because parser dependencies were unavailable.
It flagged two CSS transitions. These were not established as product defects or evidence of
slow startup. Do not treat that scan as a clean bill of health or a performance benchmark.

The architecture has useful speed measures: parallel inventory reads, background loading for
slow sources, cached views, local assets and no frontend framework. The roadmap's roughly
two-second data-load claim was not independently remeasured in this review.

Before accepting the speed requirement, measure cold start, repeat opening, project switching
and Library changes on a large setup. Include slow or unavailable sources. Agree on a budget
for the first usable view and for complete data separately; show when data is still loading.

## 5. Existing gateway limits to include in the review

The current README explicitly leaves some entries direct: servers requiring OAuth, entries in
project files, some shell-value references, custom working directories, and unsupported
transports. Review the current eligibility code before assuming an arbitrary server can move.

Sources: [README gateway section](../../README.md) and
[local_move_steps()](../../src/kitden/changes/actions.py).

This is especially relevant to the owner's remote-service examples. The review did not test
an actual Dropbox or Microsoft Office connection and does not establish their compatibility.

## 6. External facts checked

Checked against official MCP documentation on **2026-10-21**:

- Tool annotations describe behavior, but clients must treat them as untrusted unless they
  come from trusted servers. A read-only label is not a security guarantee.
  [MCP tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#tool).
- MCP security guidance discusses local-server and proxy risks, process isolation and least
  privilege. Local execution alone does not remove these risks.
  [MCP security best practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices).

Client file formats and client-specific capabilities were not independently revalidated
against all vendors' current docs in this pass. Repository descriptions of those behaviors
are evidence about Kitden's implementation, not fresh proof of vendor behavior.

## 7. Verification record

The earlier review ran the following selected Python tests with an isolated uv cache and
offline dependency resolution:

```sh
UV_CACHE_DIR=/tmp/kitden-audit-uv-cache uv run --offline pytest -q \
  tests/security \
  tests/unit/test_effective.py \
  tests/unit/test_library.py \
  tests/unit/test_local_gateway_settings.py \
  tests/unit/test_local_gateway_project.py \
  tests/unit/test_local_gateway_proxy.py \
  tests/unit/test_page.py
```

Initial result: **152 passed, 3 failed** because the execution sandbox prohibited binding
temporary local test servers. Those exact three tests were rerun with local-server access:

```sh
UV_CACHE_DIR=/tmp/kitden-audit-uv-cache uv run --offline pytest -q \
  tests/unit/test_local_gateway_proxy.py::test_secrets_stay_out_of_errors_and_logs \
  tests/unit/test_local_gateway_proxy.py::test_a_servers_own_error_passes_but_a_transport_error_stays_plain \
  tests/unit/test_page.py::test_the_server_stops_when_asked
```

Rerun result: **3 passed**. Across both runs, **155 distinct selected Python tests passed**.

```sh
node --test tests/frontend/*.test.mjs
```

Frontend result: **91 passed**.

Tests used sandbox homes. The browser preview used fixture data and a fake server entry with
cached tool metadata; no real service was contacted through that entry. The preview was
cancelled without Apply. The temporary server, browser tab and preview files were removed.

These checks do not constitute the full test suite, a penetration test, a fresh performance
benchmark, or end-to-end validation in running Claude Code, Codex and Cursor sessions.
No application changes or commits were made in that review.

## 8. Proposed order, subject to review

1. Fix misleading states and scope expectations, including the Overview gateway error.
2. Make project-scoped management and selected cross-client additions work as clear flows.
3. Strengthen gateway policy: newly discovered tools, unknown projects and denial of subsequent
   calls in existing sessions. Assess secret storage and authentication alongside these flows.
4. Measure speed on representative large setups, then polish the remaining UI friction.

This is a product sequence, not permission to defer a confirmed security defect. The next
review should decide which findings block release and which are optional scope expansion.

## 9. Request for the next reviewer

Review this brief against the repository and the owner's goals before proposing changes.
Do not implement changes as part of this review.

Please return:

1. A verdict on each finding F1–F9: confirmed, partly confirmed, rejected, or unresolved.
   Cite the code or a concrete reproduction and explain corrections.
2. A distinction between current bugs, documented limitations, UX gaps and new product scope.
3. A security assessment of the exact gateway boundary, including new tools, unknown projects,
   active sessions, direct routes, credentials and backups. Avoid absolute safety claims.
4. The smallest useful next release for the owner's three goals, with priorities and things
   deliberately left for later.
5. Concrete acceptance checks for the recommended work. Separate local fixture checks from
   real-client checks and keep all test settings in sandbox homes.
6. Open questions that genuinely require the owner's decision rather than routine engineering
   judgment. Do not propose options without a clear user need.

Read [AGENTS.md](../../AGENTS.md), [design rules](../design.md),
[development rules](../development.md), [README](../../README.md) and
[ROADMAP](../../ROADMAP.md) first. Preserve the preview, backup, verification and Undo contract.
For changing facts about clients or gateways, use their official docs and record the check date.
