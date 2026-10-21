# Developing Kitden

## Develop

```bash
uv sync
uv run pytest -q
```

`uv tool install --reinstall .` gives you the `kitden` command from this folder. Contract tests
against the real clients run in sandbox homes: `uv run pytest -m contract`.

Built with Python 3.13+, uv, Starlette and the official MCP SDK. The page is plain ES modules
and one CSS file under `src/kitden/web/static/`, with a strict Content-Security-Policy: no
framework, no bundler, nothing loaded from another site. How it looks and moves:
[design.md](design.md).

| Folder | What |
| --- | --- |
| `src/kitden/clients/` | Reading and changing each client: Claude Code, Codex, Cursor |
| `src/kitden/changes/` | Preview, Apply with backup, verify, Undo |
| `src/kitden/views/` | What the page and the MCP server show |
| `src/kitden/gateway_api.py` | MetaMCP and Obot |
| `src/kitden/local_gateway/` | The Kitden gateway: settings and rules, project finding, the proxy inside `kitden mcp` |
| `src/kitden/web/` | The local page |
| `plugins/kitden/` | The plugin for Claude Code and Codex |

## Commands

| Command | What it does |
| --- | --- |
| `kitden` / `kitden open` | Opens the page; it stops 10 minutes after its last tab closes |
| `kitden serve` | Runs the page in the terminal until Ctrl+C |
| `kitden scan --json` | Prints what the page shows and exits |
| `kitden mcp` | The "show my setup" server that clients start; it also offers the tools of servers moved into the Kitden gateway |

## Check before a release

The tests use fake servers. Before a release that touches the Kitden gateway, check it once by
hand in each of Claude Code, Codex and Cursor, on a test project (a throwaway folder; never your
own project). Kitden must know the project: open it once in the client, so that it shows in the
page's project list. For Cursor, check the IDE, which names the project to the gateway; Cursor's
command line does not (checked 2026-10-21).

1. In the page, move a server with a few tools into the Kitden gateway, and set up the `kitden`
   entry in the client if it lacks one.
2. Pick the test project at the top and turn one tool off for it.
3. Start a new session in that folder. The tool is gone; the others are still there.
4. Undo the switch and the move. Start a new session; the server is direct again with its tool.
5. Move the server in again. Turn on "Strict: only tools you turned on" and turn one tool off. A
   new session offers only the tools that are on.
6. In a session that is already open, call the tool you turned off. It is refused with "<name> is
   turned off in Kitden." Turn it on again; the call works in the same session.
7. Undo the switches and the move; check the server is direct again.

Not run yet for steps 5 to 7: they need the real clients, and Part 2 was built and tested with
fake servers only.

## Release

1. `uv version X.Y.Z`, and the same number in `src/kitden/__init__.py`,
   `plugins/kitden/.claude-plugin/plugin.json`, `plugins/kitden/plugin.json` and `KITDEN_REF` in
   `install.sh` and `install.ps1` (a test checks they match).
2. Write `docs/releases/vX.Y.Z.md`: plain notes for users about everything since the last tag
   (`git log vA.B.C..HEAD`), grouped as New, Better and Fixed.
3. Update `ROADMAP.md`: rename "### Not released yet" to the version, move anything else that
   shipped under Done, and change the "Last updated" date.
4. Commit, then `git tag vX.Y.Z` and `git push origin main vX.Y.Z`.

The workflow runs the checks and stops if the notes file is missing. Then it publishes to PyPI
with trusted publishing and creates the GitHub release with the notes file as its text.
`README.md` is also the PyPI page, so its images and links use full `https://` addresses.

## Gateways

- **Kitden gateway** — three files in `~/Library/Application Support/kitden` (mode 700):
  `gateway.json` (mode 600) holds the servers and rules, `gateway-tools.json` the tool lists, and
  `gateway-calls.json` the count and last time (UTC) of each tool's forwarded calls, never what
  was sent. Only `gateway.json` changes through review and Undo; the other two are found data
  that the gateway and Rescan write. The gateway reads `gateway.json` again on each call, so a
  tool turned off is refused at once; if the file cannot be read, the rules it started with apply. It also holds the env values and headers of moved servers; only
  you can read it, and it stays on this Mac. `kitden mcp` finds the project once, at start: the
  `CLAUDE_PROJECT_DIR` variable, then the client's roots, then `WORKSPACE_FOLDER_PATHS`, then its
  start folder. Codex keeps a tool list for up to 30 minutes and ignores "list changed" (checked
  2026-10-21), so the tools are fixed for a session and a change applies to new sessions.
- **Obot** — sign in with OAuth; Kitden reads it with an API key from
  `obot login --url <obot> --scope api --scope all-mcp --print-token`, kept in an environment
  variable. Do not run `obot setup`: it edits client files without a backup.
  "Move into the gateway" takes the administrator's path (checked 2026-10-19, v0.26.3, from
  source; there are no reference docs): a catalog entry in the built-in catalog, then the vMCP
  manifest written back with one more component. A key without the admin role gets a clear
  refusal and nothing is written. Servers on this computer or a private network are refused
  before the review: Obot blocks them unless a tunnel is set up.
- **MetaMCP** — has no public management API; Kitden signs in with an email and a password
  from an environment variable to move servers into it.

## Linux and Windows

Not supported yet: the install scripts stop with a message, and the page looks for macOS paths.
