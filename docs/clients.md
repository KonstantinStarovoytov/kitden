# What Kitden relies on in each client

This file lists the facts about Claude Code, Codex and Cursor that Kitden reads or writes. A change to how Kitden reads or writes a client's files updates it in the same pull request.
It was drafted from the code on 2026-11-11. A date in brackets is when the code last checked that fact; no date means the code gives none.
The table shape is fixed, because a daily check reads it. `Source` is a full address, or `help` (the client's own `--help`), `install` (seen on a real install) or `guess`.

## Claude Code

| What | Kind | Files | Seen in | macOS and Linux | Source |
|---|---|---|---|---|---|
| `claude mcp add-json -s user <name> '<json>'` takes the entry as an argument, no stdin or file | command | `src/kitden/clients/claude_code.py` | adding a server (2026-10-22) | same | https://code.claude.com/docs/en/mcp |
| `claude mcp remove -s <scope> <name>` | command | `src/kitden/clients/claude_code.py` | removing a server | same | https://code.claude.com/docs/en/mcp |
| User servers live in `~/.claude.json` under `mcpServers`; local servers under `projects.<path>.mcpServers`; Claude Code rewrites the file in normal use | key | `src/kitden/clients/claude_code.py` | scan, adding and removing a server (2026-10-22) | same | https://code.claude.com/docs/en/mcp |
| Project servers in `<project>/.mcp.json`, approved by `enabledMcpjsonServers`, `disabledMcpjsonServers` and `enableAllProjectMcpServers` in `~/.claude.json` | key | `src/kitden/clients/claude_code.py` | scan | same | guess |
| Update sets only `command` of the user `kitden` entry in `~/.claude.json`, by a direct file edit that checks only that entry, not `claude mcp add-json` (2026-11-12) | key | `src/kitden/clients/base.py`, `src/kitden/clients/claude_code.py` | updating Kitden's own entry | same | guess |
| MCP server types `http`, `stdio`, `sse`, `ws` (the gateway speaks only http) (2026-10-21) | key | `src/kitden/clients/entries.py` | moving a server into the gateway | same | guess |
| `headersHelper` makes a server read values from a helper command (2026-10-21) | key | `src/kitden/clients/entries.py` | moving a server into the gateway | same | guess |
| `claude plugin install <id> -s <scope> --json`, run in the project for `-s project` | command | `src/kitden/clients/claude_code.py` | installing a plugin (2026-10-22) | same | https://code.claude.com/docs/en/plugins/install |
| `claude plugin uninstall <id> -s <scope> --keep-data --json`; it fails while settings still switch the plugin on | command | `src/kitden/clients/claude_code.py` | removing a plugin (2026-10-22) | same | https://code.claude.com/docs/en/plugins/cli-reference |
| `claude plugin enable` and `claude plugin disable <id> -s <scope> --json` | command | `src/kitden/clients/claude_code.py` | turning a plugin on or off | same | help |
| `claude plugin marketplace add <source>` and `remove <name>`; the source is recorded under `extraKnownMarketplaces` in `~/.claude/settings.json` (2026-10-19, version 2.1.283) | command | `src/kitden/clients/claude_code.py` | adding a marketplace | same | install |
| `enabledPlugins` in user, project and local settings; local wins over project over user; set false in the local file to opt out (2026-10-26) | key | `src/kitden/clients/claude_code.py` | scan, plugin on or off | same | https://code.claude.com/docs/en/plugins/loading |
| `~/.claude/plugins/installed_plugins.json` (`plugins.<id>[].installPath`) and `known_marketplaces.json` (`source`, `installLocation`) | path | `src/kitden/clients/claude_code.py` | scan | same | install |
| Plugin ids ending `@synced`, `@inline` or `@skills-dir` have no install to remove | key | `src/kitden/clients/claude_code.py` | scan | same | guess |
| Project and user settings files `.claude/settings.json` and `.claude/settings.local.json` | path | `src/kitden/clients/claude_code.py` | scan, rules for one project | same | https://code.claude.com/docs/en/settings |
| Since 2.1.211 the local file is at the repository root when Claude Code starts in a subfolder (2026-10-27) | path | `src/kitden/clients/claude_code.py`, `src/kitden/changes/actions.py` | rules for one project | same | https://code.claude.com/docs/en/settings |
| `skillOverrides.<skill>` is `on`, `name-only`, `user-invocable-only` or `off`; a missing key is `on`; docs do not say how it merges across files (2026-11-09) | key | `src/kitden/clients/claude_code.py` | turning a skill off | same | https://code.claude.com/docs/en/skills |
| `disable-model-invocation: true` in SKILL.md keeps the description out of context (2026-11-06) | key | `src/kitden/clients/base.py` | skill list | same | https://code.claude.com/docs/en/skills |
| Skills in `~/.claude/skills` and `<project>/.claude/skills`, each a folder with `SKILL.md` | path | `src/kitden/clients/claude_code.py`, `src/kitden/clients/base.py` | scan | same | https://code.claude.com/docs/en/skills |
| Instruction files: `CLAUDE.md`, `CLAUDE.local.md` at the project root, `rules/*.md`, `commands/*.md`, `agents/*.md` in `.claude`, sub-folders too (2026-10-22) | path | `src/kitden/clients/claude_code.py` | scan | same | https://code.claude.com/docs/en/memory |
| Hooks in the `hooks` key of settings files | key | `src/kitden/clients/claude_code.py`, `src/kitden/clients/base.py` | scan | same | guess |
| Claude Desktop Code tab: `claude_desktop_config.json` with `mcpServers`, and bundled versions in a `claude-code` folder | path | `src/kitden/clients/claude_code.py`, `src/kitden/system.py` | scan | differs | install |
| Claude Desktop folder on Linux is assumed to be `~/.config/Claude`; macOS uses `~/Library/Application Support/Claude` (2026-11-03) | path | `src/kitden/system.py` | scan | differs | guess |
| Lowest version tested is 2.1.283, read from `claude --version` | command | `src/kitden/clients/versions.py` | client list | same | help |
| Chat logs at `~/.claude/projects/*/*.jsonl`; entry fields `timestamp`, `version`, `entrypoint`, `cwd`, `isSidechain`, and attachment `type` `skill_listing` with `isInitial`, `skillCount`, `names`, `content` (2026-11-09) | path | `src/kitden/context/claude_log.py` | skill list | same | install |
| A list with `isInitial` false holds only the skills added since the last list, each sent whole outside the limit; the full list is sent again on resume (2026-11-10; checked 2026-11-12, version 2.1.309) | key | `src/kitden/context/claude_log.py` | skill list | same | install |
| The newest list is the one with the latest time in the log, not the newest file (2026-11-12) | key | `src/kitden/context/claude_log.py` | skill list | same | install |
| Skills the Claude app gives Claude Code (`anthropic-skills:docx`) are at `local-agent-mode-sessions/skills-plugin/<org>/<id>/skills/<skill>/SKILL.md` in the app's folder, some copied to `~/.claude/skills/synced/<org>_<id>/`; the newest copy is read (2026-11-12, version 2.1.309) | path | `src/kitden/views/context_view.py` | skill list | differs | install |
| `entrypoint` is `claude-desktop` for the app; `cli` is not confirmed; `sdk*` entries are skipped (2026-11-09) | key | `src/kitden/context/claude_log.py` | skill list | same | install |
| The skill list may use 1% of the window; one description is cut at 1536 characters (2026-11-07) | limit | `src/kitden/context/tables.py` | skill list | same | install |
| Windows by model: 1,000,000 tokens at 3 characters per token for opus-5-5 and fable-5-1; 200,000 at 4 for sonnet-4-6 (2026-11-06). Every chat checks it; a model not listed gets the one window whose limit rebuilds its list, and no model is named on the estimate card | limit | `src/kitden/context/tables.py` | skill list | same | install |
| Skills that always keep their description: dataviz, artifact-design, artifact-diagramming, artifact-capabilities, update-config, keybindings-help, code-review, simplify, fewer-permission-prompts, loop, schedule, claude-api, workflow-authoring, run, plugin-authoring (2026-11-07) | limit | `src/kitden/context/tables.py` | skill list | same | install |
| When the list does not fit: built-ins and name-only skills keep their entry, other skills show a name, descriptions go to the most used (2026-11-07) | limit | `src/kitden/context/rules.py` | skill list | same | install |

## Codex

| What | Kind | Files | Seen in | macOS and Linux | Source |
|---|---|---|---|---|---|
| Settings folder is `CODEX_HOME`, default `~/.codex`; settings in `config.toml` | path | `src/kitden/clients/codex.py` | scan, every write | same | https://learn.chatgpt.com/docs/agent-configuration/agents-md |
| MCP servers in `[mcp_servers.<name>]` of `config.toml` (`command`, `args`, `url`, `enabled`); Kitden edits the file as TOML and keeps comments, not `codex mcp add` | key | `src/kitden/clients/codex.py` | adding and removing a server | same | install |
| Update sets only `command` in `[mcp_servers.kitden]` of `config.toml`; `enabled` and the timeouts stay (2026-11-12) | key | `src/kitden/clients/base.py`, `src/kitden/clients/codex.py` | updating Kitden's own entry | same | install |
| Keys filled in from elsewhere: `env_vars`, `bearer_token_env_var`, `env_http_headers`, `http_headers_helper` (2026-10-21) | key | `src/kitden/clients/entries.py` | moving a server into the gateway | same | guess |
| `codex mcp login <name>` for a server that signs in with OAuth | command | `src/kitden/clients/codex.py` | adding the gateway | same | help |
| `codex plugin add <id> --json` and `codex plugin remove <id>`; that remove deletes the `[plugins."<id>"]` table is assumed (2026-10-22, version 0.163) | command | `src/kitden/clients/codex.py` | installing and removing a plugin | same | help |
| `codex plugin marketplace add <source> --json` and `remove <name>` touch only their own tables in `config.toml` (2026-10-19, version 0.163) | command | `src/kitden/clients/codex.py` | adding a marketplace | same | help |
| `codex plugin list --json` (`installed[].pluginId`, `enabled`) is the only local view of remote plugins; it took 15 seconds on a real Mac (2026-10-20) | command | `src/kitden/clients/codex.py` | scan | same | install |
| `[plugins."<id>"] enabled` in `config.toml`; installs are for the whole environment, none per project (2026-10-22) | key | `src/kitden/clients/codex.py` | plugin on or off, installing | same | https://learn.chatgpt.com/docs/plugins |
| `[marketplaces.<name>]` with `source` and `source_type` (`local` or `git`); git copies at `.tmp/marketplaces/<name>` (2026-10-20, version 0.163.0) | key | `src/kitden/clients/codex.py` | scan | same | install |
| Plugin cache at `plugins/cache/<marketplace>/<plugin>/`, files maybe one version folder down; `.codex-plugin` folder; remote plugins keep `.codex-remote-plugin-install.json` | path | `src/kitden/clients/codex.py` | scan | same | install |
| Plugins can bundle `mcp.json` or `.mcp.json` | path | `src/kitden/clients/codex.py` | scan | same | install |
| `[projects."<path>"] trust_level = "trusted"`; project `.codex/config.toml` and `.agents/skills` count only when trusted | key | `src/kitden/clients/codex.py` | scan | same | install |
| `[[skills.config]]` with `path` of a `SKILL.md` and `enabled = false` turns a skill off; restart Codex (2026-10-26) | key | `src/kitden/clients/codex.py` | turning a skill off | same | https://learn.chatgpt.com/docs/build-skills |
| Skills in `~/.agents/skills` and `~/.codex/skills`; a project reads `.agents/skills` from its folder up to the repository root (2026-10-22) | path | `src/kitden/clients/codex.py` | scan | same | https://learn.chatgpt.com/docs/build-skills |
| Instruction files `AGENTS.override.md` and `AGENTS.md` in `CODEX_HOME` and in project folders (2026-10-22) | path | `src/kitden/clients/codex.py` | scan | same | https://learn.chatgpt.com/docs/agent-configuration/agents-md |
| Codex command is on PATH or at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`; lowest version tested is 0.159.2 | command | `src/kitden/clients/versions.py`, `src/kitden/system.py` | client list | differs | install |
| Session logs at `sessions/<year>/<month>/<day>/rollout-*.jsonl` in the Codex home; `.zst` logs are not opened (2026-11-09) | path | `src/kitden/context/codex_log.py` | skill list | same | install |
| Log lines: `session_meta` payload `timestamp`, `cwd`, `thread_source` (`user`), `cli_version`; `turn_context` payload `model`; a `response_item` with role `developer` holds `<skills_instructions>` (2026-11-09, version 0.163.0-alpha.11) | key | `src/kitden/context/codex_log.py` | skill list | same | install |
| Skill list line shape `- name: description (file: path)`, a roots line names an alias and a folder (2026-11-09) | key | `src/kitden/context/codex_log.py` | skill list | same | install |
| `models_cache.json` holds `models[]` with `slug`, `display_name`, `context_window` (2026-11-09) | path | `src/kitden/context/codex_log.py` | skill list | same | install |
| The skill list may use 2% of the window; one description is cut at 1024 characters (2026-11-06) | limit | `src/kitden/context/tables.py` | skill list | same | guess |
| `skills.max_context_tokens` is at most 10,000 tokens (2026-11-06) | limit | `src/kitden/context/tables.py` | skill list | same | guess |
| A list that does not fit: the roots table is paid first, then the room is shared one character at a time across the skills; read from `codex-rs/ext/skills/src/render.rs` and matched on a real list of 0.167.0 (2026-11-12) | limit | `src/kitden/context/rules.py`, `src/kitden/context/tables.py` | skill list | same | install |
| The newest list is the one with the latest time in the log, not the newest file: the Codex app rewrites an old chat's file when it opens it (2026-11-12, version 0.167.0) | key | `src/kitden/context/codex_log.py` | skill list | same | install |
| `model_context_window` in `config.toml` replaces the window, at most the model's `max_context_window` in `models_cache.json` (2026-11-12) | key | `src/kitden/context/codex_log.py` | skill list | same | https://developers.openai.com/codex/config-reference |

## Cursor

| What | Kind | Files | Seen in | macOS and Linux | Source |
|---|---|---|---|---|---|
| User MCP servers in `~/.cursor/mcp.json` under `mcpServers`, project ones in `<project>/.cursor/mcp.json`; Kitden edits the JSON | key | `src/kitden/clients/cursor.py` | scan, adding and removing a server | same | install |
| Update sets only `command` of the `kitden` entry in `~/.cursor/mcp.json` (2026-11-12) | key | `src/kitden/clients/base.py`, `src/kitden/clients/cursor.py` | updating Kitden's own entry | same | install |
| Server entries list `command`, `args`, `env`, `envFile`, no `cwd` (2026-11-09) | key | `src/kitden/clients/entries.py` | moving a server into the gateway | same | guess |
| A url ending in `/sse` with no type is read as SSE | key | `src/kitden/clients/entries.py` | moving a server into the gateway | same | guess |
| Header placeholder `${env:NAME}` | key | `src/kitden/clients/cursor.py` | adding the gateway | same | guess |
| `state.vscdb` in the Cursor state folder, table `ItemTable` with `key` and `value`, opened read-only | path | `src/kitden/clients/cursor.py`, `src/kitden/system.py` | scan | differs | install |
| Cursor state folder: `~/Library/Application Support/Cursor/User` on macOS; on Linux assumed `~/.config/Cursor/User` as in VS Code (2026-11-03) | path | `src/kitden/system.py` | scan | differs | guess |
| Keys starting `cursor.plugins.installedIds.` (then team, a bar, then workspace) hold installed plugin rows (`id`, `sources` user or project) | key | `src/kitden/clients/cursor.py` | scan | same | install |
| Key `src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl.persistentStorage.applicationUser` holds `thirdPartyExtensibilityEnabled` and `importPluginsFromClaudeOnBoot`, both on by default | key | `src/kitden/clients/cursor.py` | scan | same | install |
| Workspace databases `workspaceStorage/*/state.vscdb`, key prefix `workbench.customize.primitiveSourceSnapshot.` with `descriptors[].pluginId` and `filePath` | key | `src/kitden/clients/cursor.py` | scan | same | install |
| Plugin cache `~/.cursor/plugins/cache/<marketplace>/<plugin>/<version>/`, version a commit-hash folder (2026-10-20); marketplaces in `~/.cursor/plugins/marketplaces` | path | `src/kitden/clients/cursor.py` | scan | same | install |
| Plugins are installed for the user or a project, with no on or off switch; menu words from Cursor 3.21 (2026-10-22) | key | `src/kitden/clients/cursor.py` | scan | same | https://cursor.com/docs/plugins |
| Cursor loads Claude Code plugins, skills and hooks when third-party plugins are on | key | `src/kitden/clients/cursor.py` | scan | same | install |
| Skills in `.cursor/skills`, `.agents/skills`, and with third-party on `.claude/skills` and `.codex/skills`; `disable-model-invocation` keeps the description out (2026-11-09) | path | `src/kitden/clients/cursor.py`, `src/kitden/clients/base.py` | scan | same | https://cursor.com/docs/context/skills |
| Rules are `.mdc` files in `.cursor/rules`, sub-folders too; `AGENTS.md` at the project root (2026-10-22) | path | `src/kitden/clients/cursor.py` | scan | same | https://cursor.com/docs/context/rules |
| `.cursorrules` at the project root is legacy; user rules in `~/.cursor/rules` (extension not documented); rules made in Customize sync with the account and are not files (2026-10-22) | path | `src/kitden/clients/cursor.py` | scan | same | https://cursor.com/help/customization/rules |
| Hooks in `~/.cursor/hooks.json` under `hooks` | key | `src/kitden/clients/cursor.py` | scan | same | guess |
| Cursor command is on PATH or at `/Applications/Cursor.app/Contents/Resources/app/bin/cursor`; lowest version tested is 3.21.16 | command | `src/kitden/clients/versions.py`, `src/kitden/system.py` | client list | differs | install |
| Kitden keeps gateway secrets with `/usr/bin/security` (`add-generic-password -U -X`, `find-generic-password -w`, `delete-generic-password`) on macOS (2026-10-22) and `secret-tool` on Linux (2026-11-03); they hold values for every client | system | `src/kitden/local_gateway/keychain.py`, `src/kitden/system.py` | adding a server with a secret | differs | help |
