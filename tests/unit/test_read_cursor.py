from agentsetup.clients.cursor import REACTIVE_KEY, CursorAdapter
from agentsetup.model import SourceKind, UnknownReason
from tests.conftest import (
    CURSOR_DB,
    all_text,
    cursor_state_rows,
    make_home,
    rows,
    write_cursor_state,
)

FIXTURE = "cursor/3.21.16"

OWN = {
    ("cursor", "mcp_server", "Neon", "user", "on", None),
    ("cursor", "mcp_server", "n8n-mcp", "user", "on", None),
    ("cursor", "mcp_server", "site-db", "project", "on", "work/site"),
    ("cursor", "skill", "docker-expert", "user", "on", None),
    ("cursor", "plugin", "langfuse@cursor-public", "user", "unknown", None),
    ("cursor", "plugin", "superpowers@cursor-public", "user", "unknown", None),
    (
        "cursor",
        "plugin",
        "1 plugin installed (name not stored locally)",
        "project",
        "unknown",
        "work/site",
    ),
    ("cursor", "marketplace", "team-mkt", "user", "on", None),
    ("cursor", "hook", "afterFileEdit", "user", "on", None),
}
CROSS_LOADED = {
    ("cursor", "skill", "brandkit", "user", "on", None),
    ("cursor", "skill", "langfuse", "user", "on", None),
    ("cursor", "plugin", "superpowers@claude-plugins-official", "user", "on", None),
    ("cursor", "hook", "PreToolUse: Bash", "user", "on", None),
}


def _scan(tmp_path, no_version, extra_rows=None):
    home = make_home(tmp_path, FIXTURE)
    write_cursor_state(home, {**cursor_state_rows(home), **(extra_rows or {})})
    return home, CursorAdapter(home, read_version=no_version).scan()


def test_scan_includes_items_cursor_reads_from_other_clients(tmp_path, no_version):
    home, scan = _scan(tmp_path, no_version)
    assert rows(scan.items, home) == OWN | CROSS_LOADED
    assert scan.problems == []


def test_cross_loaded_items_name_the_client_that_owns_them(tmp_path, no_version):
    home, scan = _scan(tmp_path, no_version)
    owners = {
        i.name: (i.source.kind, i.source.owner_client)
        for i in scan.items
        if i.name in {"brandkit", "langfuse", "docker-expert"}
    }
    assert owners == {
        "brandkit": (SourceKind.OTHER_CLIENT_FOLDER, "claude_code"),
        "langfuse": (SourceKind.OTHER_CLIENT_FOLDER, "codex"),
        "docker-expert": (SourceKind.FOLDER, "shared"),
    }


def test_turning_off_third_party_imports_removes_cross_loaded_items(tmp_path, no_version):
    home, scan = _scan(
        tmp_path, no_version, {REACTIVE_KEY: {"thirdPartyExtensibilityEnabled": False}}
    )
    assert rows(scan.items, home) == OWN


def test_secret_rows_and_values_never_appear(tmp_path, no_version):
    _, scan = _scan(tmp_path, no_version)
    assert "SENTINEL_SECRET" not in all_text(scan)
    assert {i.name for i in scan.items if i.secret_present} == {"n8n-mcp"}


def test_broken_state_database_is_reported_and_cache_still_read(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    db = home / CURSOR_DB
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a database")
    scan = CursorAdapter(home, read_version=no_version).scan()
    assert [(p.path, p.unknown_reason) for p in scan.problems] == [
        (str(db), UnknownReason.UNRECOGNIZED_FORMAT)
    ]
    assert ("cursor", "plugin", "langfuse@cursor-public", "user", "unknown", None) in rows(
        scan.items, home
    )
