# Contract: the plugin package

One folder, `plugins/kitden/`, installed by Claude Code and Codex from two marketplace files in
the repository root. Cursor gets only the server entry, through a link.

## Marketplace files

`.claude-plugin/marketplace.json` (Claude Code):

```json
{
  "name": "kitden",
  "description": "See what your coding agents load. Change it with confidence.",
  "owner": { "name": "Konstantin Starovoytov" },
  "plugins": [
    {
      "name": "kitden",
      "source": "./plugins/kitden",
      "description": "Ask what your coding agents load; open the Kitden page"
    }
  ]
}
```

`.agents/plugins/marketplace.json` (Codex):

```json
{
  "name": "kitden",
  "plugins": [
    {
      "name": "kitden",
      "source": { "source": "local", "path": "./plugins/kitden" },
      "policy": { "installation": "AVAILABLE" }
    }
  ]
}
```

## Plugin files

| File | Content |
| --- | --- |
| `.claude-plugin/plugin.json` | `name` `kitden`, `displayName` `Kitden`, `version` = package version, `description`, `author`, `homepage`, `repository`, `license`, `keywords` |
| `plugin.json` | `$schema` `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`, `name` `kitden`, `version` = package version, `description`, `author`, `homepage`, `repository`, `license` |
| `.mcp.json` and `mcp.json` | identical: `{"mcpServers": {"kitden": {"type": "stdio", "command": "kitden", "args": ["mcp"]}}}` |
| `skills/setup/SKILL.md` | the skill below |
| `README.md` | what the plugin adds, the install line for Kitden itself, how to uninstall |

Not present: `hooks/`, `commands/`, `bin/`, `agents/`, scripts (FR-010).

## The skill

Frontmatter: `name: setup`; `description`: "Use when the user asks what their coding agents load,
what is installed or enabled where, why an item loads twice, or wants to open Kitden."

Body, four rules, in this order (FR-009):

1. For questions, call the kitden tools: `show_setup`, `list_findings`, `explain_item`,
   `list_projects`. They are read-only.
2. To open the page, run `kitden open`. It returns at once and prints the link.
3. Never edit client settings files to change the setup. The page previews, backs up and can undo
   every change; send the user there.
4. If the kitden tools are missing, Kitden is not installed. Show the one install line from the
   README and stop.

Under 200 words. Loads as `/kitden:setup` in Claude Code.

## Install, update, remove

| Client | Install | Update | Remove |
| --- | --- | --- | --- |
| Claude Code | `/plugin install kitden --marketplace KonstantinStarovoytov/kitden` (2.1.275+); or `claude plugin marketplace add KonstantinStarovoytov/kitden` then `claude plugin install kitden@kitden` | `claude plugin update kitden@kitden` | `claude plugin uninstall kitden@kitden` |
| Codex | `codex plugin marketplace add KonstantinStarovoytov/kitden` then `codex plugin add kitden@kitden` | `codex plugin marketplace upgrade` refreshes the marketplace; whether the installed plugin follows is checked in the quickstart | `codex plugin remove kitden@kitden` |
| Cursor | the README button or link below | — | remove the `kitden` entry in Cursor's MCP settings, or on the Kitden page |

## The Cursor link

The entry `{"command":"kitden","args":["mcp"]}` encoded with base64 is `eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=`.

- Link: `cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=`
- README button:
  `[![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=kitden&config=eyJjb21tYW5kIjoia2l0ZGVuIiwiYXJncyI6WyJtY3AiXX0=)`

Cursor asks before it writes. A unit test decodes the README link and compares it with
`.mcp.json`.

## Rules

- The server entry runs the installed `kitden` from PATH (research R6). When it is missing, the
  client shows the server as failed and the skill explains the install line.
- The plugin's version equals the package version; both manifests change in the release commit.
- The plugin passes `claude plugin validate --strict`, and so does the marketplace.
