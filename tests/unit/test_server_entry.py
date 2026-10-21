"""A held entry written as each client writes it (spec 3.3)."""

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
        assert translate_entry(entry, "cursor")["args"] == ["p-mcp", "${workspaceFolder}/src"]
        with pytest.raises(ValueError, match="^Codex cannot fill in the project folder"):
            translate_entry(entry, "codex")
