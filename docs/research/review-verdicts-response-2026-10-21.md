# Response to the review verdicts

Date: 2026-10-21. Code baseline: `d33bfaf`.
Status: comparison and review advice. This file does not approve or change the implementation plan.

Inputs: [new verdicts](review-verdicts-2026-10-21.md),
[my earlier conclusions](review-conclusions-2026-10-21.md),
[original brief](product-review-2026-10-21.md), and
[first review](vision-review-2026-10-21.md).
I also checked the current [design](../superpowers/specs/2026-10-21-review-follow-up-design.md)
and the gateway part of its plan because they now resolve some questions left open by the reviews.

## Overall view

The new verdicts are more precise and more useful for choosing a small release than the first
review. They distinguish bugs, existing limits and new scope. Their core findings agree with
my review; the remaining differences concern priority and the strength of product promises.

I accept the proposed starting point: correct Overview, show installation scope before an
action, and make gateway permissions enforceable. This is a useful first release. It does not
complete the owner's wider goal of managing one project across several clients.

## Where I change my assessment

| Point | My assessment now |
| --- | --- |
| F2: saved settings versus live context | Low priority. The Library already qualifies its view. Keep that boundary clear, but a live context inspector is unnecessary for the next release. |
| F3: matching names | A known comparison limit, not automatically a defect. It becomes critical when a bulk action assumes two entries are interchangeable. |
| F9: instructions missing | A gap against the full vision, but added scope rather than a broken current feature. |
| Project Add goes global | An early scope label is a reasonable first fix. Project installation remains a separate management need. |
| Length of my brief | The six requested outputs and detector paragraph made the handoff heavier than needed. A shorter decision list would have served the owner better. |
| Verification | The other reviewer reports broader test coverage. My selected tests did not establish whole-suite health, and I did not measure startup. Those limits should remain explicit. |

The startup finding is useful: version commands can delay reading. My earlier follow-up already
accepted this. The reported 0.01-second fixture read does not establish cold startup speed or
the time until a real user can act. Test counts also do not resolve a product-policy question.

## Where the new proposal is stronger

The first review mainly proposed labels and a batch switch for tools that may write. The new
one adds an explicit allowed set, keeps new tools out, and checks permission before forwarding
later calls. This addresses the mechanism behind the owner's request.

I agree with this change. Names and server labels can help a user select tools; they cannot
prove that every selected tool only reads. A strict allowed set should be described as control
over specific tools, with that limit clear. It should not be presented as proof of read-only
behavior inside an allowed tool.

Checking each call is a sensible way to enforce a new denial in an open session. The promised
boundary should be the next call checked after Apply; it does not cancel work already sent
upstream. Calling it the only possible enforcement is unnecessary: the important point is
that refreshing a displayed tool list alone does not revoke permission.

## What still needs qualification

**Unknown projects cannot be left undefined in a project permission feature.** For example,
global rules may allow editing while Project A denies it. If that session cannot be matched
to A, falling back to global rules permits editing. A strict list alone does not solve this.

However, the current design now explicitly chooses global rules for unknown folders. Section
2.4 describes it, and the owner-decisions section records it as accepted. I therefore treat
this as a defined boundary, not an unanswered question. The UI must not imply that project
restrictions apply when the project cannot be identified. This is a reasonable compatibility
choice if that limit is understood; it is not unconditional project isolation.

**OAuth prevalence is still unproven.** The reviews show a real authentication limitation but
provide no representative sample supporting “most remote servers.” Its priority should follow
the services the owner needs. This does not diminish the need for OAuth for those services.

**The read-only MCP wording remains too broad.** Kitden's own diagnostic tools only read.
Tools exposed from held servers can change data. The distinction is already explicit in
[`GATEWAY_INSTRUCTIONS`](../../src/kitden/mcp_server.py); use it consistently.

**Some criticism refers to an older document state.** The original brief does say the current
implementation targets macOS. It does not plan support for Linux and Windows. Also, ROADMAP
now contains a Planned section linked to a design marked approved; the old Under review
section is gone. The instruction to revert that earlier section is stale. I agree that merely
adding a review did not require a roadmap entry, but that does not justify reverting the
current planning work.

## A concrete issue in the current implementation plan

This is a finding about the proposed implementation, not a new reproduced runtime exploit.

[Gateway plan, Task 4](../superpowers/plans/2026-10-21-follow-up-part2-gateway-contract.md)
defines `is_allowed` as reading settings again and checking that the server state and tool
state are both `on`. It does not require the server to still exist in `settings["servers"]`.

In the current [settings helpers](../../src/kitden/local_gateway/settings.py), an absent rule
means `on`. A missing or unreadable settings file reads as empty. I evaluated the proposed
two-state check with empty settings in memory:

| Condition | Result |
| --- | --- |
| Server exists in current settings | False |
| Proposed server-state and tool-state check allows the call | True |

The current [proxy](../../src/kitden/local_gateway/proxy.py) keeps its tool-to-server mapping
and upstream objects for the session. Thus, as written, the proposed check can still permit
an already-known tool after its server and rules are removed, or after settings become
unreadable. The planned removal action deletes both the server and its rules, so this matters
to an ordinary management action as well as to file errors.

Before implementing Task 4, require that the server still exists and that the current server
and tool policy allows the call. Missing or unreadable settings must refuse upstream calls;
Kitden's own diagnostic tools can remain available. Add focused checks for removal and an
unreadable file after the first tool list, alongside the existing switched-off-tool test.
This is a small correction to the enforcement mechanism, not a reason to expand the release.

One smaller wording issue: the design preserves all currently allowed tools when strict mode
is enabled. That avoids breaking a setup, but “only tools you turned on” suggests each was
selected by the user. The preview should say it preserves the current allowed set and blocks
new tools until reviewed.

## Recommendation

Use the new verdicts as the release-level summary, with the corrections above. Keep the
larger design as staged work rather than treating every review suggestion as a release blocker.
Overview and scope wording can ship separately from the gateway change. Before that gateway
change ships, verify current denials, removed servers, unreadable settings, unknown-project
fallback and Undo in the relevant sandbox and real-client checks.

Project installation and alignment remain part of the owner's stated goal. A clearer global
Add is useful progress, not evidence that project management is no longer needed. Likewise,
the gateway's control over only the traffic routed through it is a technical boundary to
communicate, rather than a new preference question for the owner.

## Verification and changes in this follow-up

I reread the reports, relevant source functions, the current roadmap, and the relevant design
and gateway-plan sections. The small in-memory check above used no client settings, files or
network services. I did not repeat the full test suite or the earlier UI checks. The reported
787 Python and 91 frontend passes remain the other reviewer's results.

Only this response file was added. Source reports, application code, client settings and the
current roadmap were left as found. This is review advice, not implementation authorization.
