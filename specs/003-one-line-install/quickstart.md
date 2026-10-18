# Quickstart: checking the one-line install

Reviewed: 2026-10-18. Run on real machines and clients; record the versions in the table at the
end. Nothing here changes the owner's own clients: use a second macOS user account for §2–§3 and
sandbox homes (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `HOME`) for §4–§6 where possible.

## 1. The built package (any machine with uv)

```bash
uv build
tar tzf dist/kitden-*.tar.gz | grep -E '^kitden-[^/]+/(tests|docs|specs)/' && echo "FAIL: extra files" || echo "sdist ok"
unzip -l dist/kitden-*-py3-none-any.whl | grep -q kitden/web/static/index.html && echo "wheel ok"
uv run --isolated --no-project --with dist/*.whl -- kitden --version
```

Expected: `sdist ok`, `wheel ok`, `kitden <version>`.

## 2. Run without installing (clean macOS user account, uv only)

`uvx --from git+https://github.com/<owner>/kitden kitden` (later, with PyPI: `uvx kitden`).
Expected: the page opens, the link is printed, the first run takes under 2 minutes (SC-001),
the second under 10 seconds. `shasum ~/.claude.json ~/.codex/config.toml ~/.cursor/mcp.json`
before and after: unchanged (or the files do not exist).

## 3. The install line (clean macOS user account, no uv)

1. Record the client file hashes as above.
2. Paste the macOS line from the README. Expected: `Installing uv…`, `Installing Kitden…`,
   `Opening the Kitden page…`, the page opens, the PATH hint is printed, all under 3 minutes
   (SC-002). Without the command line tools, it stops with the `xcode-select --install` line.
3. Open a new terminal: `kitden --version` works after `uv tool update-shell`.
4. Paste the line again. Expected: no uv install; `Installing Kitden…` again; the page opens.
5. Hashes unchanged.
6. On a Linux machine or VM, or with `uname` faked: the line prints the "macOS today" message and
   installs nothing (exit 1).

## 4. Claude Code (terminal and the Claude Desktop Code tab)

1. `claude plugin validate --strict ./plugins/kitden` and `claude plugin validate --strict .`
   → `Validation passed`.
2. In a session: `/plugin install kitden --marketplace <owner>/kitden`, confirm the marketplace,
   choose "Install for you". Start a new session.
3. `/mcp` shows `plugin:kitden:kitden` connected; `/` lists `/kitden:setup`.
4. Ask: "What does Claude Code load in this project?" Expected: the answer comes from
   `show_setup` (visible in the tool calls), no file read or edited (SC-004).
5. Ask: "Turn off plugin X." Expected: the agent points to `kitden open` and edits nothing.
6. Repeat 3–5 in the Claude Desktop Code tab. If the server fails only there, record it: that is
   the PATH case of research R6, and the fallback applies.
7. Open the Kitden page → Agents: Claude Code shows "Provided by the kitden plugin", no Add
   button. Add the user-level entry anyway from a sandbox home: the Overview shows a duplicate.
8. `uv tool uninstall kitden` in a sandbox: `/mcp` shows the server as failed; the skill still
   loads and tells the agent to show the install line.
9. `claude plugin uninstall kitden@kitden`: `~/.claude/settings.json` loses only the
   `enabledPlugins` entry; other keys unchanged.

## 5. Codex (the ChatGPT app and the CLI)

1. `codex plugin marketplace add <owner>/kitden`, then `codex plugin add kitden@kitden`.
2. New session in the app: the kitden tools answer "what loads here"; the skill is listed.
   Repeat in the CLI (`codex`). Record whether the CLI starts the plugin's server (research R7).
3. Kitden page → Agents: Codex shows "Provided by the kitden plugin".
4. `codex plugin remove kitden@kitden`; `config.toml` keeps every other table.

## 6. Cursor

1. Hash `~/.cursor/mcp.json` (or note that it does not exist).
2. Click "Add to Cursor" in the README (on GitHub) and confirm in Cursor. Record which file
   Cursor wrote.
3. Expected: exactly one new entry `kitden` with command `kitden` and args `["mcp"]`; the rest
   of the file byte for byte the same (SC-006). Cursor's MCP settings show the server with four
   tools.
4. Kitden page → Agents: Cursor shows "Added".

## 7. The first release (the owner's repository)

After research R11: `git tag v0.1.0`, `git push origin main v0.1.0`. Expected within
15 minutes: the Actions run is green and the GitHub release holds the two files and notes. On
another machine: `uvx --from git+https://github.com/<owner>/kitden@v0.1.0 kitden --version`
prints `kitden 0.1.0` (SC-003).

## Versions recorded

| What | Version | Date | Result |
| --- | --- | --- | --- |
| macOS | 26 (Darwin 25.6) | 2026-10-18 | §1 passes; §2 and §3 wait for a clean account |
| uv | 0.10.10 | 2026-10-18 | `uv tool install` from a git ref and the update on a new ref checked with a local repository |
| Claude Code (terminal) | 2.1.283 | 2026-10-18 | `validate --strict`, marketplace add, install, list, uninstall pass in a sandbox home (contract test); a session with the plugin not yet checked |
| Claude Desktop Code tab | — | — | not checked (research R6 PATH question open) |
| Codex app / CLI | CLI 0.163.0-alpha.10.2 (ChatGPT app) | 2026-10-18 | marketplace add, plugin add, remove pass in a sandbox home and the page shows Codex as `plugin` (contract test); whether a session starts the plugin's server not checked |
| Cursor | — | — | not checked |
| Windows script | — | — | text checked only; no PowerShell on this Mac |
| Kitden | 0.1.0 | 2026-10-18 | `kitden 0.1.0` from the built wheel outside the checkout |
