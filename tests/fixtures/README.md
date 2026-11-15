# Test fixtures

Copies of real client settings, used to test reading and writing without touching real files.

## Layout

```text
tests/fixtures/
├── claude_code/<version>/   # for example 2.1.302/
├── codex/<version>/         # for example 0.163.0/
├── cursor/<version>/        # for example 3.21.16/
├── fake_mcp/                # a tiny MCP server that the gateway tests start
├── fake_security.py         # a stand-in for macOS `security`, so no test uses the Keychain
└── sandbox-home/            # a full fake home folder for end-to-end checks
```

Each version folder mirrors the client's real paths under a fake home, for example
`codex/0.163.0/home/.codex/config.toml`.

## Rules

- Every secret is replaced by a sentinel string that starts with `SENTINEL_SECRET_`, for example
  `SENTINEL_SECRET_GITHUB_TOKEN`. Tests fail if a sentinel appears in any output.
- No real tokens, keys, passwords, emails or private URLs.
- Keep each fixture small: only what a test needs.
- When a client changes its format, add a new version folder; keep the old one.
- The folder with the highest version of `claude_code` and of `codex` must hold every watched
  file (`WATCHED` in `tests/contract/written.py`), because the shape test compares with it. A
  fixture for one test goes into an older version's folder, or gets every watched file.

## A red night

A red `clients` job in Nightly tests has more than one cause. Tell them apart first:

- An `::error::` line: a client could not be installed, or the runner had an account.
- Another test's name: look at that test.
- `test_the_newest_client_writes_only_shapes_the_fixtures_know`: a client writes something no
  fixture knows, or stopped writing something.

For that last test, in order:

1. Read the sentences the test printed.
2. For each key they name, look how Kitden reads it (`src/kitden/clients/`). If Kitden would get
   it wrong, that is a bug: fix it first.
3. Download the run's `written-files-<os>` artifact: the files the newest clients wrote, holding
   only the parts Kitden reads, with the home's path as `{HOME}`.
4. Add it as a new version folder (`<client>/<version>/home/`). The version is in the run's
   summary.
5. Add a dated row to `docs/clients.md`.
