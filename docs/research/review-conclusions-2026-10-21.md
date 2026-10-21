# Kitden: conclusions from the two product reviews

Date: 2026-10-21  
Code baseline: `d33bfaf1c88187f23c1935e6654307f438bbcbac`  
Status: review conclusions and proposals. No implementation plan has been approved.

Inputs:

- [Product brief and independent review](product-review-2026-10-21.md).
- [Kitden against the owner's vision](vision-review-2026-10-21.md).

This follow-up checks the second review against the code and compares the two assessments.
The original reports remain available with their original conclusions. This document records
agreements, corrections and open decisions; it does not change application behavior.

## Overall assessment

The second review is useful and concrete. Most of its feature observations are correct. It
adds good detail about version checks, direct MCP copying, removal and UI noise. Its conclusions
about security and product readiness are more confident than the evidence supports.

The reviews agree that Kitden has a strong base: inventory, client comparison, project views,
a local gateway, per-tool switches and reversible changes. The main remaining work is making
the user's project tasks complete and making the gateway's access guarantees precise.

The absence of a read-only button does not mean there is no tool control. Users can already
turn individual tools off. A convenient batch action and a durable access policy are different
deliverables and should be reviewed separately.

## Useful contributions from the second review

### Version checks deserve a startup measurement

`read_command_version()` runs an external command with a 20-second timeout. Its ten-minute
cache lives only in memory. A new process does not retain that cache.

This is a concrete possible startup delay, which the first review did not identify in enough
detail. The timeout is an upper bound, not a measured delay on every launch.

Evidence: [client version reading](../../src/kitden/clients/base.py) and
[command selection](../../src/kitden/clients/versions.py).

Reading version metadata from an app or package may help, but the version must belong to the
client binary actually used. The app shell and an embedded or separately installed CLI can
have different versions. Compare results before replacing the current source. Slow version
discovery should also be assessed separately from reading the user's configuration.

### Direct MCP copying is a distinct user need

Some users want to align client settings without adopting a gateway. The current Library
routes them toward the gateway rather than copying a direct server entry.

That is a valid product gap against the broader management goal. It is not automatically a
reason to add every form of copying: compatibility, project scope, authorization and secret
references still need a preview that explains the result.

Evidence: `_server_why()` in [Library model](../../src/kitden/views/library.py).

### Removal and quiet status reporting matter

A manager should support removing items as well as adding or disabling them. Removal belongs
closer to the core management promise than its low position in the suggested order implies.

An item intentionally configured in several clients is not necessarily a problem. The second
review's observation about repetitive notes is useful. Keep meaningful differences visible;
do not hide all cross-client information simply because some entries are expected.

Evidence: [findings](../../src/kitden/views/findings.py),
[Overview UI](../../src/kitden/web/static/js/overview.js), and [roadmap](../../ROADMAP.md).

## Main disagreement: what a read-only mode can promise

The second review proposes reads/writes labels and a button to turn off writing tools. It
suggests using names such as `write`, `delete` and `update` when annotations are absent, clearly
marking that result as a guess. Marking uncertainty is good, but it does not make the guess a
safe basis for an access guarantee.

For example, a hypothetical `query` or `execute` tool can change data depending on its arguments.
A name without a write verb is not evidence that the tool only reads. A non-destructive tool
can also write, so `destructiveHint: false` is not a substitute for read-only evidence.

Tool annotations come from the server. The MCP specification requires clients to treat them
as untrusted unless they come from trusted servers. Checked against official documentation on
2026-10-21: [MCP tool annotations](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#tool).

Separate these two results:

| Result | What it can honestly promise |
| --- | --- |
| Selection helper | Suggest tools that may change data, show the basis and uncertainty, and let the user review a batch change. |
| Access policy | Enforce a specific allowed set, handle new tools and unknown projects deliberately, and check current denials before forwarding later calls. |

An allowlist controls which tools can be called. It still does not prove that an allowed tool's
implementation is harmless. Where a service supports credentials restricted to reading,
those restrictions provide another useful layer.

## Security conclusions need a narrower scope

The local page has substantial protections: session authentication, origin checks, a custom
request header, a strict Content Security Policy, redaction and private file permissions.
These support a positive assessment of the page's defenses.

They do not establish the security of every gateway policy, upstream server or credential
flow. Three behaviors were missing from the second review's conclusion:

| Behavior confirmed in code | Why it matters |
| --- | --- |
| A tool without a rule is enabled. | A newly discovered write tool may become available when a session uses the updated tool list. |
| Settings and offered tools are kept for a session. | Turning a tool off does not revoke that permission from existing sessions. |
| An unknown project uses global rules. | Failure to identify a restricted project can produce broader access if global rules are more permissive. |

Evidence: `_is_on()` and `allowed_tools()` in
[gateway settings](../../src/kitden/local_gateway/settings.py), `_Gateway` in
[the proxy](../../src/kitden/local_gateway/proxy.py), and
[project resolution](../../src/kitden/local_gateway/project.py).

These are partly documented design choices, not proof of an exploit. They still need explicit
decisions before the product promises a strict read-only or project-restricted mode.

Private plaintext storage being similar to a client's existing storage does not prove that
the risk is unchanged. Central storage, backups and additional processes change where secrets
exist and who can access them. Evaluate that lifecycle rather than asserting "no worse."

Evidence: [backup storage](../../src/kitden/changes/backup.py) and
[gateway transport and process setup](../../src/kitden/local_gateway/proxy.py).

## Corrections to specific claims

| Claim in the second review | More accurate statement | Evidence |
| --- | --- | --- |
| Tokens and headers never leave the Mac. | Management can stay local, but a remote server receives the authentication intended for it. The promise should exclude unrelated recipients, not all network transmission. | `_target()` in [proxy.py](../../src/kitden/local_gateway/proxy.py); `needs_sign_in()` in [actions.py](../../src/kitden/changes/actions.py). |
| The start link is one-time. | The current token can be reused while that page server is running. It is not consumed after use. | `_check()` in [security.py](../../src/kitden/web/security.py). |
| The MCP server for agents is read-only. | Kitden's own diagnostic tools only read. The same gateway can also expose mutating upstream tools. | `GATEWAY_INSTRUCTIONS` in [mcp_server.py](../../src/kitden/mcp_server.py). |
| The effective view proves what really loads. | It computes expected availability from saved settings. It does not observe the current session's context. | [effective_view()](../../src/kitden/views/effective.py). |
| Most remote servers cannot move until OAuth exists. | OAuth support is a real gap, but the report does not establish how many remote servers require it or lack another supported authentication path. | See the official GitHub example below. |
| Moving a server carries the client's tool switches. | This applies on the first move. When updating an already-held server, gateway rules are kept and the client's switches are not carried again. | `local_move_steps()` in [actions.py](../../src/kitden/changes/actions.py). |

The official remote GitHub MCP server documents both OAuth and personal access token access.
That does not prove end-to-end compatibility with Kitden, but it makes the report's broad
conclusion about remote servers insufficiently supported. Checked on 2026-10-21:
[GitHub remote MCP documentation](https://github.com/github/github-mcp-server#remote-github-mcp-server).

The one-time-link claim was checked with an isolated in-memory call to the middleware: the same
valid token produced a 303 redirect and a session cookie twice. No real page token or client
settings were used. This confirms a documentation mismatch; it does not by itself establish
an exploitable vulnerability or a requirement to make the link single-use.

## Important product gap omitted from the second review

Selecting a project filters the view, but adding a plugin or skill still targets global
settings. The review says `Adds for all your projects.`

This is central to the owner's workflow. A user needs to know the scope before choosing an
action. It should rank alongside the read-only workflow and cross-client alignment, rather
than disappear from the next-release discussion.

Evidence: `projectNote()` in [offer.js](../../src/kitden/web/static/js/offer.js) and
`skill_copy_step()` in [client base](../../src/kitden/clients/base.py).

## Performance and test evidence

The second review reports a 0.01-second inventory read on a small fixture setup with version
commands stubbed. The author limits this measurement to reading. It does not measure cold
application startup, real version commands, first installation with uvx, or a large live setup.

The report states that 787 Python tests passed, 9 contract tests were deselected, lint was clean
and 91 frontend tests passed. This is broader reported coverage than the first review's selected
155 Python tests and 91 frontend tests. The full run was not repeated or independently verified
during this follow-up. Deselected contract tests also leave real-client compatibility unproven.

Use the reports' results within those limits. Measure the time to first usable UI and the time
to complete data separately, with slow and unavailable sources included.

## Suggested priorities after comparing both reviews

These are recommendations for review, not changes to the approved Next or Later lists.

1. Fix the confirmed Overview contradiction and make installation scope clear at the action.
   Reduce repetitive notes that do not help the user decide what to do.
2. Define and enforce the gateway's access contract before presenting a strict read-only mode:
   unknown tools, unknown projects, current denials and existing sessions. Keep selection
   guesses separate from permission enforcement.
3. Complete core management flows: selected missing items across clients, removal with Undo,
   and direct MCP copying where the need and supported semantics are clear.
4. Measure startup with real sources and resolve the demonstrated bottlenecks. Verify the
   identity of a version source before changing it.
5. Prioritize Instructions, OAuth and other operating systems using real user needs. OAuth
   may move earlier if the target users' important services require it. Avoid expanding every
   dimension of the product at once.

The missing Overview state is a confirmed bug. Instructions and additional platforms expand
scope. Session policy behavior and global installation are existing limitations that need
product decisions. These categories should not be treated as equally urgent defects.

## Answers to the second reviewer's questions

**Can tool-name heuristics be used?** Yes, as a clearly uncertain selection aid. They should
not silently authorize a tool or justify a claim that all remaining tools only read.

**Should direct MCP servers be copyable?** It is a valid scenario. Preserve secret references
where supported, show when copying would create another stored secret, and explain the new
client and scope in the preview. Keep backup, verification and Undo. Assess each supported
client format rather than allowing arbitrary entry copying.

**Are app-bundle versions reliable enough?** Not established. The version must match the
selected executable and supported format. A tested fast source with a fallback may work;
otherwise reading the version in the background can be safer than guessing it.

## What was changed by this documentation task

This file was added and linked from both source reviews and the roadmap's Under review section.
The source reviews' findings were not rewritten. Application code and client settings were not
changed. These conclusions still need an implementation decision before work starts.
