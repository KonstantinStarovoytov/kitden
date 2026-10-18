# Contract: install scripts

Two files in the repository root, served raw from GitHub and later from the website.

| Line | Script | Shell |
| --- | --- | --- |
| `curl -LsSf https://raw.githubusercontent.com/<owner>/kitden/main/install.sh \| sh` | `install.sh` | POSIX `sh` |
| `powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/<owner>/kitden/main/install.ps1 \| iex"` | `install.ps1` | PowerShell |

## Steps and messages (`install.sh`)

| # | Step | Command | On failure: message, exit |
| --- | --- | --- | --- |
| 1 | System check | `uname -s` must be `Darwin` | `Kitden runs on macOS today. Linux and Windows are coming: <follow-up link>. Nothing was installed.`, exit 1 |
| 2 | Find or install uv | `command -v uv`, else `${XDG_BIN_HOME:-$HOME/.local/bin}/uv`; when neither exists: `curl -LsSf https://astral.sh/uv/install.sh \| sh`, then use the second path | `Could not install uv. See https://docs.astral.sh/uv/getting-started/installation/`, exit 2 |
| 3 | Install or update Kitden | first, `xcode-select -p` must succeed (git for the repository source): else `Kitden needs git until it is on PyPI. Run: xcode-select --install, then run this line again.`, exit 3; then `uv tool install "git+https://github.com/<owner>/kitden@$KITDEN_REF"`, where `KITDEN_REF` is the latest release tag written in the script; a newer script updates an older install | `Could not install Kitden. See the uv output above.`, exit 3 |
| 4 | Open the page | `"$(uv tool dir --bin)/kitden"` | Kitden's own message and exit 4 |
| 5 | PATH hint | when `uv tool dir --bin` is not in `$PATH`: print `To use the kitden command from any terminal, run: uv tool update-shell, then open a new terminal.` | — |

Every step prints one line saying what it does (`Installing uv…`, `Installing Kitden…`,
`Opening the Kitden page…`). The script never asks a question and never uses `sudo`.

Environment it respects: `XDG_BIN_HOME`, `UV_TOOL_BIN_DIR` (through `uv tool dir --bin`), and
uv's own installer variables (`UV_INSTALL_DIR`, `UV_NO_MODIFY_PATH`), which are passed through.

## `install.ps1`

The same five steps with uv's PowerShell installer line
(`irm https://astral.sh/uv/install.ps1 | iex`) and `$env:USERPROFILE\.local\bin\uv.exe`. Step 1
stops on Windows with the same message until Windows is supported, so steps 2–5 never run today.

## Rules

- The scripts install the `kitden` command and open the page. They never add, enable or change
  anything in Claude Code, Codex or Cursor (FR-007).
- Running a script twice is safe: uv is not reinstalled; Kitden is updated when the script names a
  newer release tag, and left as it is otherwise.
- The scripts are tested with fake `uv`, `curl` and `uname` commands (research R9); the real path
  is run in the quickstart on a clean account.
