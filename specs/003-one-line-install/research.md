# Research: One-line install

Reviewed: 2026-10-18. Status: decisions for this feature. Every claim links to a primary source
read on that date, or to a check on this machine (Claude Code 2.1.283, the Codex CLI shipped
with the ChatGPT app 0.163.0-alpha.10.2, uv 0.10.10). Vendor documentation shows a documented
feature, not runtime behaviour: the [quickstart](quickstart.md) checks the real clients.

## R1. Release pipeline

- **Decision**: one GitHub Actions workflow, `.github/workflows/release.yml`. On every push and
  pull request it runs the checks; on a pushed tag `v*` it also builds and releases. Two jobs:
  1. `build` on a macOS runner: install uv, `uv sync --locked`, `uv run ruff check .`,
     `uv run pytest -q`, `uv build`, check the built files (R2), smoke-test the wheel outside the
     checkout with `uv run --isolated --no-project --with dist/*.whl -- kitden --version`, upload
     `dist/` as an artifact.
  2. `release` (tags only): `permissions: contents: write`, `gh release create <tag> dist/*
     --generate-notes --verify-tag` with `GH_TOKEN: ${{ github.token }}`.

  Later, when the owner opens PyPI (owner decision, 2026-10-18): a `publish` job between the two
  with `environment: pypi`, `permissions: id-token: write` and `uv publish`. PyPI Trusted
  Publishing swaps the workflow's identity for a short-lived token; nothing is stored. The name
  `kitden` is registered at that first release.
- **Rationale**: FR-001. Separate jobs keep the publishing permission away from the test and
  build steps, as uv's guide does. The macOS runner is the only supported system and the tests use
  macOS paths. Release notes come from the commits; no changelog file to maintain.
- **Alternatives**: `pypa/gh-action-pypi-publish` (rejected: a second toolchain beside uv for the
  same result); publishing when a GitHub release is published (rejected: two owner actions
  instead of one tag push); `uv publish --token` by hand (rejected: a stored secret).
- **Facts checked**: a pending publisher on PyPI reserves nothing until the first publish; if
  someone registers the name first, the publisher is invalid. `gh release create` creates a
  missing tag from the default branch, so `--verify-tag` is used to refuse that. Naming any
  permission in a workflow sets every other one to `none`; `contents: write` "allows the action
  to create a release".
- **Sources**: [uv: publishing](https://docs.astral.sh/uv/guides/package/),
  [uv: GitHub Actions, the two-job publish workflow](https://docs.astral.sh/uv/guides/integration/github/),
  [PyPI: using a trusted publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
  [PyPI: pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/),
  [gh release create](https://cli.github.com/manual/gh_release_create),
  [GITHUB_TOKEN permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions),
  [GitHub token in workflows](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication).

## R2. Package metadata and contents

- **Decision**: `pyproject.toml` gains `license` (Apache-2.0, the owner's decision of 2026-10-18),
  `license-files`, classifiers (macOS, Python 3.13 and 3.14), `[project.urls]` (homepage,
  repository, releases) and keywords. `[tool.hatch.build.targets.sdist]` gets
  `only-include = ["src/kitden", "README.md", "LICENSE"]`. The release workflow checks that the
  wheel holds `kitden/web/static/index.html` and that the source distribution holds no `tests/`,
  `docs/` or `specs/` entry.
- **Why**: FR-002, FR-004. A trial `uv build` of the current code (2026-10-18) gave a 113 KB wheel
  with all 14 static files, and a 360 KB source distribution that also carried `docs/`, `specs/`
  and `tests/` with the fixtures (copies of real configurations with secrets replaced). The
  fixtures should not travel with the package.
- **Sources**: [hatch: build configuration](https://hatch.pypa.io/latest/config/build/)
  (`only-include`, `exclude` wins, VCS ignore files respected); the trial build.

## R3. Run without installing

- **Decision**: document `uvx --from git+https://github.com/KonstantinStarovoytov/kitden kitden` as the first
  path, pinned as `…/kitden@v0.1.0 kitden`. Later, with PyPI: `uvx kitden`, `uvx kitden@<version>`
  and `uvx kitden@latest` to refresh a cached one. uv downloads a Python that satisfies
  `requires-python` when none is installed (its default `python-downloads` is `automatic`).
- **Rationale**: FR-002, FR-003. `uvx` is `uv tool run`; its environment is cached and reused, and
  once `uv tool install kitden` exists, `uvx kitden` runs the installed version.
- **Sources**: [uv: tools guide](https://docs.astral.sh/uv/guides/tools/) (`uvx --from
  git+https://github.com/httpie/cli httpie`, `@tag`, `command@version`, `@latest`),
  [uv: tools concept](https://docs.astral.sh/uv/concepts/tools/) (cache; the installed version
  wins), [uv: Python versions](https://docs.astral.sh/uv/concepts/python-versions/).

## R4. The install line and the scripts

- **Decision**: two scripts in the repository root, served raw from GitHub (the website serves
  the same files later):
  - macOS and Linux: `curl -LsSf https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.sh | sh`
  - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.ps1 | iex"`

  `install.sh` is POSIX `sh`, and does, in this order: (1) `uname -s` must be `Darwin`, otherwise
  print that Kitden does not support this system yet, name the follow-up, and exit 1 before
  anything else; (2) find uv: `command -v uv`, else `${XDG_BIN_HOME:-$HOME/.local/bin}/uv`; when
  missing, run uv's own documented line `curl -LsSf https://astral.sh/uv/install.sh | sh`;
  (3) `uv tool install "git+https://github.com/KonstantinStarovoytov/kitden@$KITDEN_REF"`, where `KITDEN_REF`
  is the latest release tag written in the script (bumped at each release); running the line
  again after a release updates Kitden, because uv replaces the tool when the ref changes
  (checked here with a `git+file://` source and two refs). With PyPI, later: `uv tool install
  kitden` and `uv tool upgrade kitden`;
  (4) run `"$(uv tool dir --bin)/kitden"`, which opens the page and returns; (5) when that folder
  is not on PATH, print `uv tool update-shell` and "then open a new terminal". The contract lists
  the messages and exit codes. `install.ps1` carries the same steps with uv's PowerShell line, but
  step 1 stops on Windows until Windows is supported.
- **Why a script and not three commands joined with `&&`**: after uv's installer runs, `uv` is not
  on PATH in the same shell (the installer edits the profile for later shells), and `kitden` may
  not be either. The script uses full paths. A script also has one place for the system check.
- **Never writes to a client**: the script calls only uv and `kitden`, and `kitden` with no
  arguments opens the page and writes nothing ([feature 002 CLI contract](../002-kitden-rename/contracts/cli.md)).
- **Alternatives**: a Homebrew tap (later; [release channels](../../docs/research/release-channels-2026-10-18.md)),
  a signed package (last; most work), `pipx` (one more tool to install first).
- **Sources**: [uv: installation](https://docs.astral.sh/uv/getting-started/installation/)
  (the curl and PowerShell lines; `uv self update`),
  [uv: installer reference](https://docs.astral.sh/uv/reference/installer/) (`UV_INSTALL_DIR`,
  `UV_NO_MODIFY_PATH`), [uv: storage](https://docs.astral.sh/uv/reference/storage/) (tool
  executables go to `$XDG_BIN_HOME`, else `$XDG_DATA_HOME/../bin`, else `$HOME/.local/bin`;
  `UV_TOOL_BIN_DIR`); `uv tool dir --bin` prints that folder (checked on this machine);
  `uv tool update-shell` ([tools guide](https://docs.astral.sh/uv/guides/tools/)).

## R5. One plugin folder for Claude Code and Codex

- **Decision**: the plugin lives in `plugins/kitden/`:

  | File | For | Content |
  | --- | --- | --- |
  | `.claude-plugin/plugin.json` | Claude Code | name `kitden`, displayName, version, description, author, homepage, repository, license, keywords |
  | `plugin.json` | Codex (portable Agent Plugins format) | `$schema`, name `kitden`, version, description, author, homepage, repository, license |
  | `skills/setup/SKILL.md` | both | the one skill (FR-009); loads as `/kitden:setup` in Claude Code |
  | `.mcp.json` | Claude Code | the one stdio server entry (R6) |
  | `mcp.json` | Codex | the same entry, same bytes |
  | `README.md` | people | what the plugin adds and how to remove it |

  Two marketplace files at the repository root: `.claude-plugin/marketplace.json` (Claude Code:
  name `kitden`, owner, one entry with `"source": "./plugins/kitden"`) and
  `.agents/plugins/marketplace.json` (Codex: one entry with
  `{"source": "local", "path": "./plugins/kitden"}`). No `bin/`, `hooks/` or `commands/`.
- **Why a subfolder and not the repository root**: with the repository as the plugin, Claude Code
  would read a root `.mcp.json` as the plugin's servers, while it also reads a root `.mcp.json`
  as the project's MCP configuration for anyone working in the Kitden repository; and a copied
  plugin would be the whole repository. With a subfolder, the install copies only
  `plugins/kitden` into `~/.claude/plugins/cache/kitden/kitden/<version>/`.
- **Why two marketplace files**: each client's native format. Codex also reads
  `.claude-plugin/marketplace.json` as a legacy path, but its entry fields (`policy`) differ and
  Claude Code's strict validation warns on unknown fields. Two small files, no ambiguity.
- **Versions**: `version` in both manifests equals the package version (R10). Claude Code detects
  an update by the manifest version, so every release changes it.
- **Checked on this machine** (2026-10-18): this layout, with the extra root `plugin.json` and
  `mcp.json`, passes `claude plugin validate --strict` for the plugin and for the marketplace.
  With the repository added as a marketplace from its path, Claude Code 2.1.283 copies the plugin
  into `~/.claude/plugins/cache/kitden/kitden/0.1.0/` and lists its `mcpServers`; the Codex CLI
  0.163 copies it into `~/.codex/plugins/cache/kitden/kitden/0.1.0/` with `mcp.json` and writes
  `[plugins."kitden@kitden"] enabled = true` (contract test `tests/contract/test_plugin_install.py`).
- **Sources**: [Claude Code: publish a plugin](https://code.claude.com/docs/en/plugins/publish),
  [Claude Code: create a marketplace](https://code.claude.com/docs/en/plugins/create-marketplace),
  [Claude Code: manifest reference](https://code.claude.com/docs/en/plugins-reference) (layout,
  `.mcp.json`, `skills/`, path rules),
  [Claude Code: loading](https://code.claude.com/docs/en/plugins/loading) (copied into the cache;
  version from the manifest, else the commit),
  [Codex: build plugins](https://developers.openai.com/plugins/build/plugins) (portable
  `plugin.json` and `mcp.json`; marketplace at `.agents/plugins/marketplace.json`; the legacy
  `.claude-plugin/marketplace.json`; `codex plugin marketplace add owner/repo`),
  [Agent Plugins specification](https://agent-plugins.org/specification) (`skills/`, `mcp.json`
  stdio fields, `${PLUGIN_ROOT}`),
  [Codex: desktop-only plugins](https://developers.openai.com/plugins/deploy/desktop-only)
  (`mcp.json` with `"type": "stdio"`).

## R6. How the plugin starts the server

- **Decision**: the entry is `{"type": "stdio", "command": "kitden", "args": ["mcp"]}` in both
  files: the `kitden` command from the user's PATH. Not `uvx kitden mcp`, not a launcher script.

  | Option | Needs | At client start | Risk |
  | --- | --- | --- | --- |
  | `kitden mcp` (chosen) | Kitden installed (the install line or `uv tool install`) | starts at once, the same version as the page | the client's PATH must hold uv's tool folder; a GUI session may lack it (feature 001, R9) |
  | `uvx kitden mcp` | uv only | the first start downloads Kitden; later starts use the cache | the same PATH question for `uvx`; the server can be a different version than the page; a network call at client start; pinning the version means a plugin release per Kitden release anyway |
  | a launcher script in the plugin | one script per client root variable (`${CLAUDE_PLUGIN_ROOT}`, `${PLUGIN_ROOT}`), a shell script and later a Windows one | finds `kitden` in known places | more files; the Cursor button cannot use it; still cannot help when Kitden is missing |

- **Rationale**: one entry in every client, including the Cursor button; no second copy of
  Kitden; nothing downloaded when a client starts; the missing-command case is visible in the
  client (`/mcp` shows the server as failed) and explained by the skill (FR-009).
- **Open check**: the PATH of the Claude Desktop Code tab. The quickstart checks it. If the server
  fails only there, the fallback is a launcher for Claude Code alone
  (`${CLAUDE_PLUGIN_ROOT}/bin/kitden-mcp`, which adds `$HOME/.local/bin` to PATH); recorded here
  so the decision can change with evidence.
- **Sources**: [Claude Code: MCP](https://code.claude.com/docs/en/mcp) (plugin servers;
  `${CLAUDE_PLUGIN_ROOT}` in `command`, `args`, `env`; failed stdio servers are not retried;
  `/mcp` shows `Failed to connect`), the Agent Plugins specification (`command` is one executable
  token, no expansion in it), [feature 001 research R9](../001-agent-setup-inventory/research.md#r9-read-only-mcp-server).

## R7. Install commands per client

| Client | Command | Verified how (2026-10-18) |
| --- | --- | --- |
| Claude Code, in a session | `/plugin install kitden --marketplace KonstantinStarovoytov/kitden` — asks to confirm the marketplace, then opens the plugin's details to choose a scope. Needs 2.1.275 or newer | [install page](https://code.claude.com/docs/en/plugins/install#add-a-marketplace-and-install-in-one-command) |
| Claude Code, shell | `claude plugin marketplace add KonstantinStarovoytov/kitden`, then `claude plugin install kitden@kitden`. One command with `--marketplace` needs 2.1.292 or newer (the owner's 2.1.283 cannot) | [publish page](https://code.claude.com/docs/en/plugins/publish); `claude plugin --help` here |
| Claude Code, update | `claude plugin update kitden@kitden`; auto-update is off by default for a marketplace like ours | [loading page](https://code.claude.com/docs/en/plugins/loading#when-auto-update-runs) |
| Codex | `codex plugin marketplace add KonstantinStarovoytov/kitden` (also `owner/repo@ref`, `--sparse`), then `codex plugin add kitden@kitden` (or `codex plugin add kitden --marketplace kitden`); `codex plugin list`, `codex plugin remove` | `codex plugin --help`, `codex plugin add --help` of 0.163.0-alpha.10.2 (ChatGPT app); the [build page](https://developers.openai.com/plugins/build/plugins) shows the marketplace commands and leaves installing to the app's plugin browser |
| Cursor | `cursor://anysphere.cursor-deeplink/mcp/install?name=kitden&config=<base64>` where `<base64>` encodes `{"command":"kitden","args":["mcp"]}`; Cursor asks before installing | [install links](https://cursor.com/docs/mcp/install-links) |
| Cursor, README button | `[![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=kitden&config=<base64>)`; the badge images come from the docs page; the `https://cursor.com/en/install-mcp` page shows "Installing MCP Server — Redirecting to Cursor…" (observed, not on the docs page). The README also shows the plain `cursor://` link as text | docs page source; the page itself |

Codex's documentation says plugins from a marketplace run in "supported local clients, including
Codex CLI and Codex in the ChatGPT desktop app", and documents the stdio shape only on the
desktop-only page. Whether the Codex CLI starts the plugin's server is a real test in the
quickstart, not a documented fact. Which file Cursor writes for the button is not documented;
the quickstart records it (expected `~/.cursor/mcp.json`).

## R8. The page and plugin-provided servers

- **Decision**: `setup_server_state` gets a fifth state, `plugin`: the client has an MCP server
  named `kitden` whose source is a plugin (Kitden already reads plugin MCP servers for Claude Code
  and Codex, feature 001). The Agents place shows "Provided by the kitden plugin" and no Add
  button for that client. A user-level `kitden` entry next to it stays `added`, and the findings
  mark the pair as a duplicate with the existing rule. Cursor has no plugin path: the button
  writes a user-level entry, the existing `added` state.
- **Rationale**: FR-014; an honest inventory (constitution IV).
- **Found while building** (2026-10-18): the Codex reader now reads `mcp.json` (or `.mcp.json`)
  in an installed plugin's cache folder, so Codex reaches the `plugin` state too (checked with
  the real `codex` in the contract test); whether a Codex session starts that server is still
  the quickstart §5 check. A plugin entry beside an old `agentsetup` entry keeps the `plugin`
  state and the update only removes the old entry; the API refuses to add a second entry where
  the plugin provides the server. The existing effective view ranks a user entry over a plugin
  entry of the same name, so that pair is reported as an override (info), not a duplicate; in
  Claude Code both would run (`plugin:kitden:kitden` and `kitden`). That is a follow-up for the
  inventory, not for this feature.
- **Sources**: `src/kitden/views/setup_server.py`, `src/kitden/model.py` (`SourceKind.PLUGIN`,
  `Scope.PLUGIN`).

## R9. Testing

- **Unit, `tests/unit/test_plugin_package.py`**: every JSON file parses; names are `kitden`; both
  manifest versions equal `kitden.__version__`; `.mcp.json` and `mcp.json` are the same bytes
  and hold only the one stdio entry; the skill has `name` and `description` and the four rules of
  FR-009; no `hooks/`, `commands/`, `bin/`; the README's Cursor link decodes to the same entry.
- **Unit, `tests/unit/test_install_script.py`**: run `sh install.sh` with a temporary home and
  fake `uv`, `curl` and `uname` commands first on PATH, and check the calls: macOS without uv →
  installer, `tool install`, `kitden` run from the tool folder, PATH hint; uv present → no
  installer; Kitden present → `tool upgrade`; Linux → exit 1 and no call. `install.ps1`: a
  `pwsh -NoProfile` syntax check when `pwsh` exists, otherwise skipped and listed as not verified.
- **Unit, `tests/unit/test_setup_server.py`**: the `plugin` state per client; a user entry beside
  a plugin entry; Cursor unchanged.
- **Contract, `tests/contract/test_plugin_install.py`** (marker `contract`, local only, sandbox
  homes as in the existing handshake test): `claude plugin validate --strict` on the plugin and
  the marketplace; `claude plugin marketplace add <repo path>`, `claude plugin install
  kitden@kitden`, `claude plugin list`, uninstall; `codex plugin marketplace add <repo path>`,
  `codex plugin add kitden@kitden`, `codex plugin list --json`, remove. Files outside the plugin
  records keep their bytes.
- **Release workflow**: the built-file checks and the wheel smoke test (R1).
- **Quickstart**: a clean macOS user account, the Claude Desktop Code tab, the Codex app and CLI,
  Cursor; versions recorded.
- **Sources**: constitution V; `tests/contract/test_mcp_handshake.py`.

## R10. Versions and the first release

- **Decision**: `uv version 0.1.0` sets the package version: the first public version (0.1 and
  0.2 were working versions never published; owner decision 2026-10-18). The two manifests carry
  the same number (the unit test catches a miss). Tag `v0.1.0`, push the tag. Release notes are
  generated from the commits.
- **Rationale**: FR-015: one number everywhere; Claude Code sees a new plugin version only when
  the manifest version changes.
- **Sources**: `uv version` (checked here), [Claude Code: publish, "Decide how you'll version"](https://code.claude.com/docs/en/plugins/publish).

## R11. Owner steps outside the code, once

1. License: decided, Apache-2.0 (`LICENSE` file and the `license` field are in the code).
2. Create the GitHub repository `KonstantinStarovoytov/kitden`, public, in the personal profile, and push
   `main`. The login was given on 2026-10-18 and is in every link and manifest.
3. First release: `git tag v0.1.0`, `git push origin main v0.1.0`. The workflow builds and creates
   the GitHub release.
4. Later, for PyPI: an account; under "Publishing", a pending trusted publisher: project `kitden`,
   owner `KonstantinStarovoytov`, repository `kitden`, workflow `release.yml`, environment `pypi`; on GitHub,
   Settings → Environments → `pypi`. Register the name `kitden` with that first publish.

Sources: the PyPI pending publisher page and the uv GitHub guide ("create the environment … under
Settings → Environments"), both above.

## Not chosen now

A Homebrew tap, Anthropic's directory (paid plan and review), OpenAI's directory (partner
allowlist for local MCP), the MCP Registry, a signed binary, the website: see the
[release channels research](../../docs/research/release-channels-2026-10-18.md). Linux and
Windows support is the named follow-up feature.
