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
| `src/kitden/views/` | What the page and the read-only MCP server show |
| `src/kitden/gateway_api.py` | MetaMCP and Obot |
| `src/kitden/web/` | The local page |
| `plugins/kitden/` | The plugin for Claude Code and Codex |

## Commands

| Command | What it does |
| --- | --- |
| `kitden` / `kitden open` | Opens the page; it stops 10 minutes after its last tab closes |
| `kitden serve` | Runs the page in the terminal until Ctrl+C |
| `kitden scan --json` | Prints what the page shows and exits |
| `kitden mcp` | The read-only "show my setup" server that clients start |

## Release

1. `uv version X.Y.Z`, and the same number in `src/kitden/__init__.py`,
   `plugins/kitden/.claude-plugin/plugin.json`, `plugins/kitden/plugin.json` and `KITDEN_REF` in
   `install.sh` and `install.ps1` (a test checks they match).
2. Write `docs/releases/vX.Y.Z.md`: plain notes for users about everything since the last tag
   (`git log vA.B.C..HEAD`), grouped as New, Better and Fixed.
3. Update `ROADMAP.md`: move what shipped under Done and change the "Last updated" date.
4. Commit, then `git tag vX.Y.Z` and `git push origin main vX.Y.Z`.

The workflow runs the checks and stops if the notes file is missing. Then it publishes to PyPI
with trusted publishing and creates the GitHub release with the notes file as its text.
`README.md` is also the PyPI page, so its images and links use full `https://` addresses.

## Gateways

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
