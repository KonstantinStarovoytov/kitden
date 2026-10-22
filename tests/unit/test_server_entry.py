"""An entry written as each client writes it (spec 3.3, 3.4)."""

import re

import pytest

from kitden.changes.server_entry import translate_entry

FILES = {"command": "npx", "args": ["files-mcp"], "env": {"FILES_TOKEN": "SENTINEL_SECRET_FILES"}}
REMOTE = {
    "url": "https://api.invalid/mcp",
    "headers": {"Authorization": "Bearer SENTINEL_SECRET_R"},
}


def test_a_held_local_entry_in_each_client():
    assert translate_entry(FILES, "claude_code") == {"type": "stdio", **FILES}
    assert translate_entry(FILES, "codex") == FILES
    assert translate_entry(FILES, "cursor") == FILES
    waits = {**FILES, "startup_timeout_sec": 45}
    assert translate_entry(waits, "codex") == waits
    assert translate_entry(waits, "claude_code") == {"type": "stdio", **FILES}
    assert translate_entry(waits, "cursor") == FILES


def test_a_held_remote_entry_in_each_client():
    assert translate_entry(REMOTE, "claude_code") == {"type": "http", **REMOTE}
    assert translate_entry(REMOTE, "codex") == {
        "url": REMOTE["url"],
        "http_headers": REMOTE["headers"],
    }
    assert translate_entry(REMOTE, "cursor") == REMOTE


def test_a_wrong_shape_or_client_is_refused():
    with pytest.raises(ValueError, match="^The entry could not be read.$"):
        translate_entry({"command": "npx", "env": {"KEY": {"keychain": "files/KEY"}}}, "codex")
    with pytest.raises(ValueError, match="^The entry could not be read.$"):
        translate_entry({"command": "npx", "args": ["a", 1]}, "cursor")
    with pytest.raises(ValueError, match="^The entry could not be read.$"):
        translate_entry({"args": ["a"]}, "cursor")
    with pytest.raises(ValueError, match="cannot take an MCP entry"):
        translate_entry(FILES, "claude_desktop_code_tab")


def test_a_project_folder_takes_the_clients_own_form():
    for placeholder in ("${workspaceFolder}", "${CLAUDE_PROJECT_DIR}", "${CLAUDE_PROJECT_DIR:-.}"):
        entry = {"command": "npx", "args": ["p-mcp", f"{placeholder}/src"]}
        assert translate_entry(entry, "claude_code")["args"] == [
            "p-mcp",
            "${CLAUDE_PROJECT_DIR:-.}/src",
        ]
        # Cursor's ${workspaceFolder} in its user file is the home folder, not the project.
        for client, words in (("codex", "Codex"), ("cursor", "Cursor")):
            with pytest.raises(
                ValueError, match=f"^{words} cannot fill in the project folder this server needs.$"
            ):
                translate_entry(entry, client)


API = {
    "type": "http",
    "url": "https://api.invalid/mcp",
    "headers": {"Authorization": "Bearer ${API_KEY}"},
}


def test_a_reference_is_kept_where_the_client_can_read_it():
    assert translate_entry(API, "claude_code") == API
    assert translate_entry(API, "cursor") == {
        "url": API["url"],
        "headers": {"Authorization": "Bearer ${env:API_KEY}"},
    }
    assert translate_entry(API, "codex") == {"url": API["url"], "bearer_token_env_var": "API_KEY"}
    other = {"url": API["url"], "headers": {"X-Key": "${X_KEY}"}}
    assert translate_entry(other, "codex") == {
        "url": API["url"],
        "env_http_headers": {"X-Key": "X_KEY"},
    }
    env = {"command": "npx", "args": ["x"], "env": {"HOME_TOKEN": "${HOME_TOKEN}"}}
    assert translate_entry(env, "codex") == {
        "command": "npx",
        "args": ["x"],
        "env_vars": ["HOME_TOKEN"],
    }
    assert translate_entry(env, "cursor") == {
        "command": "npx",
        "args": ["x"],
        "env": {"HOME_TOKEN": "${env:HOME_TOKEN}"},
    }
    with_default = {"command": "npx", "args": ["${DIR:-/tmp}"]}
    assert translate_entry(with_default, "claude_code") == {"type": "stdio", **with_default}


def test_a_reference_the_client_cannot_read_is_refused_with_the_spec_words():
    shelled = {"command": "npx", "args": ["x", "${TOKEN}"]}
    with pytest.raises(
        ValueError, match=r"^Codex cannot read `\$\{TOKEN\}` from your shell; put the value in\.$"
    ):
        translate_entry(shelled, "codex")
    with pytest.raises(
        ValueError,
        match=r"^Cursor cannot read `\$\{TOKEN\}` from your shell; put the value in\.$",
    ):
        translate_entry({"url": "https://a.invalid/mcp", "headers": {"A": "${TOKEN:-x}"}}, "cursor")
    # A default may hold a secret: the reason names only the variable.
    secret = "sk-live-SENTINEL_SECRET_DEFAULT_0123456789"
    for client in ("cursor", "codex"):
        with pytest.raises(ValueError) as refused:
            translate_entry({"command": "npx", "args": [f"--key=${{TOKEN:-{secret}}}"]}, client)
        assert secret not in str(refused.value) and "`${TOKEN}`" in str(refused.value)
    with pytest.raises(ValueError, match=r"^Codex cannot read `\$\{OTHER\}` from your shell"):
        translate_entry({"command": "npx", "env": {"KEY": "${OTHER}"}}, "codex")


def test_the_other_clients_forms_are_read_into_the_canonical_shape():
    codex = {
        "url": "https://t.invalid/mcp",
        "bearer_token_env_var": "TOKEN",
        "env_http_headers": {"X": "X_KEY"},
    }
    assert translate_entry(codex, "claude_code") == {
        "type": "http",
        "url": codex["url"],
        "headers": {"Authorization": "Bearer ${TOKEN}", "X": "${X_KEY}"},
    }
    assert translate_entry({"command": "npx", "env_vars": ["HOME_TOKEN"]}, "claude_code") == {
        "type": "stdio",
        "command": "npx",
        "env": {"HOME_TOKEN": "${HOME_TOKEN}"},
    }
    cursor = {"command": "npx", "env": {"KEY": "${env:KEY}"}}
    assert translate_entry(cursor, "claude_code") == {
        "type": "stdio",
        "command": "npx",
        "env": {"KEY": "${KEY}"},
    }
    assert translate_entry(cursor, "codex") == {"command": "npx", "env_vars": ["KEY"]}
    timed = {"command": "npx", "startup_timeout_sec": 20, "tool_timeout_sec": 90, "enabled": True}
    assert translate_entry(timed, "codex") == {k: v for k, v in timed.items() if k != "enabled"}
    assert translate_entry(timed, "cursor") == {"command": "npx"}


@pytest.mark.parametrize(
    "entry, client, words",
    [
        (
            {"command": "npx", "envFile": "/opt/app/.env"},
            "codex",
            "The entry reads values from a file or a helper program; put the values in.",
        ),
        (
            {"url": "https://h.invalid/mcp", "headersHelper": "/opt/h"},
            "cursor",
            "The entry reads values from a file or a helper program; put the values in.",
        ),
        (
            {"command": "uv", "args": ["run"], "enabled": False},
            "claude_code",
            "The entry is turned off; turn it on first.",
        ),
        (
            {"command": "uv", "enabled_tools": ["draw"]},
            "cursor",
            "The entry keeps some tools off. Move it into the gateway to share it with its "
            "switches.",
        ),
        (
            {"type": "sse", "url": "https://s.invalid/sse"},
            "codex",
            "Codex cannot use an SSE connection from here.",
        ),
        (
            {"url": "https://s.invalid/sse"},
            "codex",
            "Codex cannot use an SSE connection from here.",
        ),
        (
            {"type": "ws", "url": "wss://w.invalid/mcp"},
            "cursor",
            "Cursor cannot use a WebSocket connection from here.",
        ),
        (
            {"command": "npx", "cwd": "/opt/app"},
            "cursor",
            "Cursor has no setting for a start folder.",
        ),
        (
            {"command": "npx", "cwd": "/opt/app"},
            "claude_code",
            "Claude Code has no setting for a start folder.",
        ),
        ({"command": "npx", "mystery": 1}, "codex", "Kitden does not know the setting mystery."),
    ],
)
def test_what_cannot_be_copied_is_refused_with_the_reason(entry, client, words):
    with pytest.raises(ValueError, match=f"^{re.escape(words)}$"):
        translate_entry(entry, client)


def test_sse_and_a_start_folder_are_kept_where_the_client_has_them():
    sse = {"type": "sse", "url": "https://s.invalid/sse"}
    assert translate_entry(sse, "claude_code") == sse
    # Cursor reads SSE from a url entry; it has no type for it.
    assert translate_entry(sse, "cursor") == {"url": sse["url"]}
    assert translate_entry({"command": "npx", "cwd": "/opt/app"}, "codex") == {
        "command": "npx",
        "cwd": "/opt/app",
    }


def test_cursors_own_variables_stay_in_cursor():
    for variable in ("userHome", "workspaceFolder", "workspaceFolderBasename", "pathSeparator"):
        entry = {"command": "npx", "args": [f"${{{variable}}}/data"]}
        for client, words in (("claude_code", "Claude Code"), ("codex", "Codex")):
            with pytest.raises(ValueError) as refused:
                translate_entry(entry, client, source="cursor")
            assert str(refused.value) == (
                f"The entry uses a Cursor variable (`${{{variable}}}`) that {words} cannot read."
            )
    env = {"command": "npx", "env": {"KEY": "${env:KEY}"}}
    assert translate_entry(env, "codex", source="cursor") == {"command": "npx", "env_vars": ["KEY"]}


def test_a_codex_literal_stays_plain_text():
    entry = {"command": "npx", "env": {"PASS": "a${B}c", "KEY": "${KEY}"}}
    # Codex fills in nothing, so `${KEY}` is text there, not a reference.
    assert translate_entry(entry, "cursor", source="codex") == entry
    with pytest.raises(ValueError) as refused:
        translate_entry(entry, "claude_code", source="codex")
    assert (
        str(refused.value) == "The entry holds `${B}` as plain text; Claude Code would fill it in."
    )
    with pytest.raises(ValueError, match="Cursor would fill it in"):
        translate_entry({"command": "npx", "args": ["${userHome}"]}, "cursor", source="codex")
    # Codex's own reference keys are still references.
    assert translate_entry(
        {"command": "npx", "env_vars": ["K"]}, "claude_code", source="codex"
    ) == {
        "type": "stdio",
        "command": "npx",
        "env": {"K": "${K}"},
    }
