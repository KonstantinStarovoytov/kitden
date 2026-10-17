import copy
import json

import pytest

from agentsetup.redact import SECRET, redact, redact_text

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
