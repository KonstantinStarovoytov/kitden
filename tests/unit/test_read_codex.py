import shutil
from pathlib import Path

from kitden.clients.codex import CodexAdapter
from kitden.model import UnknownReason
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


# Feature 003, FR-014: MCP servers inside an installed plugin (research R8).
PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins/kitden"


def _install_kitden_plugin(home: Path, enabled: str = "true") -> None:
    shutil.copytree(PLUGIN_DIR, home / ".codex/plugins/cache/kitden/kitden/0.1.0")
    config = home / ".codex/config.toml"
    config.write_text(config.read_text() + f'\n[plugins."kitden@kitden"]\nenabled = {enabled}\n')


def test_mcp_servers_inside_an_installed_plugin_are_read(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    _install_kitden_plugin(home)
    scan = CodexAdapter(home, read_version=no_version).scan()
    assert ("codex", "mcp_server", "kitden", "plugin", "on", None) in rows(scan.items, home)
    item = next(i for i in scan.items if i.name == "kitden" and str(i.kind) == "mcp_server")
    assert str(item.source.kind) == "plugin"
    assert item.source.path.endswith("kitden/0.1.0/mcp.json")


def test_a_plugin_turned_off_turns_its_servers_off(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    _install_kitden_plugin(home, enabled="false")
    scan = CodexAdapter(home, read_version=no_version).scan()
    assert ("codex", "mcp_server", "kitden", "plugin", "off", None) in rows(scan.items, home)
