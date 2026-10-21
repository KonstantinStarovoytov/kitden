# Kitden: adoption and go-to-market research

Reviewed: 2026-10-18. Status: research and proposals, not approved product changes.

## Recommendation

**Proposal:** launch Kitden as a local companion for developers who use at least two AI coding clients. Lead with a concrete task: understand which setup applies to a project, find the source of an unexpected item, and make a supported change with undo. Keep the first run free of accounts and cloud configuration.

The first commercial question is whether people return when their setup changes. Downloads, stars, and compliments about the interface do not answer that question. Test usage and willingness to pay before building billing or a team service.

Suggested positioning: **“See what your coding agents load. Change it with confidence.”** This is proposed copy, not a claim that every client state is observable. Unsupported state must remain visibly unknown.

## Competitive evidence

These are current maintainer descriptions, not independent runtime verification. No product was installed for this review.

| Project | What the source currently describes | Lesson for Kitden |
| --- | --- | --- |
| [Cross-Code Organizer](https://github.com/mcpware/cross-code-organizer) | Local command-launched dashboard; Claude Code, Codex, OpenCode and DSH; effective context, duplicates, reversible repair, skill copying, plugins/hooks and backups. Cursor remains planned in the reviewed README. | Effective state, duplicates, undo, local UI and one-command startup are already competing features. |
| [AgentShelf](https://github.com/yigitkonur/agentshelf) | Local web UI launched with `npx agent-shelf`; assets across Claude Code, Codex, Cursor and other clients; source preview, copying, conflict handling and undo. | Cross-client UI and Cursor coverage alone do not establish differentiation. |
| [CC Switch](https://github.com/farion1231/cc-switch) | Desktop app focused on provider switching, shared MCP/skills, routing, sessions and usage. Releases and Homebrew installation; MIT license and sponsor placements. | Packaging and a clear task matter. Its broader model/provider workflow is different from Kitden's current scope. Sponsor placements show a possible business mechanism, not verified income. |

**Important correction:** the project brief's older comparison understates current Cross-Code Organizer coverage. Do not reuse “plugins + Cursor = unique” in marketing. AgentShelf also overlaps that claim. The brief was not edited during this research.

**Differentiation hypothesis:** the clearest explanation of a real cross-client setup, attractive usable design, accurate source/scope relationships, and a smaller set of trustworthy reversible actions. This needs user comparison, not a novelty slogan. Gateway handoff is a secondary workflow; leading with “gateway” would misrepresent the current local companion.

Do not promise a percentage of context savings. A setup entry can be available without being loaded into the model's current context. Any future saving claim needs a stated client/version, measurement method and before/after test.

## Who to recruit first

**Proposal:** developers on macOS who actively alternate between two or more supported clients, have added skills/plugins/MCP servers, and have recently been confused by what is enabled or inherited. Prefer people with a real current issue over people collecting AI tools.

Avoid starting with everyone who uses an AI assistant, enterprise admins, or users who only need to switch a model provider. Those groups have different jobs and support costs.

## The demonstration

Record a 45–60 second demonstration with fictional or sanitized paths:

1. Open the same project in the Kitden client comparison.
2. Show an unexpected item and its exact source and scope.
3. Explain one real conflict or duplicate supported by the client rules. An item present in two separate clients is not automatically a harmful duplicate.
4. Preview a supported change; Apply; show the result; Undo.
5. End with the install route and supported client versions.

Demonstrate the actual working release. Keep an optional hosted sample UI clearly labeled “demo data”; it cannot inspect a visitor's computer. Never put private configuration or secret values in screenshots.

The landing page needs one main action, a short demo, the three supported clients, a compatibility table, read-only-first behavior, privacy boundaries, and uninstall/update instructions. A precise limitation is more useful than “works with every agent.”

## Separate discovery, delivery, hosting and payment

| Job | Proposed starting point | What it does not do |
| --- | --- | --- |
| Explain the product | A small website with demo, documentation and compatibility | Cannot read the visitor's OS configuration by itself |
| Deliver a version | GitHub Releases plus the selected package/install route | Does not create demand on its own |
| Help people discover it | Relevant communities, technical writeups, Show HN, later Product Hunt | Does not replace installation or payment |
| Run the application | Local component and browser UI | Does not require a hosted inventory database |
| Charge for value | Separate checkout/licensing once an offer is validated | Does not justify collecting local inventory |

[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) supports versioned release notes and downloadable binaries. Download counts are delivery metrics; they are not active-user counts.

## First 10–30 users: proposed sequence

The numbers below are experiment sizes, not a growth forecast or benchmark.

1. **First five:** observe a first run on a real setup, with consent. Ask the person to explain what they learned before offering help. Record install failures, inaccurate inventory, time to the first useful finding, and whether undo restored the intended state. Do not collect raw configuration files by default.
2. **Next five to ten:** offer the improved build to people with the same concrete problem. Use short human conversations and relevant community posts by the owner. Ask what they currently do instead, and what would make them stop using Kitden.
3. **Ten to thirty:** release a public beta with demo, release notes, issue template and tested compatibility. Track which discovery channel produces a successful first run, using voluntary feedback or explicit opt-in measurement.
4. **Return check:** after a real trigger such as installing a plugin, switching clients or changing projects, ask whether they reopened Kitden and completed the task without help. Weekly activity is not automatically the right metric for an occasional utility.
5. **Commercial check:** show a concrete paid offer to users with repeated value. Record actual purchases or commitments separately from hypothetical interest. Do not require a payment system to learn whether the offer is useful.

Suggested decision gate before a wider launch: several people can install without live assistance; several find a useful explanation on their own setup; supported writes and undo work in the tested matrix; at least some return for a second real task. These are proposed criteria, not existing results.

No outreach, launch submission or public post was made as part of this research.

## Channels and current rules

| Channel | Appropriate use | Evidence and limits |
| --- | --- | --- |
| GitHub | README demo, releases, issues, transparent compatibility and changelog | Useful for evaluation and trust. Public source requires an explicit license decision; public binaries can have a separate distribution policy. |
| Cursor community Showcase | Explain a specific Cursor-related setup problem and show the working solution | [Forum guidelines](https://forum.cursor.com/guidelines) welcome relevant projects, ask creators to contribute beyond promotion and disclose financial interest. Entirely AI-generated posts may be removed; use owner-reviewed, personal writing. |
| Show HN | A working tool that readers can immediately try | [Official rules](https://news.ycombinator.com/showhn.html) exclude sign-up-only pages and favor low-friction trials. The maker should be present to discuss the work. Do not solicit votes or comments from friends. |
| Product Hunt | A later, prepared visual launch after the first useful beta | [Official guide](https://www.producthunt.com/launch) supports self-submission; no outside hunter is needed. [Launch guidance](https://help.producthunt.com/en/articles/17350772-launch-guide) recommends demo media and a maker explanation. No asking for upvotes or rewarding votes. |
| Relevant user communities and small creator demos | Specific tutorials and comparisons that solve real setup tasks | Check each community's current rules before posting. Do not mass-DM, automate comments or use other projects' issues as ad space. |

Proposed useful articles: “Which skills does this project load in each client?”, “Why the same setup appears in two places”, and “Change a coding-agent plugin and undo it safely.” Publish only examples the release can substantiate. This is a narrow learning loop, not a plan to flood search with generated content.

## Commercial patterns worth considering

**Fact:** [Bruno](https://www.usebruno.com/pricing), a local developer tool in a different category, offers a free open-source edition and paid editions with integrations, support and organization features. Reviewed prices were $6 and $11 per user/month billed annually. These demonstrate a packaging pattern, not Kitden willingness to pay or an appropriate price for an occasional utility.

**Proposal:** make the initial local beta easy to try. Test paid individual convenience or supported releases only after repeated demand. A one-time license with a clear update period is worth comparing with annual updates; avoid a lifetime-update promise while client formats change frequently. Pricing and license enforcement remain separate decisions.

**Later hypothesis:** teams may pay for a known-good setup, support and change review. This is outside the first-release scope and overlaps vendor management features. Validate demand before expanding into hosted team inventory or recurring per-seat billing.

Do not charge extra to undo a change Kitden made. Do not sell “security” or guaranteed token savings without evidence. Do not mistake open-source license selection, a marketplace listing, or attractive screenshots for proof of a business.

## Unresolved

- Which released Kitden workflow users prefer over CCO and AgentShelf in a hands-on comparison.
- Whether the app is an occasional troubleshooter or a frequently used setup workspace.
- Which install route succeeds for the intended audience without support.
- Whether individual users will pay for ongoing compatibility; no revenue forecast is justified yet.
- Final public-source/commercial policy, payment provider and publication readiness are separate decisions.

