# Kitden on Linux

Date: 2026-11-03. Owner's choices from a chat the same day; the rest are the writer's calls,
marked "(call)".

## Why

Kitden runs on macOS only. Linux is the cheapest way to reach many more people: the three
clients keep their files in the same places there (`~/.claude`, `~/.codex`, `~/.cursor`), and
macOS is tied in only a few spots: the Keychain, the data folder, Cursor's state database,
Claude Desktop's files, the app links on the map, the installer and CI. "macOS only" would be
the first comment under a launch post, so Linux comes right after the launch, as its own release.

The first Linux user is a person on a laptop with a desktop (the owner's picture), not a server
or WSL. That decides where secrets go.

## Goals

1. `uvx --python 3.13 kitden demo` and `uv tool install --python 3.13 kitden && kitden` work on
   a Linux desktop the same way they do on a Mac: the page opens, the three clients are read,
   changes go through preview → Apply with a backup → verify → Undo.
2. Secrets of moved servers live in the desktop's keyring, never in a file, with the same
   reference in `gateway.json` as today.
3. The same test suite passes on both systems, and CI runs it on both.
4. The docs say Linux plainly, with the one thing a Linux user may need to install.

## Non-goals

- Windows. `install.ps1` keeps saying it is coming.
- Servers, containers and WSL without a desktop keyring. They may work for everything but
  secrets; Kitden does not promise it.
- Finding a client's command when it is not on the PATH. On macOS Kitden falls back to the
  app bundles; on Linux there is no fixed place (Cursor's AppImage, say), so a client whose
  command is not on the PATH shows its version as unknown and offers no plugin commands. The
  `.deb` and `.rpm` installs put the command on the PATH.
- Links from the map to the client apps (`claude://`, `cursor://`). On Linux the map shows the
  clients without links.
- A sandboxed client (snap, Flatpak) whose gateway process cannot reach the desktop's bus.
- A Homebrew tap or Linux packages. `uv` stays the one install path.

## Anti-goals

- A secret in a plain file, even with mode 0600, as a fallback when the keyring is missing. A
  server whose secret cannot be stored waits in preview, as it does today when the Keychain
  cannot be reached.
- A second code path for Linux spread over the clients. The system difference lives in one
  place.
- `if sys.platform` checks in tests. Tests build paths through the same helpers the code uses.

## The parts

### 1. One place for system differences (call)

A new module `kitden/system.py` answers "where does this system keep things" and nothing else:

- `SYSTEM`: `"mac"` or `"linux"`, from `sys.platform` once at import; the environment variable
  `KITDEN_SYSTEM` overrides it, for tests and the demo only. Any other platform is refused at
  start with one sentence: "Kitden runs on macOS and Linux." (Windows keeps its own message in
  `install.ps1`.)
- `data_dir(home)`: macOS `Library/Application Support/kitden`; Linux `~/.local/share/kitden`,
  not moved by `XDG_DATA_HOME` (changed while building, 2026-11-03: the gateway `kitden mcp` is
  started by each client with that client's environment, and Codex passes only a short list of
  variables, so the page and a gateway under Codex would read different folders). `gateways.py`
  and everything that builds on `DATA_DIR` goes through it. The one-time copy from the old
  `agentsetup` folder stays macOS-only; on Linux there is nothing to copy.
- `cursor_state_dir(home)`: macOS `Library/Application Support/Cursor/User`; Linux
  `$XDG_CONFIG_HOME/Cursor/User`, by default `~/.config/Cursor/User`. Cursor is a VS Code
  build and keeps its state where VS Code does (to check on a real Linux install before
  release; write the date in `cursor.py`).
- `claude_desktop_dir(home)`: macOS `Library/Application Support/Claude`; Linux
  `$XDG_CONFIG_HOME/Claude`, by default `~/.config/Claude`. Claude Desktop has a Linux beta
  for Ubuntu 22.04+ and Debian 12+ (checked 2026-11-03, support.claude.com "Install Claude
  Desktop"); the page does not name its config path, so the builder checks that folder and
  whether the Linux app bundles Claude Code on a real install, and writes the date beside it.
  When the folder is missing, nothing is read, as today.
- `watched(home)`: the folders `kitden` watches for a rescan: the three client folders,
  `.agents` and the Claude Desktop folder of that system.
- `app_roots(home)`: moves here from `apps.py`; on Linux it returns an empty list, so
  `app_url` gives no link.
- `app_commands(client)`: the fallback paths of a client's command when it is not on the PATH
  (today in `clients/versions.py` and `changes/client_cli.find_command`, under
  `/Applications`); on Linux there are none.
- `secret_store_name()`: "Keychain" on macOS, "keyring" on Linux, for the page's words.

The page's `shortPath` in `dom.js` shortens `/home/<name>` to `~` as it does `/Users/<name>`.

The tests' fixtures (`conftest.py`'s `CURSOR_DB` and the `Library/...` paths in seven test
files) build their paths through these helpers, so the suite runs unchanged on Ubuntu. Tests
that are about one system set `KITDEN_SYSTEM` for that test.

### 2. Secrets in the Linux keyring

On Linux `local_gateway/keychain.py` runs `secret-tool` (package `libsecret-tools`, which
GNOME Keyring and KDE Wallet both serve over the Secret Service API) in place of `security`:

| Kitden does | macOS `security` | Linux `secret-tool` |
| --- | --- | --- |
| store | `-i` with one `add-generic-password -U -s kitden -a "<account>" -X <hex>` line on stdin | `secret-tool store --label="Kitden: <account>" service kitden account <account>`, the value on stdin |
| read | `find-generic-password -s kitden -a <account> -w` | `secret-tool lookup service kitden account <account>` |
| delete | `delete-generic-password -s kitden -a <account>` | `secret-tool clear service kitden account <account>` |

Facts about `secret-tool`, from the Debian man page (libsecret-tools, trixie) and libsecret's
`tool/secret-tool.c` on main, checked 2026-11-03: `store` takes the password from stdin until
EOF, so the value is never on the command line, and a trailing newline would become part of it
(Kitden writes none); `lookup` prints the first matching unlocked password, with no newline
when piped; `clear` removes all unlocked items that match. `lookup` exits 1 with nothing on
stdout both when no item matches and when the Secret Service cannot be reached; only the second
case writes a line to stderr. `store` exits 1 on any error. `clear` most likely exits 1 for a
missing item too (libsecret reports a clear that removed nothing as a failure); the builder
checks this on Ubuntu and writes the date beside it.

So the exit code alone cannot tell "not there" from "could not reach", and Kitden must not
mix them: a preview that took "could not reach" for "not there" would pass and Apply would then
fail and roll back, which breaks the promise below. The runner therefore returns stderr too,
`(code, stdout, stderr)`, on both systems (call: the `run=` call sites in `engine.py`,
`proxy.py`, `oauth.py` and `views.py` only pass the runner on and keep their signatures; the
demo's `DemoKeychain` and the two test stand-ins return the three values). The rules: `read`
takes exit 1 with empty stdout and empty stderr as "not there", and anything on stderr, or a
tool that cannot run, as "could not reach"; `store` reads the item back, as on macOS; `delete`
is quiet on exit 1 with empty stderr. On macOS the stderr is carried and ignored, since
`security` has its own code 44 for a missing item.

The gateway resolves secrets inside the process a client starts, and `secret-tool` finds the
keyring through `DBUS_SESSION_BUS_ADDRESS`. Codex passes only a whitelist of environment
variables to a stdio MCP server (its config reference, `mcp_servers.<id>.env_vars`, checked
2026-11-03), so a gateway started by Codex would not see the bus. Kitden therefore runs
`secret-tool` with `DBUS_SESSION_BUS_ADDRESS` set to `unix:path=$XDG_RUNTIME_DIR/bus`, or
`/run/user/<uid>/bus` when `XDG_RUNTIME_DIR` is missing too, whenever the environment lacks
it; that is where the user session bus of every systemd desktop listens. Nothing is written to
any client file for this. The CI round trip (below) runs once with a cleared environment to
prove it.

Rules that stay the same on both systems: the command by its full path (`/usr/bin/secret-tool`;
`KITDEN_SECRET_TOOL` points tests at a stand-in, as `KITDEN_SECURITY` does today); the same
20 s timeout, since the keyring may ask the person to unlock it; the same reference
`{"keychain": "<server>/<key>"}` in `gateway.json`, so a gateway file moves between systems
without change; `KeychainError` with one plain sentence and never a value. The engine's own
"in your Keychain" sentences take `secret_store_name()` too.

What the person sees when `secret-tool` is missing or the keyring daemon is not running: the
same step as today when the Keychain cannot be reached. The server waits in preview with
"Kitden could not reach the keyring." and one line more: "Install libsecret-tools and sign in
to your desktop session." Apply writes the other changes. The Linux page says "keyring" where
the macOS page says "Keychain": "Saved in your keyring on Apply.", "Move secrets to the
keyring…", "Not in the keyring". The server tells the page the store's name once, with the
setup it already sends; no second copy of the texts in JavaScript.

Tests: `tests/fixtures/fake_secret_tool.py` beside `fake_security.py`, keeping items in the
same JSON file shape, knowing only the three commands above and answering "no match" the way
the real tool does. The demo's `DemoKeychain` learns the same three commands, so `kitden demo`
runs on Linux without a keyring. CI on Ubuntu also runs one real round trip (store, lookup,
clear) through `gnome-keyring-daemon` under `dbus-run-session`, so the command lines are
checked against the real tool on every push, not only by hand.

### 3. Installer and the start

`install.sh` accepts `Darwin` and `Linux`. It installs Kitden from PyPI by its pinned version
(`uv tool install --python 3.13 kitden==<version>`) and no longer from the git tag, so git and
`xcode-select` are not needed on either system (call: the comment in the script says this was
the plan once Kitden is on PyPI). On Linux it also says, once, when `secret-tool` is not on the
PATH: "To store server secrets, install libsecret-tools (Debian, Ubuntu) or libsecret
(Fedora, Arch)." The test `test_install_script.py` runs the script with `FAKE_UNAME=Linux` too.

`kitden` opens the page with `webbrowser.open`, which uses `xdg-open` on Linux; nothing to add.
The private link, the page lock and the page record live in the data folder and need no
change.

### 4. CI

The `build` job runs on `macos-latest` and `ubuntu-latest` (a matrix). Both run ruff, the
Python tests with the coverage floor, the page's tests, the start-time budget and the
dependency audit. Only one of them (macOS, as today) builds the package and uploads it, so the
publish and release jobs stay as they are. The Ubuntu job installs `libsecret-tools`,
`gnome-keyring` and `dbus` for the real round trip of part 2.

### 5. Docs and metadata

- README: "Needs macOS or Linux, uv and at least one of…"; "Everything stays on your
  computer."; "Secrets live in the macOS Keychain or your Linux keyring only."; the Linux note
  about `libsecret-tools` under Get started.
- Guide: the same words in Requirements and in Privacy and limits.
- `docs/development.md`: the "Linux and Windows" section becomes "Windows" and says Linux is
  supported; a line on how to run the suite under `KITDEN_SYSTEM=linux` on a Mac and on the
  Ubuntu CI job; the hand check of secrets before a release (step 17 to 19) gets its Linux
  twin.
- `pyproject.toml`: add `Operating System :: POSIX :: Linux`.
- ROADMAP: Linux moves to Done under the next version; Windows stays in Next.
- The release notes file for that version.
- `docs/launch-posts.md` (not in git) loses "macOS only" from the limits once this ships.

## Checked against other tools' docs

- `secret-tool` syntax, stdin, stdout and exit codes: Debian man page and libsecret
  `tool/secret-tool.c`, checked 2026-11-03. `clear` of a missing item: to check on Ubuntu,
  builder.
- Claude Desktop Linux beta, Ubuntu 22.04+ and Debian 12+: support.claude.com, checked
  2026-11-03. Its config folder and whether Claude Code is bundled: to check on a real install,
  builder.
- Codex passes a whitelist of environment variables to stdio MCP servers: Codex config
  reference, checked 2026-11-03.
- Cursor's state folder on Linux (`~/.config/Cursor/User`): to check on a real install, builder.
- Kitden 0.1.1 to 0.4.0 are on PyPI, checked 2026-11-03, so the installer can pin a version.

## Left to the builder

- The exact shape of `system.py` and how the runner with stderr passes through `engine.py`,
  `proxy.py`, `oauth.py` and `views.py`; the call sites keep their signatures.
- Tests patch both `KITDEN_SYSTEM` (for child processes) and `kitden.system.SYSTEM`;
  `conftest.py` clears `XDG_DATA_HOME` and `XDG_CONFIG_HOME` so sandbox homes stay sandboxed.
- Whether the Ubuntu CI round trip is a pytest test marked for Linux or a workflow step.
- The order of the small edits in the test files, and which of the seven can lose their
  `Library/...` strings for the helpers without a rewrite.
- The version number, the release notes and the ROADMAP lines, written as the last step.

## Done when

- `uv run pytest -q`, `uv run ruff check .` and `node --test tests/frontend/*.test.mjs` pass on
  macOS and on the Ubuntu CI job.
- On an Ubuntu desktop (a VM or a laptop): `uvx --python 3.13 kitden demo` opens the page; with
  Claude Code and Cursor installed, `kitden` reads them, moves a server with a token into the
  gateway, the token is in the keyring (`secret-tool lookup service kitden account <server>/<key>`
  prints it), the gateway starts the server, and Undo removes the item.
- With `libsecret-tools` removed, the same move waits in preview with the keyring message and
  Apply writes the rest.
