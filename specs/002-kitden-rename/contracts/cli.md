# Contract: command line (replaces feature 001's CLI contract)

All commands are local and never send data off the computer.

| Command | Behavior | Exit codes |
| --- | --- | --- |
| `kitden` or `kitden open` | If a page runs for this home folder, opens it in the browser. Otherwise starts the page in the background, waits until it listens, then opens it. Always prints the link. Returns in under 5 s | 0 ok; 2 no free port; 4 the page did not start (see `page.log`) |
| `kitden open --no-browser` | Same, but only prints the link | Same |
| `kitden serve` | Runs the page in the foreground until Ctrl+C, for development and tests. If a page already runs, opens it and exits | 0; 2 no free port |
| `kitden serve --background` | Used by `kitden open`; stops after 10 minutes without a tab | 0 |
| `kitden scan [--json]` | Prints the redacted inventory, then exits. Never writes | 0; 3 a client file could not be read |
| `kitden mcp` | Runs the read-only MCP server over stdio | 0 on stdin close |
| `kitden --version` | Prints `kitden <version>` | 0 |

Every command accepts `--home PATH` (testing). The data folder, lock and page record live under
that home, so test pages never touch the developer's own page.

Rules:

- No command writes client settings. Writes happen only through the page's Apply.
- Every command copies the old data folder once when needed
  ([data model](../data-model.md#data-folder)).
- Install: `uv tool install <repository path>` for now, which gives `~/.local/bin/kitden` for
  client configs. After updating old entries: `uv tool uninstall agentsetup`.
