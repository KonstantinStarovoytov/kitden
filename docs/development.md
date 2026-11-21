# Developing Kitden

## Develop

```bash
uv sync
uv run pytest -q
```

`uv tool install --reinstall .` gives you the `kitden` command from this folder. Contract tests
against the real clients run in sandbox homes: `uv run pytest -m contract`. Each client gets a
sandbox home, so your real settings files are never read or changed. But on a machine where you
are signed in, a real client can still find your account in the system's keychain and run as
you, and `ssh` still uses your real keys. The test keeps nothing of that: a saved copy holds only
the parts Kitden reads. Every night the contract tests also run against the newest Claude Code
and Codex, with no account (`.github/workflows/nightly.yml`, job `clients`);
`-m "contract and not signed_in"` is what runs there. The job installs the clients with the
vendors' own installers. Tests marked `signed_in` need a signed-in client. Tests can build a
sample home with `kitden.demo.build_demo_home(root, size)`.

Browser tests (`tests/browser/`) open the page on the demo sample in a real browser and press
its buttons: preview, Apply and Undo, the bar that asks for a new preview when the settings
changed under one, and a drag onto the gateway on the Gateway map. An error in the browser
console fails them, so they catch a break of the page's Content-Security-Policy. Playwright is
not a project dependency, so these tests are not in the default run. Run them with:

```bash
uv run --with playwright==1.64.1 python -m playwright install chromium
uv run --with playwright==1.64.1 python -m pytest -m browser -q
```

Use `python -m pytest`, not `pytest`: `uv run --with` can start the project's own pytest,
which has no Playwright, and then every browser test skips. The tests run in Playwright's
Chromium. `KITDEN_BROWSER=firefox` or `KITDEN_BROWSER=webkit` runs them in that engine
(install it first, as above, with `firefox` or `webkit`), and
`KITDEN_BROWSER_CHANNEL=chrome` in the Google Chrome installed on the computer. Another
value stops the run. One engine per run, so a test's name is the same in every engine.

Built with Python 3.13+, uv, Starlette and the official MCP SDK. The page is plain ES modules
and one CSS file under `src/kitden/web/static/`, with a strict Content-Security-Policy: no
framework, no bundler, nothing loaded from another site. How it looks and moves:
[design.md](design.md).

| Folder | What |
| --- | --- |
| `src/kitden/clients/` | Reading and changing each client: Claude Code, Codex, Cursor |
| `src/kitden/changes/` | Preview, Apply with backup, verify, Undo |
| `src/kitden/views/` | What the page and the MCP server show |
| `src/kitden/local_gateway/` | The Kitden gateway: settings and rules, project finding, the proxy inside `kitden mcp` |
| `src/kitden/demo/` | Sample setups for `kitden demo` and the tests, and the demo's stand-ins |
| `src/kitden/web/` | The local page |
| `plugins/kitden/` | The plugin for Claude Code and Codex |

## Tests that fail by chance

When a test fails by chance, set it aside: add its line to `tests/set-aside.txt`, as pytest
names it in its FAILED line (with the `[…]` part of a parametrized test), then two spaces, `#`,
the date and the reason:

```text
tests/unit/test_watch.py::test_x  # 2026-11-20 gave up waiting on macos-15-intel
```

The normal run leaves it out. It runs only in the nightly run's last step
(`uv run pytest -q --set-aside=only`), which never fails the job. Delete the line to take the
test back. The desk shows how many tests are set aside. To run a set-aside test by hand, add
`--set-aside=run`; without it pytest leaves the test out and runs nothing.
A browser test that is set aside runs nowhere at night: that step leaves browser tests out.
Open an issue to bring it back when you set one aside.
Contract tests are never listed there: fix them, or mark them `signed_in` when they need an
account.

## Commands

| Command | What it does |
| --- | --- |
| `kitden` / `kitden open` | Opens the page; it stops 10 minutes after its last tab closes |
| `kitden serve` | Runs the page in the terminal until Ctrl+C |
| `kitden demo [--size small\|medium\|large]` | Opens the page on a sample setup (medium if no size is given) in a temporary folder; it runs no client, starts no MCP server, uses no Keychain and stays offline; the folder is deleted when it stops |
| `kitden scan [--json]` | Prints what each client loads and whether its skill list fit in the last chat, then exits; `--json` prints what the page shows instead |
| `kitden show WHAT` | Prints one read-only answer as JSON and exits: `setup`, `findings`, `item NAME`, `projects` or `context`. The plugin's skills run it |
| `kitden mcp` | The "show my setup" server that clients start; it also offers the tools of servers moved into the Kitden gateway |

## Speed

`uv run python scripts/measure-start.py` builds the large sample setup
(`build_demo_home(root, "large")`: about 500 items, 17 projects and 12 servers in the Kitden
gateway) with fake `claude`, `codex` and `cursor` commands, then starts the page twice on a free
port. Then it starts the page on the medium sample, as `kitden demo` does. It prints four
numbers:

- **first usable**: time to the first answer of `/api/overview` while Codex's plugin list takes
  10 seconds. The start line must then say "Still checking Codex plugins". Budget: 2 s.
- **gateway view**: the time `/api/gateway-view`, the Gateway page's data, takes to answer once
  the page is up. It has no budget.
- **complete**: time until every step of the first scan is done, with the list answering at
  once. Budget: 5 s.
- **demo (medium)**: time from building the medium sample to the first answer of
  `/api/overview`. Budget: 2 s.

A missed budget gives exit code 1. The nightly's Intel Mac is slower and has twice the budgets
(`KITDEN_START_BUDGET_SCALE=2`). Times start with the page, and the demo's with building its
sample; Python's own start and a `uvx` cold start are not counted. The client versions are known
before each run, as on every start after the first: the page reads them from `versions.json` in
the data folder (`~/Library/Application Support/kitden`) and runs a client's version command
only in the background, when its binary is new or changed.

Measured: first usable 0.1 s, complete 0.1 to 0.2 s, demo under 0.1 s (checked 2026-10-23,
Apple M4 Max, macOS 26.6.2). With Python's own start, `uv run kitden demo` has its first overview
in about 0.3 s (checked 2026-10-22). On the large sample the gateway view took 5 and 7 ms in two
runs (checked 2026-10-24, Apple M4 Max, macOS 26.6.2).

The Gateway map has two marks and a layout test. `uv run python scripts/measure-start.py --probe`
builds the probe sample (the medium sample with direct servers added until the Gateway has 20
servers), starts the page on it, prints its links and waits for Ctrl+C. It opens no browser: open
the `#gateway?view=map` link in one and read the marks.

- `kitden:map-draw`, a `performance.measure`: building the map's blocks and links, not the
  browser's own layout and paint. Limit 50 ms.
- `kitden:gateway-drawn`, a `performance.mark`: the time from the start of the navigation until
  the Gateway is drawn.
- `tests/frontend/map.test.mjs` times the layout of 20 servers and of the large sample in node.
  Limit 16 ms.

Measured 2026-10-24 (Apple M4 Max, macOS 26.6.2):

- Browser pane of the Claude desktop app at 1440×900, probe sample (20 servers), 5 loads of
  `#gateway?view=map`, build c90b67f: `kitden:map-draw` 4.5, 2.8, 3.3, 2.8 and 3.1 ms (median
  3.1 ms, limit 50 ms); `kitden:gateway-drawn` 64.0, 54.9, 64.3, 58.3 and 64.2 ms from the
  start of the navigation (median 64.0 ms).
- Node, `map.test.mjs`, on the code as it is today, 3 runs: layout median 0.03 to 0.04 ms for 20
  servers and 0.11 to 0.12 ms for the large sample.

## CPU and memory

`scripts/measure-use.py` measures how much CPU and memory a `kitden` command uses. It starts
it as a child process and uses no Kitden code, so it can measure any release since 0.3.0. It
needs psutil, which is not a project dependency: run it with
`uv run --no-project --python 3.13 --with psutil==7.2.2`.

One run of the page scenario, on a sandbox home: start `kitden demo --no-browser --size large`,
wait until its first scan is done, wait 30 s, call `/api/items` 1,000 times, stop it with
SIGTERM. It notes:

- **peak memory**: the largest memory of the process (`ru_maxrss`);
- **CPU to ready**: CPU seconds (user and system) until the page says it is ready;
- **idle CPU**: CPU seconds used in the 30 s with nothing to do;
- **memory growth**: the memory after the last call minus the memory after the first 200;
- time to ready, which is not compared: it ran from 0.9 to 9.4 s for the same code on one Mac.

The numbers are taken the same way for every version, so they can be compared:

- Versions compared run in one job on one machine, in turn, and each round starts one version
  later (A B, B A, A B …), so none always runs first. Same script and Python. Each gets one
  warm-up run, thrown away, then the same number of runs.
- Each number is a median, with the lowest and highest run. Every run is kept.
- Each result keeps the installed packages of each version, the size of its sample (items and
  bytes of `/api/items`), the order of every round, and the machine: runner image, system, CPU
  model, cores, Python and psutil. When A's and B's samples differ, or a version's sample
  changed between its runs, they are not compared, and the result says why.
- `SERIES` at the top of the script holds one number per scenario. A scenario's number is
  raised with any change to what or how it measures. Numbers of two series are never
  compared, and a new page series needs a new backfill. The measurement is
  `scripts/measure-use.py`, `.github/workflows/use.yml` and
  `tests/fixtures/fake_mcp/echo_server.py`: a pull request that changes any of them may not
  change `src/kitden/`, or the check "The measurement changes alone" fails.

Run it on this machine (it makes its own sandbox homes). It builds the working tree as it
is, so commit first, or the `main@<sha>` label names a commit that was not measured:

```bash
S=$(mktemp -d)
uv venv -q --python 3.13 "$S/a" && uv pip install -q --python "$S/a/bin/python" kitden==0.9.2
uv build --wheel --out-dir "$S/dist"
uv venv -q --python 3.13 "$S/b" && uv pip install -q --python "$S/b/bin/python" "$S"/dist/*.whl
uv run --no-project --python 3.13 --with psutil==7.2.2 python scripts/measure-use.py run \
  --out "$S/night.json" --runs 2 0.9.2="$S/a/bin/kitden" "main@$(git rev-parse --short HEAD)=$S/b/bin/kitden"
uv run --no-project python scripts/measure-use.py check "$S/night.json"
```

One page run takes about 45 s; this command makes six (a warm-up and 2 runs for each
version), so about 5 minutes. macOS takes memory back from an idle process, so the memory
numbers that count come from Linux.

Every night `.github/workflows/use.yml` measures the newest release (A) and `main` (B), 5 runs
each, and keeps the numbers on the branch `use-numbers`: `nights/<date>.json`,
`releases/<version>.json`, a README with tables, and `chart.json`, which the desk page draws
as two charts, CPU to ready and peak memory by release. A warning means that B's median
peak memory is more than 15% over A's, or its CPU to ready more than 25%: a `::warning::` line
and a line in the job summary; the job stays green. A broken limit turns the job red. The
limits are `PAGE_LIMITS` at the top of the script; `None` means off, as it is until they are
set from the first 7 nights. To change a limit, change the constant in a pull request of its
own and say which nights it comes from. Started by hand with a list of versions, the workflow
measures those releases instead (a backfill), each with the dependencies of its release day,
and this commit last; the charts are redrawn from that run alone, so list every release.
A second run on the same UTC date (by hand, or a rerun) replaces that date's night file.

## Check before a release

Tests now do most of these checks; the table says which test does each. The ones against the
real clients are contract tests (`uv run pytest -m contract`) and browser tests
(`pytest -m browser`), run as [Develop](#develop) says. The nightly run
(`.github/workflows/nightly.yml`) runs them every night: the contract tests in its job
`clients`, the browser tests in `browser`, and the real Keychain and keyring tests in `systems`.
"The tester" below is a planned nightly run with a signed-in client; until it exists, the checks
that need one are done by hand.

### What became of the 24 checks

"Test" means tests do the check; where they prove only part of it, the last column says what
is left unproven, and the paragraph after the hand checks for adding and removing names what no
test and no hand check covers yet. "Signed-in client" means it needs a client that is signed
in, which no runner has, so it is still done by hand (see below). A stand-in session is
`kitden mcp` started as the client starts it, with the client's signal, but not the client's
own session.

| # | Check | Done by | Run by |
|---|---|---|---|
| 1 | Move a server into the gateway; set up the `kitden` entry | test | `tests/contract/test_gateway_session.py::test_a_moved_server_is_what_each_client_lists_and_its_tools_come_through`, with the real `claude` and `codex` |
| 2 | Turn one tool off for the test project | test | `tests/contract/test_gateway_session.py::test_a_tool_off_for_the_project_is_gone_there_and_stays_elsewhere` |
| 3 | A new session there: the tool is gone, the others stay | signed-in client | By hand until the tester runs it. Kitden's side: `tests/contract/test_gateway_session.py::test_a_tool_off_for_the_project_is_gone_there_and_stays_elsewhere`, with a stand-in session for each client |
| 4 | Undo the switch and the move; the server is direct again | test | `tests/contract/test_gateway_session.py::test_undo_puts_every_file_back_and_the_clients_list_the_server_again` undoes the move; `tests/unit/test_local_gateway_views.py::test_a_rule_change_previews_applies_and_undoes` undoes a tool turned off for one project and checks `gateway.json` is as before |
| 5 | Strict mode ("Turn strict mode on…"): a new session offers only the tools that are on | signed-in client | By hand until the tester runs it. Kitden's side: `tests/contract/test_gateway_session.py::test_strict_mode_offers_only_the_tools_set_on`, with a stand-in session for each client |
| 6 | An open session is refused a tool turned off, and gets it back | signed-in client | By hand until the tester runs it. Kitden's side: `tests/contract/test_gateway_session.py::test_an_open_session_is_refused_a_tool_turned_off_and_gets_it_back`, with a stand-in session for Claude Code |
| 7 | Undo the switches and the move | test | `tests/contract/test_gateway_session.py::test_undo_puts_every_file_back_and_the_clients_list_the_server_again` (the move); `tests/contract/test_gateway_session.py::test_an_open_session_is_refused_a_tool_turned_off_and_gets_it_back` (a tool turned off for all projects); `tests/unit/test_api_changes.py::test_gateway_strict_previews_applies_and_undoes` (strict mode) |
| 8 | Remove a plugin in Claude Code, then in Codex; Undo | test | `tests/contract/test_manage_items.py::test_a_removed_plugin_leaves_the_clients_list_and_undo_brings_it_back`, in both; it reads the client's plugin list, not a new session |
| 9 | Remove a skill; Undo: its folder is back | test | `tests/unit/test_remove_skill.py::test_removing_a_skill_backs_it_up_and_undo_copies_it_back`; a client loads a skill only from its folder |
| 10 | "Put back in <client>…" a held server, remove it from the gateway | test | `tests/contract/test_gateway_session.py::test_a_server_put_back_and_removed_from_the_gateway`; it reads `claude mcp get` and an open session's refused call, not a new session reaching the server directly |
| 11 | "+ Add" a server with a `${VAR}` header into Cursor and Codex; a new session reaches it | signed-in client | By hand until the tester runs it. Tested: Codex lists the added entry with the variable, not its value: `tests/contract/test_manage_items.py::test_a_server_with_a_variable_header_is_listed_by_codex_with_the_variable`. Not tested: Cursor, and a session reaching the server |
| 12 | "Add to this project…" a skill and a plugin; only that folder has them | test | `tests/contract/test_manage_items.py::test_add_to_this_project_shows_in_that_folder_only` (a Claude Code plugin; it reads the client's plugin list, not a new session); `tests/unit/test_project_add.py::test_a_skill_goes_into_the_project_folder` (the skill goes into that project's folder, shows for that project only, and Undo removes it; a client loads a skill only from its folder) |
| 13 | "Add missing plugins and skills…", Apply, Undo | test | `tests/contract/test_manage_items.py::test_add_missing_adds_a_plugin_and_a_server_together_and_undo_removes_both` (a plugin and a server into Codex); `tests/unit/test_align.py::test_add_missing_is_one_change_and_undo_takes_it_all_back` (a skill into Codex's project folder and a server into Claude Code, and Undo puts every file back). Not tested: a plugin or a skill added into Claude Code |
| 14 | Remove a plugin that is off; Undo: back and still off | test | `tests/contract/test_manage_items.py::test_a_removed_off_plugin_comes_back_off`, in Claude Code and Codex; it reads the client's plugin list, not a new session |
| 15 | Remove a plugin that is on for one project only | test | `tests/contract/test_manage_items.py::test_a_project_only_plugin_is_uninstalled_in_its_project`; it reads the client's plugin list, not a new session |
| 16 | Codex: remove a plugin, Undo; add a plugin and a server together, Undo | test | `tests/contract/test_manage_items.py::test_codex_remove_deletes_the_plugins_table_and_add_writes_it_back`; `tests/contract/test_manage_items.py::test_add_missing_adds_a_plugin_and_a_server_together_and_undo_removes_both` |
| 17 | A token moved in becomes a Keychain item; `gateway.json` holds a reference | test | `tests/unit/test_real_secrets.py::test_a_move_stores_the_token_and_leaves_a_reference`, real Keychain and real keyring |
| 18 | A new session: the server's tools work | test | `tests/unit/test_real_secrets.py::test_a_session_gets_the_secret_from_the_real_store`, a stand-in session with the real Keychain and keyring |
| 19 | Undo the move: the Keychain item is gone | test | `tests/unit/test_real_secrets.py::test_undo_of_the_move_removes_the_item` |
| 20 | "Move secrets to the Keychain…" moves a plain token | test | `tests/unit/test_real_secrets.py::test_a_plain_token_in_gateway_json_moves_to_the_keychain` |
| 21 | `security` facts: any value comes back whole, a long one is refused | test | On macOS runners: `tests/unit/test_real_secrets.py::test_a_missing_item_ends_with_44`, `tests/unit/test_real_secrets.py::test_a_value_with_quotes_and_spaces_comes_back_unchanged`, `tests/unit/test_real_secrets.py::test_a_value_with_a_quote_comes_back_unchanged` (`a"b`), `tests/unit/test_real_secrets.py::test_a_value_with_a_backslash_comes_back_unchanged` (`a\b`), `tests/unit/test_real_secrets.py::test_an_account_with_a_space_is_quoted_on_the_security_line`, `tests/unit/test_real_secrets.py::test_a_value_in_other_alphabets_comes_back_unchanged`, `tests/unit/test_real_secrets.py::test_a_value_with_no_ascii_letter_comes_back_unchanged`, `tests/unit/test_real_secrets.py::test_a_4_kb_value_comes_back_unchanged`. A secret in any characters comes back whole: Kitden reads `find-generic-password -g`, whose `0x` form tells a value's hex from the value. `security` cuts a `-i` line longer than 4,095 bytes, so on macOS Kitden refuses a secret longer than about 1,970 bytes before it writes anything, with "The secret <server>/<key> is too long for the Keychain: …", and the item that was there stays as it was; the 4 KB test checks that refusal (`tests/unit/test_real_secrets.py::test_the_longest_value_that_fits_comes_back_whole` and `tests/unit/test_real_secrets.py::test_one_byte_more_is_refused_and_nothing_is_stored` check the edge; seen 2026-11-15 on a GitHub macOS runner). With a stand-in `security`, the move is refused at preview and the files are unchanged: `tests/unit/test_local_gateway_move.py::test_a_secret_too_long_for_the_keychain_is_refused_at_preview`. On Linux the same values, 4 KB too, come back whole |
| 22 | With Claude Code open, put back a server with a token; the entry stays | signed-in client | By hand until the tester runs it. Part of it: `tests/contract/test_manage_items.py::test_an_entry_kitden_wrote_itself_survives_the_clients_own_write`: "+ Add" (`mcp.add`) of a server with a token into Claude Code writes `~/.claude.json` with no command, the entry outlives `claude mcp add-json` rewriting the file, and Undo keeps the rest. Not tested: "Put back" with Claude Code open |
| 23 | Settings change under an open preview: "Preview again", Cancel | test | `tests/browser/test_preview_drift.py::test_settings_changed_under_a_preview_ask_for_a_new_one_and_cancel_writes_nothing`; it writes the settings file as Claude Code would, and does not run Claude Code |
| 24 | Drag a server onto the gateway on the map, Apply, Undo from the toast | test | `tests/browser/test_map_drag.py::test_a_server_dragged_onto_the_gateway_is_moved_and_undo_from_the_toast_moves_it_back`: drag, Apply and Undo. Not tested here: a new session reaching the server through the gateway, which is part of check 3 |
| — | Linux: 17 to 19 on an Ubuntu desktop | test | The tests of 17 to 19 on Ubuntu x64 and ARM, nightly job `systems`; a keyring that is down: `tests/unit/test_local_gateway_move.py::test_on_linux_a_keyring_that_is_down_refuses_the_review`, a unit test with a stand-in `secret-tool`, not run against Ubuntu's keyring: the move is refused at preview with "Kitden could not reach the keyring." and the files are unchanged |

Two checks stay by hand for good: they are in the Cursor IDE, and Cursor needs its window and
an account, which no runner has (checked 2026-11-14). Five more, the checks for a signed-in
client, are by hand until the tester runs them. Do them all on a test project (a
throwaway folder; never your own project). Kitden must know the project: open it once in the
client, so that it shows in the page's project list. For Cursor, check the IDE, which names the
project to the gateway; Cursor's command line does not (checked 2026-10-21).

Before a release that touches the Kitden gateway, check these once by hand, on a test project
(the tester is a planned nightly run with a signed-in client):
1. In the Cursor IDE: move a server in, turn one tool off for the project, see in a new chat
   that the tool is gone, undo.
2. Check 3, in Claude Code and in Codex: move a server with a few tools into the gateway and
   turn one tool off for the project. A new session there does not have that tool and has the
   others (until the tester runs it)
3. Check 5, in each: turn strict mode on in the server's Details ("Turn strict mode on…") and
   turn one tool off. A new session offers only the tools that are on (until the tester runs it)
4. Check 6, in each: in a session that is already open, call a tool you turn off. It is refused
   with "<name> is turned off in Kitden."; turn it on again and the call works in the same
   session. Undo the switches and the move (until the tester runs it)

Before a release that adds, removes or puts back items, also check these once by hand (the
tester is a planned nightly run with a signed-in client):
1. In the Cursor IDE: a server added from Claude Code with a `${VAR}` header answers in a new
   chat; "Add missing plugins and skills…" shows in a new chat; undo.
2. Check 11, in Codex: "+ Add" a server whose header reads a `${VAR}` from Claude Code into
   Codex. A new session reaches it (until the tester runs it)

No test or hand check covers yet: a new session after a plugin is removed, brought back or
added to a project (checks 8, 12, 14 and 15; the tests read the client's plugin list), a new
session after a server is put back (check 10; the test reads `claude mcp get`), and a plugin
or a skill that "Add missing plugins and skills…" adds into Claude Code (check 13; the tests
add into Codex, and a server into Claude Code).

Before a release that touches secrets, also check this once by hand (the tester is a planned
nightly run with a signed-in client):
1. Check 22: with Claude Code open, "Put back in Claude Code…" a held server that has a token.
   Use Claude Code for a minute, then check the entry is still in `~/.claude.json` and a new
   session has the server. Undo; the entry is gone and the rest of the file is kept
   (until the tester runs it)

The Keychain is not fully proven. Its tests (checks 17 to 21) run every night against the real
Keychain on macOS and the real keyring on Linux. A secret in any characters comes back whole on
both. On macOS a secret longer than about 1,970 bytes cannot be stored, because `security` cuts a
longer line (seen 2026-11-15 on a GitHub macOS runner): Kitden refuses it before it writes
anything, says "The secret <server>/<key> is too long for the Keychain: …", and the item that
was there stays as it was. That holds for an OAuth sign-in too, which keeps its tokens and its
client in one item: one that long cannot be kept on macOS, and a token in a header is the way
out where the server takes one. Linux has no such limit. Check 18 runs with a stand-in
session and a keychain made for the run, which never asks for a password; a gateway started by
a real client and reading the login Keychain is not tested. A Linux keyring that is down is
tested only in a unit test with a stand-in `secret-tool`.

## Release

A release is one pull request. You review it and merge it; the rest happens on its own.

1. In GitHub, open Actions → Release prep → Run workflow, on `main`. Keep the version on
   **Auto** and the agent picks the next minor or patch, or pick **Features (0.X.0)** for the
   next minor or **Fixes (0.0.X)** for the next patch. The run opens one pull request,
   "Kitden X.Y.Z": the version in all eight places, `docs/releases/vX.Y.Z.md`, ROADMAP
   ("### Not yet released" becomes the version), README and policy edits, the guide and the
   plugin README when they change, and the checks from
   [Check before a release](#check-before-a-release) that this release touches. Every README
   picture is recorded again. A still (PNG) goes in when it differs; an animation (WebP) goes
   in only when a file of the page changed after it was last made. The pull request is a
   draft when a check still fails after the one fix, or a picture could not be made; "Fix
   before merge" lists what is left.
2. Review the pull request, do those checks, and fix anything with commits on its branch.
3. Merge it with a merge commit, not squash: the notes link the branch's commits.

Then, with no step from you:

- `release.yml` on `main` sees a version that has notes and no tag, and tags it with the
  release app, Kitden Beacon.
- The tag's run checks everything again, publishes to PyPI with trusted publishing and
  creates the GitHub release with the notes file as its text.
- kitden-sdlc's publish workflow then publishes `server.json` to the
  [MCP Registry](https://registry.modelcontextprotocol.io), moves the `release` branch to the
  tag, and opens the formula pull request in the
  [Homebrew tap](https://github.com/KonstantinStarovoytov/homebrew-tap), where `brew pr-pull`
  merges it and makes the bottles. When the dependencies changed, the tap's daily autobump
  opens that pull request the next day instead. The run's summary shows each store's version.
- Both of Kitden's plugin marketplaces read the plugin from the `release` branch. The
  marketplace files are still read from `main`; their plugin entry is a `git-subdir` source
  with `"ref": "release"`, which Claude Code and Codex both support (checked 2026-11-12:
  Claude Code's "Create a marketplace" docs, Codex's "Build plugins" docs). The Claude plugin
  directory reads it from `release` once you set its tracked branch to `release`.
- Once a day, Release watch (`release-watch.yml`) opens an issue when a store is behind or
  different, and "Time for a release?" when merged changes wait for a release. When a job
  failed, its issue says which one to re-run.

Two steps stay by hand, only when you are told:

- **The Claude plugin directory:** when the release pull request or the run's summary says
  so, change the Listing tab or the "collects user data" switch in the directory's settings.
- **The GitHub description:** when Release watch says it differs, set the repository's
  description (the gear next to About) to `short` in `listing.toml`.

`listing.toml` holds each name and description once: PyPI, `server.json`, both `plugin.json`
files, the marketplace and the Homebrew `desc`. kitden-sdlc's release check fails a pull
request when a file differs from it or a text breaks a store's limit.

The notes, `docs/releases/vX.Y.Z.md`, are plain notes for users about everything since the
last tag, in this order: the title `# Kitden X.Y.Z — <theme>`, a short overview, the sections
New, Better, Fixed and Documentation (leave out empty ones; each item links its pull request
and author), "## Upgrade and limits", a `<details>` block with every other commit, and the
`**Full changelog:**` link.

On every push and pull request the workflow runs ruff, the type check (`pyright`), the
Python tests with a 94% coverage floor, the page's tests (`node --test
tests/frontend/*.test.mjs`), the start-time budget (`scripts/measure-start.py`), a dependency
audit (`pip-audit`), a check of the workflow files (`zizmor`), the release check and the
package build. On a tag it also stops if the version differs from the tag or the notes file is
missing. A pull request that changes the page or the recorder also runs the scenes check
(`.github/workflows/scenes.yml`): it records every README picture and uploads them as the
artifact `scenes`.
Once a day the tests also run on the newest versions of the dependencies
(`.github/workflows/latest-deps.yml`): people who install Kitden get those, not the ones in
`uv.lock`.
Every night the tests also run on four systems and two Pythons
(`.github/workflows/nightly.yml`): macOS on ARM and on Intel, Ubuntu on x64 and on ARM, each
with Python 3.13 and 3.14. The `browser` job of the same workflow runs the browser tests in
Chromium on Ubuntu. The `engines` job runs them again in Google Chrome and Firefox on Ubuntu
and in WebKit on macOS.
When a job of either scheduled run is red, the desk in kitden-sdlc opens a `ci-failure` issue
for it, rewrites it each day and closes it when the job is green again.
`README.md` is also the PyPI page. [README media](readme-media.md) says how its pictures are
made, how their addresses work on GitHub and PyPI, and what to check before promoting a release.

## Gateways

- **Kitden gateway** — four files in `~/Library/Application Support/kitden` (mode 700):
  `gateway.json` (mode 600) holds the servers and rules, `gateway-tools.json` the tool lists,
  `gateway-calls.json` the count and last time (UTC) of each tool's forwarded calls, never what
  was sent, and `gateway-names.json` which server each bare tool name belongs to, so a server
  added later cannot take it. Only `gateway.json` changes through review and Undo; the other
  three are found data that the gateway and Rescan write. The gateway reads `gateway.json` again on each call, so a tool
  turned off is refused at once; if the file cannot be read, the rules it started with apply. It
  keeps references, not secrets: each non-empty env value or header that would be hidden is a Keychain item
  (service `kitden`, account `<server>/<key>`), and `gateway.json` holds `{"keychain": "<server>/<key>"}`.
  The gateway reads the items when it starts a server. Kitden calls `/usr/bin/security`; the
  env variables `KITDEN_SECURITY` and `KITDEN_SECRET_TOOL` replace the paths only when Kitden
  runs from a source checkout (tests); a release, installed in site-packages, ignores them. `kitden mcp` finds the project once, at start: the `CLAUDE_PROJECT_DIR` variable, then
  the client's roots, then `WORKSPACE_FOLDER_PATHS`, then its start folder. Codex keeps a tool
  list for up to 30 minutes and ignores "list changed" (checked 2026-10-21), so the offered list
  is fixed for a session; a tool turned off is still refused at once.

## Linux and Windows

Linux runs as macOS does; `kitden/system.py` is the one place that knows where each system keeps
things, and secrets go to the keyring through `secret-tool`. To run the suite as Linux on a Mac:
`KITDEN_SYSTEM=linux uv run pytest -q`. The Ubuntu job in CI is the real check: it runs every
test there and one real keyring round trip (`tests/unit/test_real_keyring.py`). Tests that are
about macOS words or `security` command lines say so with `pytestmark =
pytest.mark.usefixtures("as_mac")`.

Windows is not supported yet: `install.ps1` stops with a message.

## Planned AI review of forks

The current `agents-review.yml` calls kitden-sdlc directly and skips forks. The
[new design](https://github.com/KonstantinStarovoytov/kitden-sdlc/blob/main/docs/fork-review-design.md)
replaces that with a secret-free gate and a trusted receiver. PR source is inert review
data; tests run only in separate unprivileged CI. Models, effort, cross-file context,
finding history and the single Lantern comment must be preserved.

Implementation order, security cases, paired evals and rollback are in the
[rollout plan](https://github.com/KonstantinStarovoytov/kitden-sdlc/blob/main/docs/fork-review-plan.md).
Activation updates the two callers, their full-SHA pins and the AI policy together.
This is a documentation proposal; no runtime or client-setting behaviour changes.
