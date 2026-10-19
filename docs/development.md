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

1. `uv version X.Y.Z`, and the same number in `plugins/kitden/.claude-plugin/plugin.json`,
   `plugins/kitden/plugin.json` and `KITDEN_REF` in `install.sh` and `install.ps1`
   (a test checks they match).
2. Commit, then `git tag vX.Y.Z` and `git push origin main vX.Y.Z`.

The workflow runs the checks, publishes to PyPI with trusted publishing and creates the GitHub
release.

## Gateways

- **Obot** — sign in with OAuth; Kitden reads it with an API key from
  `obot login --url <obot> --scope api --scope all-mcp --print-token`, kept in an environment
  variable. Do not run `obot setup`: it edits client files without a backup.
- **MetaMCP** — has no public management API; Kitden signs in with an email and a password
  from an environment variable to move servers into it.

## Linux and Windows

Not supported yet: the install scripts stop with a message, and the page looks for macOS paths.
