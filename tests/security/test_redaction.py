import copy
import json

import pytest

from kitden.redact import SECRET, redact, redact_line, redact_lines, redact_text

GITHUB_LIKE = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


@pytest.mark.parametrize(
    ("entry", "want", "found"),
    [
        (  # env values are secrets; pure references stay
            {"env": {"API_KEY": "SENTINEL_SECRET_A", "HOME_DIR": "${HOME}"}},
            {"env": {"API_KEY": SECRET, "HOME_DIR": "${HOME}"}},
            True,
        ),
        (  # header values are secrets in every client's spelling
            {
                "headers": {"Authorization": "Bearer SENTINEL_SECRET_B"},
                "http_headers": {"X-Key": "${env:KEY}"},
            },
            {"headers": {"Authorization": SECRET}, "http_headers": {"X-Key": "${env:KEY}"}},
            True,
        ),
        (  # Codex stores variable NAMES here, not values
            {
                "env_http_headers": {"Authorization": "GITHUB_TOKEN"},
                "bearer_token_env_var": "GITHUB_TOKEN",
                "env_vars": ["A", "B"],
            },
            {
                "env_http_headers": {"Authorization": "GITHUB_TOKEN"},
                "bearer_token_env_var": "GITHUB_TOKEN",
                "env_vars": ["A", "B"],
            },
            False,
        ),
        (  # secret query parameters and user info in URLs
            {"url": "https://api.example.com/mcp?api_key=SENTINEL_SECRET_C&region=eu"},
            {"url": "https://api.example.com/mcp?api_key=[secret]&region=eu"},
            True,
        ),
        (
            {"url": "https://user:SENTINEL_SECRET_D@host.example/mcp"},
            {"url": "https://[secret]@host.example/mcp"},
            True,
        ),
        (  # flag followed by a value, and flag=value
            {
                "args": [
                    "--api-key",
                    "SENTINEL_SECRET_E",
                    "--port",
                    "8080",
                    "--token=SENTINEL_SECRET_F",
                ]
            },
            {"args": ["--api-key", SECRET, "--port", "8080", "--token=[secret]"]},
            True,
        ),
        (  # well-known token shapes anywhere
            {"note": GITHUB_LIKE, "nested": [{"value": "sk-" + "x" * 40}]},
            {"note": SECRET, "nested": [{"value": SECRET}]},
            True,
        ),
        (  # URL without secrets keeps its exact spelling
            {"url": "https://x.example/mcp?q=a+b&region=eu%2Fwest"},
            {"url": "https://x.example/mcp?q=a+b&region=eu%2Fwest"},
            False,
        ),
        (  # nothing secret: unchanged
            {"command": "uvx", "args": ["mcp-server-time", "--local-timezone=Europe/Berlin"]},
            {"command": "uvx", "args": ["mcp-server-time", "--local-timezone=Europe/Berlin"]},
            False,
        ),
    ],
)
def test_redact(entry, want, found):
    assert redact(entry) == (want, found)


def test_redact_does_not_change_its_input():
    entry = {"env": {"API_KEY": "SENTINEL_SECRET_A"}}
    before = copy.deepcopy(entry)
    redact(entry)
    assert entry == before


def test_no_sentinel_survives_a_realistic_entry():
    entry = {
        "command": "npx",
        "args": ["-y", "@example/server", "--password", "SENTINEL_SECRET_G"],
        "env": {"DB_URL": "postgres://app:SENTINEL_SECRET_H@db/app"},
        "headers": {"Cookie": "session=SENTINEL_SECRET_I"},
        "url": "https://x.example/mcp?token=SENTINEL_SECRET_J",
    }
    redacted, found = redact(entry)
    assert found is True
    assert "SENTINEL_SECRET" not in json.dumps(redacted)


@pytest.mark.parametrize(
    "value",
    ["Bearer ${GW_KEY}", "Bearer ${env:GW_KEY}", "Basic ${AUTH}", "${A}:${B}"],
)
def test_header_values_made_of_references_stay(value):
    assert redact({"headers": {"Authorization": value}}) == (
        {"headers": {"Authorization": value}},
        False,
    )


def test_header_value_with_a_reference_and_a_secret_is_hidden():
    assert redact({"headers": {"Authorization": "${A} SENTINEL_SECRET_X"}})[0] == {
        "headers": {"Authorization": SECRET}
    }


def test_redact_text_hides_tokens_inside_free_text():
    text = f"error: bad token {GITHUB_LIKE} for Bearer abcdefgh12345 at url"
    assert redact_text(text) == f"error: bad {SECRET} for {SECRET} at url"


def test_redact_text_keeps_references_and_json_punctuation():
    text = '{"headers": {"Authorization": "Bearer ${GW_KEY}"}}'
    assert redact_text(text) == text
    assert (
        redact_text('{"Authorization": "Bearer abcdefgh12345"}')
        == f'{{"Authorization": "{SECRET}"}}'
    )


def test_secret_env_pairs_in_args_are_hidden():
    entry = {
        "args": [
            "run",
            "-e",
            "N8N_API_KEY=SENTINEL_SECRET_ARG",
            "-e",
            "LOG_LEVEL=error",
            "-e",
            "N8N_API_URL=http://host:5678",
            "-e",
            "TOKEN=${TOKEN}",
        ]
    }
    redacted, found = redact(entry)
    assert redacted["args"] == [
        "run",
        "-e",
        f"N8N_API_KEY={SECRET}",
        "-e",
        "LOG_LEVEL=error",
        "-e",
        "N8N_API_URL=http://host:5678",
        "-e",
        "TOKEN=${TOKEN}",
    ]
    assert found


def test_tokens_inside_longer_strings_are_hidden():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJlLXZhbHVl"
    redacted, found = redact({"args": [f"CONFIG={jwt}"], "command": f"run --x {GITHUB_LIKE}"})
    assert redacted == {"args": [f"CONFIG={SECRET}"], "command": f"run --x {SECRET}"}
    assert found


@pytest.mark.parametrize(
    ("line", "want"),
    [
        ("PASSWORD=hunter2hunter2", f"PASSWORD={SECRET}"),
        ("export API_KEY=abc123", f"export API_KEY={SECRET}"),
        ("password: correct horse", f"password: {SECRET}"),
        ("- token: SENTINEL_SECRET_X", f"- token: {SECRET}"),
        ("db at postgres://admin:s3cret@localhost/app", f"db at postgres://{SECRET}@localhost/app"),
        (f"use {GITHUB_LIKE} here", f"use {SECRET} here"),
        ("API_KEY=${API_KEY}", "API_KEY=${API_KEY}"),
        ('  "apiKey": "abc123secretvalue",', f'  "apiKey": {SECRET}'),
        ('{"token":"abc123secretvalue"}', f'{{"token":{SECRET}'),
        ("'password': 'hunter2hunter2'", f"'password': {SECRET}"),
        ("DB_PASS=hunter2hunter2", f"DB_PASS={SECRET}"),
        ("MYSQL_PWD=hunter2hunter2", f"MYSQL_PWD={SECRET}"),
        ("PRIVATE_KEY=abc123", f"PRIVATE_KEY={SECRET}"),
        ("cookie: session=abc123", f"cookie: {SECRET}"),
        ("key AIza" + "B" * 35 + " here", f"key {SECRET} here"),
        ("Bring your passport.", "Bring your passport."),
        ("Run `make test` before each commit.", "Run `make test` before each commit."),
        ("See https://example.com/docs for more.", "See https://example.com/docs for more."),
    ],
)
def test_redact_line_hides_secrets_in_free_text(line, want):
    assert redact_line(line) == want


def test_redact_lines_hides_values_that_span_lines():
    lines = [
        "config:",
        "  password: |",
        "    first-secret-line",
        "",
        "    second-secret-line",
        "  user: me",
        "TOKEN=",
        "  next-line-secret",
        "Done.",
    ]
    out = redact_lines(lines)
    assert out[0] == "config:" and out[5] == "  user: me" and out[8] == "Done."
    assert out[3] == ""
    assert not any("secret-line" in line or "next-line-secret" in line for line in out)


def test_redact_lines_hides_a_private_key_body():
    lines = [
        "Key:",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "b3BlbnNzaC1rZXktdjEAAAAA",
        "QyNTUxOQAAACD",
        "-----END OPENSSH PRIVATE KEY-----",
        "After.",
    ]
    out = redact_lines(lines)
    assert out[1] == lines[1] and out[4] == lines[4] and out[5] == "After."
    assert out[2] == SECRET and out[3] == SECRET
    # The end can be past the lines shown: the body is still hidden.
    assert redact_lines(lines[:3])[2] == SECRET
