# Quickstart: check feature 002

Run on a sandbox home first (`--home <folder>`), then once on the owner's real setup.

## 1. New name

```bash
uv tool install --reinstall .
kitden --version
```

Expected: `kitden 0.2.0`. The page title says Kitden.

## 2. Old data folder

Sandbox home with `Library/Application Support/agentsetup` (a gateway and one applied change), no
`kitden` folder. Run `kitden open --home <sandbox>`.

Expected: the gateway and the change are listed; delete the old folder, then Undo the old change
from Changes: the file comes back exactly.

## 3. Old MCP entries

Sandbox home where Claude Code, Codex and Cursor each have an `agentsetup` entry running
`.../agentsetup mcp`, plus one `agentsetup` entry running another program.

Expected: Agents shows "Old entry" with "Update to Kitden…" for the three clients and nothing for
the other one. Update → review shows remove + add in one file per client → Apply → `kitden` entries;
Undo → old entries back exactly. Contract test does the same with the real `claude` and `codex`.

## 4. One page, opened from anywhere

```bash
kitden open --home <sandbox>   # starts and opens
cd /tmp && kitden open --home <sandbox>   # opens the same page
```

Expected: the second call returns in under 2 s; one `kitden serve` process. A page for another home
keeps its own login.

## 5. Stops without a tab

Close the tab and wait 10 minutes (tests use a short wait).

Expected: the process is gone and `page.json` is removed. A change running at that moment finishes
first.

## 6. Owner's real setup (last)

Stop the old page (Ctrl+C), install Kitden, run `kitden`, update the Codex entry from Agents, then
`uv tool uninstall agentsetup`.
