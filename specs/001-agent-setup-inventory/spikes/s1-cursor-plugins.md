# Spike S1: Cursor plugin state

Date: 2026-10-17. Cursor 3.21.16, which updated itself to 3.25.6 during the spike.
Method: the owner changed one plugin in Cursor. We compared hashes of Cursor's state before and
after (values were never stored), then read only the plugin keys. Docs checked on the same day:
[cursor.com/docs/plugins](https://cursor.com/docs/plugins).

## Result: no writes. Cursor plugins stay read-only

| Question | Answer |
| --- | --- |
| Is there an on/off switch? | No. A plugin is installed for you ("Add for Myself"), for some projects ("Add to Project …"), or not at all. The docs only describe installing in "a project or user scope". |
| What changed when "Add for Myself" was unchecked? | One row changed: `cursor.plugins.installedIds.<team>\|no-workspace` lost id `648` (Create Plugin). No files changed, and the plugin's cache folder stayed. |
| Where does the real state live? | In the Cursor account. The plugin page's "Used by N teammates" went from 2 to 1. The local rows are a copy. |
| Add back, then restart | `648` came back after "Add to Cursor" and was still there after a full restart. |
| Row format | `[{"id": "648", "sources": ["user"]}, …]`. `sources` is `user` (installed for you) or `project` (installed for that project). |
| Project rows | `installedIds.<team>\|file:///path` rows repeat your own installs and add the project's. Cursor updates them only when it opens that project: after the change, 5 project rows still listed `648`. |
| Plugin names | The rows hold no names. Each workspace database has Customize snapshots (`workbench.customize.primitiveSourceSnapshot.*.v3`) that list skills, rules and subagents with `pluginId` and `filePath`. A path under `~/.cursor/plugins/cache/<marketplace>/<plugin>/` gives the name. A plugin with no skills, rules or subagents (here id `4800`) stays unnamed. |

We do not write because Cursor has no local switch, and the install list lives in the account.
Writing the local copy would not change what Cursor loads, and account sync would overwrite it
(constitution III).

## What the tool does

- An installed plugin is shown as on. Your own installs come from the `no-workspace` row.
  Project installs come from entries marked `sources: ["project"]`.
- A multi-folder window shows the project plugins of all its folders. Its row adds a plugin only
  when none of those folders already has it, and only to folders without a row of their own.
- Your own installs are labeled "not documented". Project installs are labeled "may be stale".
- Names come from the Customize snapshots. A plugin without a name is shown as
  "plugin <id> (name not stored locally)".
- When there are no install rows, downloaded plugins are listed from the cache as "unknown",
  because a downloaded plugin may already be uninstalled.
- The plugin has no on/off control. The page says: "Cursor has no plugin on/off. Change it in
  Cursor: Customize → Plugins → the plugin's menu (Add for Myself / Add to Project)."
- Not tested: the Cursor CLI setting `enabled_plugins` in `~/.cursor/settings.json` (changelog,
  2026-05-20). That file does not exist on the owner's machine.

## Bug found and fixed

The first reader counted your repeated installs as project installs. For example, it showed
"5 plugins installed" in projects that have none of their own. It also listed every downloaded
plugin as installed. Both are fixed in `src/agentsetup/clients/cursor.py`, with tests.

Side note: the snapshots also tag the skills of the Claude Code `superpowers` plugin that Cursor
imports with id `684`, the id of Cursor's own `superpowers`. Cursor shows both copies under one
plugin, which supports the "loaded twice" duplicate finding.
