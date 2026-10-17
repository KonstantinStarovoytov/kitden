# Research: Agent setup inventory and safe controls

**Feature**: [spec.md](spec.md) | **Date**: 2026-10-17 | **Phase**: 0

Three research tasks ran on 2026-10-17: Cross-Code Organizer (CCO) evaluation, client loading and
write rules, and technical stack. Facts were checked against official docs, changelogs, source
code, package registries and local CLI help output. Local tests used temporary copies only; no real
client configuration was changed. Items marked UNVERIFIED came from bundled code or observation.

Installed client versions on the owner's Mac: Claude Code 2.1.283 (latest 2.1.302), Codex CLI
0.159.2 bundled in ChatGPT.app 26.928.40906 (latest 0.163.0), Cursor 3.21.16 with bundled
agent CLI 2026.09.02 (latest 2026.10.08).

## R1. Own tool or contribution to Cross-Code Organizer

- **Decision**: Build an own tool. Use CCO (MIT) as a reference with attribution, not as a base.
- **Rationale**:
  - Coverage of our 38 requirements: about 3 covered, 18 partial, 15 missing, 2 in conflict.
    The conflicts are core: CCO's MCP server returns secret values and has destructive tools.
  - CCO's config-key writes have no backup, verification or stale-file check, and a parse failure
    of `~/.claude.json` can overwrite the whole file.
  - One maintainer; outside pull requests are usually re-implemented rather than merged; the npm
    release of v0.20.0 failed, so `npx` still serves v0.19.3 (2026-04-28).
  - Our trust requirements would mean redesigning CCO's core.
- **Reuse with attribution**: adapter shape (`src/harness/interface.mjs`), loopback Host and Origin
  guard (`isTrustedLocalRequest`), fingerprint and transaction undo design
  (`src/control-plane-operations.mjs`), Claude and Codex project discovery.
- **Alternatives considered**: contribute a Cursor adapter and plugin support to CCO (rejected for
  the reasons above); revisit if CCO adds a read-only MCP mode, secret masking, safe config writes
  and a second maintainer.
- **Owner decision, optional**: whether to report the CCO bugs found (file overwrite, secrets in
  MCP output, partial skill undo) upstream.

## R2. Language, runtime and distribution

- **Decision**: Python 3.14 (minimum 3.13), packaged with `uv`. Start with `uvx <tool>`; install
  with `uv tool install` to get a stable absolute path for client MCP configs.
- **Rationale**: the owner's daily language; a fresh Mac needs only `uv`, which downloads Python;
  `tomlkit` is the most mature format-preserving TOML editor (Codex config); the official MCP SDK
  2.x supports the current spec in both stacks; Starlette and Uvicorn already come with the MCP SDK.
- **Alternatives considered**: TypeScript on Node with `npx`. Better JSON-with-comments editing
  (`jsonc-parser`), but needs Node installed and weaker TOML editing; `npx` paths are fragile in
  GUI clients. Would be preferred only if we contributed to CCO.
- **Known gap**: Python has no mature JSON-with-comments editor. Mitigation: the files we write are
  strict JSON (Claude Code settings, `~/.cursor/mcp.json`); use client CLIs where they exist; edit
  JSON with a small, property-tested span splicer that changes only the target bytes.

| Purpose | Choice (version on 2026-10-17) |
| --- | --- |
| Runtime | Python 3.14.8, uv 0.13.1 |
| MCP server | `mcp` 2.3.0 (`MCPServer`, stdio) |
| TOML | `tomlkit` 0.15.2 for edits, stdlib `tomllib` for strict reads |
| JSON | stdlib `json` for reads, own span splicer for edits |
| Web | `starlette` 1.8.0, `uvicorn` 0.54.0 |
| File watching | `watchfiles` 1.3.0 (FSEvents on macOS) |
| Tests | `pytest` 9.1.1, `hypothesis` 6.170.1, `syrupy` 6.1.1 |

## R3. Where each client keeps its setup, and what wins

| Client | Sources (scope) | Collision rule |
| --- | --- | --- |
| Claude Code CLI | MCP: `~/.claude.json` `projects.<path>.mcpServers` (local), `.mcp.json` (project), `~/.claude.json` `mcpServers` (user), managed files, plugin `.mcp.json`, claude.ai connectors. Settings: managed > `.claude/settings.local.json` > `.claude/settings.json` > `~/.claude/settings.json`. Plugins: `~/.claude/plugins/{installed_plugins.json, known_marketplaces.json, cache/, synced/}` and `enabledPlugins`. Skills: managed, `~/.claude/skills`, `.claude/skills`, plugins, `~/.claude/skills/synced/` | MCP: whole entry from the winning source (managed > local > project > user > plugin > connectors). `enabledPlugins`: highest source naming the id wins. Hooks: all run. Skills: enterprise > personal > project |
| Claude Desktop Code tab | Same as Claude Code, plus `claude_desktop_config.json` | That file wins on a name clash |
| Codex (CLI and app) | `~/.codex/config.toml` (user), `.codex/config.toml` from repo root to cwd (trusted projects only), profiles, cloud-managed, `/etc/codex`. Keys: `[mcp_servers.<id>]`, `[plugins."name@mkt"] enabled`, `[marketplaces.<n>]`, `[[skills.config]]`, `[projects."<path>"] trust_level`. Skills: `.agents/skills`, `~/.agents/skills`, deprecated `~/.codex/skills`, `/etc/codex/skills`, plugins | **Field-by-field merge** across layers (verified with a temporary `CODEX_HOME`). Same-name skills both appear |
| Cursor (IDE and `agent` CLI) | MCP: `~/.cursor/mcp.json`, `.cursor/mcp.json`, plugins, team. Skills: `.cursor/skills`, `.agents/skills`, `~/.cursor/skills`, `~/.agents/skills`, plugins. Plugins: `~/.cursor/plugins/{cache,marketplaces,local}`; installed set in the IDE state database. Hooks: enterprise > team > `.cursor/hooks.json` > `~/.cursor/hooks.json` > Claude settings hooks | MCP: project wins. Hooks: all run. Agents: `.cursor/agents` wins over Claude and Codex agents |

**Cross-client reading (on by default):**

- Cursor reads `.claude/skills`, `.codex/skills`, `~/.claude/skills`, `~/.codex/skills`, Claude and
  Codex agent folders, Claude settings hooks and Claude Code plugins
  (`installed_plugins.json` plus `enabledPlugins`; UNVERIFIED, from bundled code). Switch:
  Settings → Agents → Third-Party Imports. Observed on the owner's Mac: superpowers listed twice.
- Codex reads the shared `.agents` skills and Claude-format marketplaces and manifests; `/import`
  and desktop auto-sync **copy** Claude Code and Cursor setups, which can create duplicates.
- Claude Code reads `AGENTS.md` when there is no `CLAUDE.md`; it does not read other clients'
  skill folders (documented).

## R4. Write mechanisms for the first release

> **Updated by R13 (gateway first):** the first release no longer adds, enables or disables
> individual MCP servers in client files. Of the MCP rows below, only "add" (used for the gateway
> entry and the setup server) and "remove" (old direct entries) are still used. The on/off rows and
> spikes S2 and S3 are kept as research findings only. The current source of truth is
> [contracts/write-matrix.md](contracts/write-matrix.md).

| Client | Action | Mechanism | Verify | Status |
| --- | --- | --- | --- | --- |
| Claude Code | MCP add/remove (user, local) | `claude mcp add-json -s <scope> <name> '<json>'`, `claude mcp remove -s <scope> <name>` | Re-read `~/.claude.json` | v1 write |
| Claude Code | `.mcp.json` server on/off | `disabledMcpjsonServers` / `enabledMcpjsonServers` in `.claude/settings.local.json` (documented) | Re-read settings | v1 write |
| Claude Code | User or local MCP on/off | No CLI. Candidates: `deniedMcpServers` in `~/.claude/settings.json` (documented, hot-reloaded) or app-owned `disabledMcpServers` in `~/.claude.json` | — | **Spike S3** |
| Claude Code | Plugin on/off | `claude plugin enable|disable <id> -s <scope> --json` | `claude plugin list --json` | v1 write. 2.1.283 can exit before its write finishes (fixed in 2.1.302): always verify |
| Codex | MCP add/remove/on-off, plugin on-off | Own format-preserving edit of `~/.codex/config.toml` (`mcp_servers.<id>`, `.enabled`, `plugins."x@y".enabled`) | `codex mcp list --json` (redact), `codex plugin list --json` | v1 write; restart notice. Not `codex mcp add`: it drops comments in `[mcp_servers]` |
| Codex | Desktop app overwriting outside edits while running | Unknown | — | **Spike S4** |
| Cursor | MCP add/remove (user, project) | Edit `~/.cursor/mcp.json` or `.cursor/mcp.json` (plain JSON); secrets as `${env:NAME}` | Re-read file | v1 write; restart notice |
| Cursor | MCP on/off | IDE state database vs CLI `~/.cursor/projects/<slug>/mcp-disabled.json` | — | Read-only; **Spike S2** |
| Cursor | Plugin on/off | IDE state database `cursor.plugins.installedIds.*`; CLI code uses `.cursor/settings.json` `plugins.<name>.enabled`; changelog says `enabled_plugins` | — | Read-only; **Spike S1** |
| All | Install, update, move plugins; add marketplaces | Show only: `claude plugin install`, `codex plugin add`, `agent plugin marketplace add`, and similar | — | Show command (FR-029) |

**Environment variable references for secrets**: Claude Code `${VAR}` and `${VAR:-default}` in
command, args, env, url and headers; Codex `env_vars`, `bearer_token_env_var`, `env_http_headers`;
Cursor `${env:NAME}`.

**Machine-readable listing**: `claude plugin list --json`, `claude plugin marketplace list --json`,
`codex mcp list --json`, `codex mcp get <n> --json`, `codex plugin list --json`,
`agent plugin marketplace list --format json`. `claude mcp list` and `agent mcp list` have no JSON
output; read the files instead.

**Restart or reload**: Claude Code hot-reloads settings files; plugin changes need
`/reload-plugins` or a new session; MCP edits in `~/.claude.json` assume a new session. Codex and
Cursor: restart after config edits.

## R5. Reading the Cursor state database

- **Decision**: read the Cursor IDE state database (SQLite) in read-only mode, querying only an
  allowlist of non-secret keys: `cursor.plugins.installedIds.*`, `cursor/approvedProjectMcpServers`,
  `cursor/disabledMcpServers`, `workbench.customize.primitiveSourceSnapshot.{mcps,skills}.v3`.
  Never query `mcpOAuth.*` or `secret://` keys. Label snapshot data as "may be stale".
- **Rationale**: Cursor's plugin and MCP state is only in this database; FR-005 requires labeling
  rather than hiding it; an allowlist keeps FR-006.
- **Alternatives considered**: skip the database and label all Cursor plugin state "unknown"
  (fallback if the read proves unstable).

## R6. Local web page security

- **Decision**: bind to `127.0.0.1` only; per-start 32-byte random token printed in the start URL,
  exchanged for an HttpOnly, SameSite=Strict cookie, then redirected to a clean URL; allow only
  `Host` values `127.0.0.1:<port>` and `localhost:<port>`; for every state-changing request require
  an exact same-origin `Origin`, `Sec-Fetch-Site: same-origin` when present, and a custom request
  header; send no CORS headers; GET never changes state; same checks on any WebSocket or SSE
  handshake; CSP `default-src 'self'; frame-ancestors 'none'`; no CDN assets; redact secrets on
  the server before anything reaches the browser.
- **Rationale**: a page that can write client configs is a target for DNS rebinding and
  cross-site requests from other tabs. Follows the MCP transport security guidance, OWASP CSRF
  guidance, and Jupyter's token model. CCO checks Host and Origin but has no token.
- **Alternatives considered**: Host and Origin checks only (CCO model), rejected because any local
  process or same-browser page could still call write endpoints in some cases.

## R7. Safe write pattern

- **Decision**:
  1. Preview: read bytes; record SHA-256, mode, size, mtime and inode; build new bytes with a
     minimal edit; show a masked diff.
  2. Apply: resolve symlinks to the real path; refuse files with more than one hard link; re-hash
     and abort if changed since preview (FR-016).
  3. Back up the original bytes to `~/Library/Application Support/<tool>/changes/<UTC>-<id>/`
     with a manifest (paths, hashes, mode, client version, no secrets); directories 0700, files
     0600; retention: the larger of 30 days and the last 100 changes.
  4. Write a temp file in the same directory (`O_EXCL`, original mode), `F_FULLFSYNC` on macOS,
     then `os.replace`.
  5. Verify: re-read and parse; check the target value; check bytes outside the edited span are
     unchanged; where a client CLI exists, confirm with it. On mismatch, restore atomically.
  6. Undo: restore only if the current hash equals the post-apply hash; otherwise warn and stop.
- **Rationale**: meets FR-015 to FR-020 and constitution principle III; protects symlinked
  dotfiles and concurrent client writes.

## R8. File watching

- **Decision**: `watchfiles` on parent directories, debounced; events trigger a rescan; the
  tool's own writes are ignored by comparing hashes.
- **Rationale**: renames replace inodes, so watching single files misses changes.

## R9. Read-only MCP server

- **Decision**: stdio server built with `mcp` 2.x, exposing read-only tools only, all marked
  `readOnlyHint: true`, returning the same redacted model as the page. Clients launch it through
  the absolute path from `uv tool install`. Registration per client uses the R4 mechanisms
  (Claude CLI, Codex TOML edit, Cursor JSON edit) after confirmation (FR-032).
- **Rationale**: GUI clients may not inherit the shell `PATH`; stdio opens no network port.
- **Note**: test the handshake with each real client; some may still use spec revision 2025-11-25.

## R10. Testing

- **Decision**:
  - Fixtures: real configs copied per client version, with secrets replaced by sentinel strings;
    assert sentinels never appear in page responses, the change log or MCP output (SC-004).
  - Property tests (`hypothesis`): no-op edits keep bytes identical; apply then undo restores
    identical bytes (SC-003); an edit changes only its target span.
  - Edge tests: file changed between preview and apply, rename-based writers, symlinks.
  - Local contract tests against pinned real clients with isolated homes (`CODEX_HOME`; temporary
    `HOME` for Cursor; `CLAUDE_CONFIG_DIR` behavior for `~/.claude.json` UNVERIFIED).
  - CI runs fixture and property tests only.

## R11. Supported client versions (first release)

| Client | Minimum | Tested | Version command |
| --- | --- | --- | --- |
| Claude Code | 2.1.283 (verify-after-write required) | 2.1.302 | `claude --version`; Desktop Code tab via its bundled folder or `/status` |
| Codex CLI and app | 0.159.2 | 0.163.0 | `codex --version` (bundled at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex` when not on `PATH`) |
| Cursor IDE and agent CLI | 3.21.16 / 2026.09.02 | 3.21.16 / 2026.10.08 | `.../Cursor.app/Contents/Resources/app/bin/cursor --version`, `agent --version` |

Unknown formats in newer versions make affected items "unknown" and block writes (FR-034 edge
case, constitution V).

## R12. Spikes that come first in tasks

| Spike | Question | Unblocks |
| --- | --- | --- |
| S1 | Where Cursor stores plugin on/off; does a write survive restart and team sync? | Cursor plugin toggles (FR-028) |
| S2 | Is Cursor IDE `disabledMcpServers` shared with the CLI's `mcp-disabled.json`; what restart is needed? | Not needed after R13 (MCP on/off moved to the gateway) |
| S3 | Claude user/local MCP off: `deniedMcpServers` in settings vs app-owned `disabledMcpServers` | Not needed after R13 |
| S4 | Does the running Codex desktop app overwrite outside edits to `config.toml`? | Safe Codex writes while the app runs |
| S5 | Where Cursor stores the Third-Party Imports switch | Cross-loading accuracy for Cursor (FR-012) |

## R13. Gateway first for MCP tools

- **Decision** (owner, 2026-10-17): MCP tools are managed in an existing MCP gateway (Obot or
  MetaMCP). The tool connects the gateway to every client once, flags MCP servers that bypass it,
  and can remove old direct entries. It does not add or toggle individual MCP servers in client
  files.
- **Rationale**: the 2026-10-16 trial showed that turning a tool off in the gateway hides it from
  clients, and MetaMCP blocked direct calls even from sessions opened earlier. One gateway entry per
  client means fewer writes to client files and removes spikes S2 and S3.
- **Limits**: a gateway cannot reach MCP servers bundled in plugins or local servers that need the
  laptop (for example computer use or local apps); these stay direct and are flagged. Plugins,
  skills, hooks and marketplaces remain local and are still handled by this tool.
- **Costs**: Obot needs a Docker socket or Kubernetes and stores credentials unencrypted unless an
  encryption provider is set; MetaMCP's published image is ten months old. Each client logs in to
  an OAuth gateway itself; the Codex login waits only a few minutes
  ([gateway trial](../../docs/research/gateway-trial-2026-10-16.md)).
- **Alternatives considered**: gateway optional with per-client MCP toggles (the previous plan);
  rejected by the owner as unnecessary file editing when a gateway already controls tools.

## Sources (accessed 2026-10-17)

- CCO: https://github.com/mcpware/cross-code-organizer (commit `39cf32f`)
- Claude Code: https://code.claude.com/docs/en/mcp, /settings, /plugins/loading, /plugins/cli-reference,
  /skills, /hooks, /desktop; https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md (2.1.302)
- Codex: https://developers.openai.com/codex/config-reference, /mcp, /skills, /plugins;
  https://learn.chatgpt.com/docs/import; https://github.com/openai/codex (rust-v0.163.0;
  `codex-rs/core-plugins/src/marketplace.rs`, `codex-rs/ext/skills/src/host_roots.rs`)
- Cursor: https://cursor.com/docs/mcp, /docs/cli/mcp, /docs/plugins, /docs/skills,
  /docs/reference/third-party-hooks, /docs/cli/changelog (2026.10.08)
- MCP: https://modelcontextprotocol.io/specification/versioning;
  https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices
- Security: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html;
  https://jupyter-server.readthedocs.io/en/latest/operators/security.html
- Libraries: https://pypi.org (mcp, tomlkit, starlette, uvicorn, watchfiles, pytest, hypothesis,
  syrupy); https://github.com/python-poetry/tomlkit; https://docs.astral.sh/uv/
- Apple `fsync`: https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html
