from agentsetup.clients.codex import CodexAdapter
from agentsetup.model import UnknownReason
from tests.conftest import all_text, make_home, rows

FIXTURE = "codex/0.159.2"

EXPECTED = {
    ("codex", "mcp_server", "neon", "user", "on", None),
    ("codex", "mcp_server", "langfuse-data", "user", "on", None),
    ("codex", "mcp_server", "aseprite", "user", "off", None),
    ("codex", "mcp_server", "api-docs", "project", "on", "work/api"),
    ("codex", "mcp_server", "neon", "project", "on", "work/api"),
    ("codex", "mcp_server", "evil", "project", "off", "work/untrusted"),  # untrusted: not loaded
    ("codex", "plugin", "browser@openai-bundled", "user", "on", None),
    ("codex", "plugin", "pdf@openai-primary-runtime", "user", "off", None),
    ("codex", "plugin", "gmail@openai-curated-remote", "user", "unknown", None),
    ("codex", "marketplace", "openai-bundled", "user", "on", None),
    ("codex", "skill", "pixel-art", "user", "off", None),
    ("codex", "skill", "docker-expert", "user", "on", None),
    ("codex", "skill", "langfuse", "user", "on", None),
    ("codex", "skill", "api-style", "project", "on", "work/api"),
}


def test_scan_lists_every_item_with_scope_and_state(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    scan = CodexAdapter(home, read_version=no_version).scan()
    assert rows(scan.items, home) == EXPECTED
    assert scan.problems == []


def test_secret_headers_are_hidden(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    scan = CodexAdapter(home, read_version=no_version).scan()
    assert "SENTINEL_SECRET" not in all_text(scan)
    assert {i.name for i in scan.items if i.secret_present} == {"langfuse-data"}


def test_untrusted_project_is_known_but_its_servers_are_off(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    scan = CodexAdapter(home, read_version=no_version).scan()
    paths = {p.path.removeprefix(str(home) + "/") for p in scan.projects}
    assert paths == {"work/api", "work/untrusted"}


def test_broken_config_is_reported_and_skills_still_read(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    config = home / ".codex/config.toml"
    config.write_text("[mcp_servers.neon\nurl = ")
    scan = CodexAdapter(home, read_version=no_version).scan()
    assert [(p.path, p.unknown_reason) for p in scan.problems] == [
        (str(config), UnknownReason.PARSE_ERROR)
    ]
    assert ("codex", "skill", "docker-expert", "user", "on", None) in rows(scan.items, home)
    assert not [i for i in scan.items if str(i.kind) == "mcp_server"]


def test_codex_home_can_point_elsewhere(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    moved = tmp_path / "codex-home"
    (home / ".codex").rename(moved)
    scan = CodexAdapter(home, read_version=no_version, codex_home=moved).scan()
    assert ("codex", "mcp_server", "neon", "user", "on", None) in rows(scan.items, home)


def test_remote_plugins_say_their_state_is_in_the_account(tmp_path, no_version):
    # Spike S4: on/off of a remote plugin is stored in the ChatGPT account, not config.toml.
    home = make_home(tmp_path, FIXTURE)
    scan = CodexAdapter(home, read_version=no_version).scan()
    gmail = next(i for i in scan.items if i.name == "gmail@openai-curated-remote")
    assert gmail.source.unknown_reason is UnknownReason.STORED_IN_ACCOUNT
