# Test fixtures

Copies of real client settings, used to test reading and writing without touching real files.

## Layout

```text
tests/fixtures/
├── claude_code/<version>/   # for example 2.1.302/
├── codex/<version>/         # for example 0.163.0/
├── cursor/<version>/        # for example 3.21.16/
├── fake_mcp/                # a tiny MCP server that the gateway tests start
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
