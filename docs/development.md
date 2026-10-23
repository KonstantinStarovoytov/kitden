# Developing Kitden

## Develop

```bash
uv sync
uv run pytest -q
```

`uv tool install --reinstall .` gives you the `kitden` command from this folder. Contract tests
against the real clients run in sandbox homes: `uv run pytest -m contract`. Tests can build a
sample home with `kitden.demo.build_demo_home(root, size)`.

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
| `src/kitden/demo/` | Sample setups for `kitden demo` and the tests, and the demo's stand-ins |
| `src/kitden/web/` | The local page |
| `plugins/kitden/` | The plugin for Claude Code and Codex |

## Commands

| Command | What it does |
| --- | --- |
| `kitden` / `kitden open` | Opens the page; it stops 10 minutes after its last tab closes |
| `kitden serve` | Runs the page in the terminal until Ctrl+C |
| `kitden demo [--size small\|medium\|large]` | Opens the page on a sample setup (medium if no size is given) in a temporary folder; it runs no client, starts no MCP server, uses no Keychain and stays offline; the folder is deleted when it stops |
| `kitden scan --json` | Prints what the page shows and exits |
| `kitden mcp` | The "show my setup" server that clients start; it also offers the tools of servers moved into the Kitden gateway |

## Speed

`uv run python scripts/measure-start.py` builds the large sample setup
(`build_demo_home(root, "large")`: about 500 items, 17 projects and 12 servers in the Kitden
gateway) with fake `claude`, `codex` and `cursor` commands, then starts the page twice on a free
port. Then it starts the page on the medium sample, as `kitden demo` does. It prints three
numbers:

- **first usable**: time to the first answer of `/api/overview` while Codex's plugin list takes
  10 seconds. The start line must then say "Still checking Codex plugins". Budget: 2 s.
- **complete**: time until every step of the first scan is done, with the list answering at
  once. Budget: 5 s.
- **demo (medium)**: time from building the medium sample to the first answer of
  `/api/overview`. Budget: 2 s.

A missed budget gives exit code 1. Times start with the page, and the demo's with building its
sample; Python's own start and a `uvx` cold start are not counted. The client versions are known
before each run, as on every start after the first: the page reads them from `versions.json` in
the data folder (`~/Library/Application Support/kitden`) and runs a client's version command
only in the background, when its binary is new or changed.

Measured: first usable 0.1 s, complete 0.1 to 0.2 s, demo under 0.1 s (checked 2026-10-23,
Apple M4 Max, macOS 26.6.2). With Python's own start, `uv run kitden demo` has its first overview
in about 0.3 s (checked 2026-10-22).

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

Before a release that adds, removes or puts back items, also check these once by hand, on the
same test project:

8. Remove a plugin in Claude Code, then in Codex. A new session does not have it. Undo; a new
   session has it again.
9. Remove a skill. A new session does not have it. Undo; its folder is back.
10. "Put back in <client>…" a held server, then remove it from the Kitden gateway. A new session
    reaches it directly; an open session's call to it through the gateway is refused.
11. "+ Add" a server whose header reads a `${VAR}` from Claude Code into Cursor and Codex. A new
    session in each reaches it.
12. With the test project picked, "Add to this project…" a skill and a Claude Code plugin. A
    session in that folder has them; one in another folder does not.
13. "Add missing…" on the test project, Apply, check a new session in each client, then Undo.
14. Remove a plugin that is turned off. Undo; it is back and still off.
15. Remove a Claude Code plugin that is on for the test project only. Kitden runs
    `claude plugin uninstall <name> -s project` in the project folder. A session there no longer
    has it; Undo puts it back for that project only.
16. In Codex, remove a plugin, then Undo. `codex plugin remove <id>` should delete its
    `[plugins."<id>"]` table in `~/.codex/config.toml`, and `codex plugin add <id> --json` should
    write it back and fetch the plugin again. This is assumed from `codex plugin --help` (0.163,
    2026-10-19); Codex's docs do not say it (checked 2026-10-22). Then "Add missing…" a Codex
    plugin and a Codex server together and Undo: the plugin is gone from Codex's `/plugins` too,
    not only from the file.

Not run yet for steps 8 to 16: Part 3 was built and tested with fake client commands only.

Before a release that touches secrets, also check the Keychain once by hand, on the same test
project, with a server that has a token:

17. Move the server into the gateway. A Keychain item (service `kitden`, account `<server>/<key>`)
    appears, and `gateway.json` holds a reference, not the token.
18. Start a new session. The server's tools work.
19. Undo the move. The Keychain item is gone.
20. Move a server in, edit `gateway.json` to hold a plain token for it, and open its Details:
    "Move secrets to the Keychain…" moves the token and leaves a reference.
21. Confirm four `security` facts by hand: `find-generic-password` exits with 44 for a missing
    item; `security -i` reads the quoted `add-generic-password` line as the code expects; `find ... -w`
    prints a non-ASCII value back unchanged; a long value (for example 4 KB) is stored and read
    back unchanged.
22. With Claude Code open, "Put back in Claude Code…" a held server that has a token. Kitden
    writes `~/.claude.json` itself (no `claude mcp add-json`, so the token is never in a
    command's arguments). Use Claude Code for a minute, then check the entry is still there and
    a new session has the server. Undo; the entry is gone and the rest of the file is kept.

Not run yet for steps 17 to 22: Part 5 was built and tested with a fake `security` only, and
step 22 with a fake `claude`.

Before a release that touches Details or reviews, also check this once by hand, on the same test
project, with a Claude Code plugin that is on:

23. Open a review (Remove for a Claude Code plugin) and do not press Apply. Then turn that plugin
    off in Claude Code itself. The page rescans on its own; press Rescan if it does not. The
    review says "Settings changed since this preview." and offers "Preview again"; Apply is gone.
    Press "Preview again": a new review opens for the plugin as it is now. Press Cancel there:
    Details comes back and shows the plugin off.

Not run yet for step 23: Part 3 of visual management was tested with sandbox files only.

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
  was sent. Only `gateway.json` changes through review and Undo; the other two are found data that
  the gateway and Rescan write. The gateway reads `gateway.json` again on each call, so a tool
  turned off is refused at once; if the file cannot be read, the rules it started with apply. It
  keeps references, not secrets: each non-empty env value or header that would be hidden is a Keychain item
  (service `kitden`, account `<server>/<key>`), and `gateway.json` holds `{"keychain": "<server>/<key>"}`.
  The gateway reads the items when it starts a server. Kitden calls `/usr/bin/security`; the
  env variable `KITDEN_SECURITY` replaces that path, as a test hook only. `kitden mcp` finds the project once, at start: the `CLAUDE_PROJECT_DIR` variable, then
  the client's roots, then `WORKSPACE_FOLDER_PATHS`, then its start folder. Codex keeps a tool
  list for up to 30 minutes and ignores "list changed" (checked 2026-10-21), so the offered list
  is fixed for a session; a tool turned off is still refused at once.
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
