# Independent review of the project brief

Date: **2026-10-17**. Reviewed document: [project brief](../project-brief.md) as of 2026-10-17.
Two reviewers ran in parallel with the same prompt and no access to each other's results:
Claude Opus and Claude Fable. Both were told to verify claims against primary sources,
steelman the case against building, and give kill criteria and cheap experiments.
Claude then re-checked the points where they disagreed or contradicted the brief.

## Scores (1 = worst, 5 = best)

| Dimension | Opus | Fable | Agreement |
| --- | --- | --- | --- |
| Feasibility and worthwhileness | 2 (4 if narrowed) | 3 | Both: the full scope is too wide for one developer |
| Overlap with Obot (higher = less overlap) | 4 developer / 2 team | 4 developer / 2 team | Same |
| Novelty | 2 | 2 | Same |
| Usefulness | 2 | 3 | Both: real pain, small audience, comes in episodes |
| Value: owner's daily work | 3 | 3 | Same |
| Value: interview portfolio | 3 | 4 | Opus: "why not CCO?" will be asked |
| Value: small team | 2 | 2 | Same: vendors and Obot own this |
| **Verdict** | **Build with changes** | **Build with changes** | Same |

## What both reviewers agree on

- The pain is real and new: in 2026 the clients started reading each other's skills, plugins,
  hooks and marketplaces, so "what actually loads where, and what loads twice" became confusing.
- The brief is too wide. Both would **cut**: moving plugins, the Langfuse switch, the hook-based
  sync plugin, Claude Desktop account-side state and the team server.
- Both would **keep**: an inventory with provenance (which file or scope each item comes from),
  effective state per project, duplicate and cross-loading detection, reversible toggles through
  the vendors' own CLIs, and a read-only "show my setup" MCP tool, added as a plain MCP server.
- Hidden writes at every session start conflict with the brief's own anti-goals.
- The original interview incident (a folder missing from `@`) is not solved by the brief.
- Run cheap experiments before writing a specification.

## Competitors the brief missed (verified by Claude on 2026-10-17)

| Tool | What it does | What it lacks | Evidence |
| --- | --- | --- | --- |
| **Cross-Code Organizer (CCO)** | Local web dashboard started with `npx`. Claude Code, Codex CLI, OpenCode, DeepSeek Harness. Shows what Claude Code actually loads per project, finds and repairs duplicates, moves items, disables MCP servers per project, undo for every action, git-backed backups, security scan. MIT, 383 stars, pushed 2026-10-16 (v0.20.0) | Cursor and Claude Desktop ("planned"), plugin and marketplace management | [repo](https://github.com/mcpware/cross-code-organizer) |
| mTarsier | Desktop app (Tauri): MCP servers and skills across about 15 clients with backups and rollback. MIT, 50 stars, last push 2026-04-20 | Plugins, marketplaces, project scope | [repo](https://github.com/mcp360/mTarsier) |
| Claude Code Tool Manager | GUI with per-project toggles for MCP, skills, agents, hooks; syncs MCP to Codex and Cursor. 382 stars, last push 2026-07-17 | Plugins, marketplaces, Claude Desktop | [repo](https://github.com/tylergraydev/claude-code-tool-manager) |
| Codex `/import`, Claude Code `/import` | Vendors import each other's setups; Codex desktop can keep imports in sync | No "what is installed where" view | [Codex import](https://learn.chatgpt.com/docs/import), [Claude Code commands](https://code.claude.com/docs/en/commands) |
| Microsoft APM | Desired-state push of plugins, MCP servers, marketplaces with a lockfile | No inventory of what clients really load | [repo](https://github.com/microsoft/apm) |

**Conclusion:** the brief's statement "no local tool shows and changes these items across the four
clients" is literally true but misleading. CCO already covers a large part of the first release
for Claude Code and Codex. The open gap is narrower: **Cursor + plugins and marketplaces +
cross-client loading ("who loads what twice") in one page.**

## Disputed facts, resolved

| Claim | Opus | Fable | Claude's check |
| --- | --- | --- | --- |
| Codex reads Claude and Cursor marketplace manifests | Verified | Not supported | **True on the Codex main branch**: `MARKETPLACE_MANIFEST_RELATIVE_PATHS` includes `.claude-plugin/marketplace.json` and `.cursor-plugin/marketplace.json` ([source](https://github.com/openai/codex/blob/main/codex-rs/core-plugins/src/marketplace.rs)). Fable relied on OpenAI's plugin *submission* guide, which is a different topic |
| Obot Sentry inventory works | Docs say beta inventory | Docs vs README conflict | **README says inventory collection is "currently stubbed out"**: scans send an empty manifest ([README](https://github.com/obot-platform/obot-sentry)) |
| Codex plugin on/off state is undocumented | Outdated | Outdated | **Mostly outdated**: `[plugins."name@marketplace"] enabled` lives in `config.toml` (seen on the owner's machine). Some curated app plugins still have no local entry |
| Cursor plugin state is undocumented | CLI documented, IDE unverified | Undocumented | **Partly documented**: the Cursor CLI changelog adds `enabled_plugins` in `~/.cursor/settings.json` (2026-05-20) and lists Claude Code plugins next to native ones (2026-05-07) ([changelog](https://cursor.com/docs/cli/changelog)). Cursor IDE state is unverified |
| "One switch" to Langfuse | Not one switch: Langfuse takes OTel traces; Codex exports logs and metrics | Unverified | Not re-checked by Claude; treat as a risk |

## Usage evidence (reviewers' sources, not re-checked)

- JetBrains survey (May–July 2026, 15k+ developers): work use of Claude Code 39%, Codex 16%,
  Cursor 12%; no overlap figures. Opus estimate for all three at once: 1–5%.
- Pragmatic Engineer survey (906 respondents, early 2026): 70% use 2–4 AI tools.
  Fable estimate for the three-client overlap: 6–20%.

## Strongest argument against building (both reviewers)

Vendors are making cross-client use native (shared standards, `/import` both ways, Cursor reading
Claude and Codex folders by default). CCO, APM and Obot already cover inventory, desired-state
push and team governance. Writing into four clients that release weekly is a permanent
maintenance cost, and the value shrinks with each vendor release.

## Experiments proposed (each under one day)

| Experiment | Go | Stop |
| --- | --- | --- |
| **Bake-off**: list the owner's 10 most common setup questions and try them with CCO, mTarsier, Claude Code Tool Manager, vendor UIs and `/import --dry-run` | 4 or more frequent tasks remain unsolved | 2 or fewer remain unsolved |
| **Write spike**: toggle a plugin and an MCP server in Cursor IDE, Codex and Claude Code; restart; check persistence and that account sync does not overwrite it | All three are reliable | Cursor fails: drop cross-client control |
| **Inventory script**: about 200 lines that print client, scope, provenance, duplicates and an "unknown" column for the owner's machine | Shows something new and unknowns are under 20% | Output is boring or Cursor state is invisible |

## Options after the review

| Option | Summary |
| --- | --- |
| A. Contribute to CCO | Add a Cursor adapter and plugin and marketplace support to an active MIT project |
| B. Narrow own tool | Read-first explainer for Cursor + Codex + Claude Code: provenance, cross-loading, duplicates, a few safe toggles, read-only MCP tool |
| C. Different angle | Testing plugins and skills on datasets with Langfuse across clients (suggested by Opus as stronger for an AI solutions lead); not researched yet |

Decision pending the owner. The bake-off decides between A and B.
