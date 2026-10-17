# Spike S4: Codex app and outside edits to `config.toml`

Date: 2026-10-17. Codex app (ChatGPT.app, app version 26.928.40906), Codex CLI 0.159.2.
Method: with the app running, we backed up `~/.codex/config.toml` and made an outside edit: a
comment on the first line, and `[plugins."pdf@openai-primary-runtime"] enabled = false`. The
owner then turned a plugin off and on again in the app (Plugins → CoinGecko). After each step we
compared the file with the backup, hiding secret-looking values. At the end we removed our two
edits and checked the result.

## Result: passed. Outside edits survive while the app runs

| Question | Answer |
| --- | --- |
| Does the app keep outside edits? | Yes. The app rewrote the file at each toggle, and both the comment and `pdf … enabled = false` were still there. It reads the file again before it writes. |
| Does it keep comments? | It kept the first-line comment. Comments inside tables the app rewrites were not tested. |
| What does the app write itself? | It rewrites its own `[mcp_servers.node_repl]` table: the same env values in a new order, `args = []`, and `120` instead of `120.0`. The second toggle wrote the same bytes again (new file time, same hash). |
| Does Codex see our edit? | Yes. `codex plugin list --json` showed `pdf` as off right after the edit. |
| Where is a remote plugin's on/off? | In the ChatGPT account. Turning CoinGecko (`app-6a4f02…@openai-curated-remote`) off added nothing to `config.toml`, but `codex plugin list --json` showed `enabled: false`. Its cache folder has only `.codex-remote-plugin-install.json` with a `remote_plugin_id`. |
| Clean up | Our two edits were removed. The plugin tables match the backup. The only difference left is the app's own `node_repl` table. File mode stays `600`. |

## What the tool does

- Codex writes (plugin `enabled` for plugins with a `config.toml` entry, the gateway entry, and
  removing old MCP entries) are allowed while the app runs. Keep the stale check: the app may
  rewrite the file between preview and apply.
- Compare file hashes, not modification times. The app can rewrite the same bytes.
- Never change the app's own `node_repl` table.
- Remote plugins (`@openai-curated-remote` with an install record) are labeled "stored in
  account" (done in `src/agentsetup/clients/codex.py`). They have no on/off control. The page
  says where to change them: Codex → Plugins.
- For US4 (T052): read the real on/off of every plugin from `codex plugin list --json`, and verify
  writes with it.
- Not tested: whether a `config.toml` entry for a remote plugin overrides the account state.
