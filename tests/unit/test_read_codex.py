import shutil
from pathlib import Path

from kitden.clients.codex import CodexAdapter
from kitden.model import ItemKind, Scope, UnknownReason
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
    ("codex", "instructions", "AGENTS.md", "user", "on", None),
    ("codex", "instructions", "AGENTS.md", "project", "on", "work/api"),
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
    # The plugin as it was up to 0.7.1, when it still brought the server.
    cache = home / ".codex/plugins/cache/kitden/kitden/0.1.0"
    shutil.copytree(PLUGIN_DIR, cache)
    entry = '{"mcpServers": {"kitden": {"command": "kitden", "args": ["mcp", "--read-only"]}}}'
    (cache / "mcp.json").write_text(entry)
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


# A quick scan never waits for `codex plugin list` (15 s on a real Mac): it asks in the
# background, and says when the answer is in.
def test_a_quick_scan_asks_codex_in_the_background_and_says_when_the_answer_is_in(
    tmp_path, monkeypatch
):
    import json
    import subprocess
    import threading

    import kitden.clients.codex as codex

    monkeypatch.setattr(codex, "_LIST_CACHE", {})
    monkeypatch.setattr(codex, "version_command", lambda client: ["codex", "--version"])
    release, runs = threading.Event(), []

    def slow_list(command, **kwargs):
        runs.append(command)
        release.wait(5)
        listing = {"installed": [{"pluginId": "gmail@openai-curated-remote", "enabled": False}]}
        return subprocess.CompletedProcess(command, 0, json.dumps(listing), "")

    monkeypatch.setattr(codex.subprocess, "run", slow_list)
    home = make_home(tmp_path, FIXTURE)
    answered = threading.Event()

    def quick():
        return CodexAdapter(
            home, read_version=lambda: "0.163.0", quick=True, on_slow_answer=answered.set
        )

    first = quick()
    first.scan()  # does not wait for the list
    assert first.skipped is True
    second = quick()
    second.scan()  # the list is still on its way: no second command
    assert second.skipped is True
    release.set()
    assert answered.wait(5)
    assert len(runs) == 1 and runs[0][1:] == ["plugin", "list", "--json"]
    third = quick()
    gmail = next(i for i in third.scan().items if i.name == "gmail@openai-curated-remote")
    assert third.skipped is False and str(gmail.enabled) == "off"


def test_a_git_marketplace_is_read_from_the_copy_codex_keeps(tmp_path, no_version):
    # Codex clones a git marketplace into .tmp/marketplaces/<name> (seen with Codex 0.163.0,
    # 2026-10-20). Without that root the Library offered to add a marketplace Codex has.
    home = make_home(tmp_path, FIXTURE)
    config = home / ".codex/config.toml"
    config.write_text(
        config.read_text()
        + '\n[marketplaces.claude-plugins-official]\nsource_type = "git"\n'
        + 'source = "https://github.com/anthropics/claude-plugins-official.git"\n'
    )
    clone = home / ".codex/.tmp/marketplaces/claude-plugins-official"
    (clone / ".claude-plugin").mkdir(parents=True)
    (clone / ".claude-plugin/marketplace.json").write_text('{"name": "claude-plugins-official"}')
    roots = CodexAdapter(home, read_version=no_version).marketplace_roots()
    assert roots["claude-plugins-official"] == clone


def _instructions(scan):
    return {
        (i.scope, i.name, dict(i.summary)["category"], i.project, i.source.path)
        for i in scan.items
        if i.kind is ItemKind.INSTRUCTIONS
    }


def test_scan_reads_agents_md_for_the_user_and_each_project(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    api = home / "work/api"
    (api / "AGENTS.override.md").write_text("x")
    (home / ".codex/AGENTS.override.md").write_text("x")
    scan = CodexAdapter(home, read_version=no_version).scan()
    assert _instructions(scan) == {
        (Scope.USER, "AGENTS.md", "instructions", None, str(home / ".codex/AGENTS.md")),
        (
            Scope.USER,
            "AGENTS.override.md",
            "instructions",
            None,
            str(home / ".codex/AGENTS.override.md"),
        ),
        (Scope.PROJECT, "AGENTS.md", "instructions", str(api), str(api / "AGENTS.md")),
        (
            Scope.PROJECT,
            "AGENTS.override.md",
            "instructions",
            str(api),
            str(api / "AGENTS.override.md"),
        ),
    }


def test_the_user_agents_md_follows_codex_home(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    moved = tmp_path / "codex-home"
    (home / ".codex").rename(moved)
    scan = CodexAdapter(home, read_version=no_version, codex_home=moved).scan()
    paths = {i[4] for i in _instructions(scan) if i[0] is Scope.USER}
    assert paths == {str(moved / "AGENTS.md")}


def test_the_home_folder_as_a_codex_project_keeps_its_agents_md(tmp_path, no_version):
    home = make_home(tmp_path, FIXTURE)
    (home / "AGENTS.md").write_text("x")
    (home / "AGENTS.override.md").write_text("x")
    config = home / ".codex/config.toml"
    config.write_text(config.read_text() + f'\n[projects."{home}"]\ntrust_level = "trusted"\n')
    scan = CodexAdapter(home, read_version=no_version).scan()
    in_home = {i[4] for i in _instructions(scan) if i[3] == str(home)}
    assert in_home == {str(home / "AGENTS.md"), str(home / "AGENTS.override.md")}


# `kitden scan` and `kitden show` are new processes each time. The plugin list is kept on disk,
# so a repeat run does not wait for Codex again.
LISTING = {"installed": [{"pluginId": "gmail@openai-curated-remote", "enabled": False}]}


def _ask_codex(monkeypatch, outcome):
    """Fake `codex plugin list --json`. `outcome` is the stdout text, or an exception to raise.
    Returns the list of commands that were run."""
    import json
    import subprocess

    import kitden.clients.codex as codex

    runs: list[list[str]] = []

    def run(command, **kwargs):
        runs.append(command)
        if isinstance(outcome, Exception):
            raise outcome
        text, code = outcome if isinstance(outcome, tuple) else (json.dumps(outcome), 0)
        return subprocess.CompletedProcess(command, code, text, "")

    monkeypatch.setattr(codex, "version_command", lambda client: ["codex", "--version"])
    monkeypatch.setattr(codex.subprocess, "run", run)
    return runs


def _new_run(monkeypatch):
    """What a second `kitden scan` starts with: nothing in memory."""
    import kitden.clients.codex as codex

    monkeypatch.setattr(codex, "_LIST_CACHE", {})


def _gmail(adapter):
    return next(i for i in adapter.scan().items if i.name == "gmail@openai-curated-remote")


def test_a_second_run_does_not_ask_codex_again(tmp_path, monkeypatch, capsys):
    runs = _ask_codex(monkeypatch, LISTING)
    home = make_home(tmp_path, FIXTURE)
    assert str(_gmail(CodexAdapter(home, read_version=lambda: "0.163.0")).enabled) == "off"
    assert capsys.readouterr().err == "Asking Codex which plugins are on (up to 15 s)…\n"
    _new_run(monkeypatch)
    second = _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert str(second.enabled) == "off"
    assert len(runs) == 1
    assert capsys.readouterr() == ("", "")  # nothing to wait for, nothing to say


def test_a_changed_config_asks_codex_again(tmp_path, monkeypatch):
    runs = _ask_codex(monkeypatch, LISTING)
    home = make_home(tmp_path, FIXTURE)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    config = home / ".codex/config.toml"
    config.write_text(config.read_text() + "\n# the app wrote this\n")
    _new_run(monkeypatch)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert len(runs) == 2


def test_a_timeout_is_not_kept_as_an_answer(tmp_path, monkeypatch, capsys):
    import subprocess

    from kitden.gateways import data_dir

    runs = _ask_codex(monkeypatch, subprocess.TimeoutExpired(["codex"], 15))
    home = make_home(tmp_path, FIXTURE)
    assert str(_gmail(CodexAdapter(home, read_version=lambda: "0.163.0")).enabled) == "unknown"
    assert "Asking Codex" in capsys.readouterr().err
    assert not list(data_dir(home).glob("codex-plugins*"))
    _new_run(monkeypatch)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert len(runs) == 2  # the next run asks again


def test_a_failed_call_is_not_kept_as_an_answer(tmp_path, monkeypatch):
    from kitden.gateways import data_dir

    runs = _ask_codex(monkeypatch, ("not signed in", 1))
    home = make_home(tmp_path, FIXTURE)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert not list(data_dir(home).glob("codex-plugins*"))
    _new_run(monkeypatch)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert len(runs) == 2


def test_only_the_plugin_ids_and_their_state_are_kept_on_disk(tmp_path, monkeypatch):
    import json

    from kitden.gateways import data_dir

    listing = {
        "installed": [{**LISTING["installed"][0], "token": "SENTINEL_SECRET", "marketplace": "m"}],
        "available": [{"pluginId": "other@x", "authUrl": "SENTINEL_SECRET"}],
        "account": {"email": "SENTINEL_SECRET"},
    }
    _ask_codex(monkeypatch, listing)
    home = make_home(tmp_path, FIXTURE)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    (stored,) = data_dir(home).glob("codex-plugins*")
    assert "SENTINEL_SECRET" not in stored.read_text()
    assert json.loads(stored.read_text())["installed"] == LISTING["installed"]
    assert stored.stat().st_mode & 0o077 == 0  # only its owner can read it


def test_a_quick_scan_reads_the_stored_answer(tmp_path, monkeypatch):
    runs = _ask_codex(monkeypatch, LISTING)
    home = make_home(tmp_path, FIXTURE)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    _new_run(monkeypatch)
    quick = CodexAdapter(home, read_version=lambda: "0.163.0", quick=True)
    assert str(_gmail(quick).enabled) == "off"
    assert quick.skipped is False and len(runs) == 1


def test_a_broken_stored_file_is_asked_for_again(tmp_path, monkeypatch):
    from kitden.gateways import data_dir

    runs = _ask_codex(monkeypatch, LISTING)
    home = make_home(tmp_path, FIXTURE)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    (stored,) = data_dir(home).glob("codex-plugins*")
    stored.write_text("{ not json")
    _new_run(monkeypatch)
    assert str(_gmail(CodexAdapter(home, read_version=lambda: "0.163.0")).enabled) == "off"
    assert len(runs) == 2


def _age_the_stored_answer(home, seconds):
    """Make the stored answer look `seconds` old."""
    import json
    import time

    from kitden.gateways import data_dir

    stored = data_dir(home) / "codex-plugins.json"
    data = json.loads(stored.read_text())
    data["asked_at"] = time.time() - seconds
    stored.write_text(json.dumps(data))


def test_an_answer_just_inside_its_age_is_used(tmp_path, monkeypatch):
    import kitden.clients.codex as codex

    runs = _ask_codex(monkeypatch, LISTING)
    home = make_home(tmp_path, FIXTURE)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    _age_the_stored_answer(home, codex.PLUGIN_LIST_MAX_AGE_SECONDS - 60)
    _new_run(monkeypatch)
    assert str(_gmail(CodexAdapter(home, read_version=lambda: "0.163.0")).enabled) == "off"
    assert len(runs) == 1


def test_an_answer_past_its_age_is_asked_for_again(tmp_path, monkeypatch):
    # A remote plugin's on/off lives in the ChatGPT account, so a change made elsewhere does not
    # touch this config.toml.
    import kitden.clients.codex as codex

    runs = _ask_codex(monkeypatch, LISTING)
    home = make_home(tmp_path, FIXTURE)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    _age_the_stored_answer(home, codex.PLUGIN_LIST_MAX_AGE_SECONDS + 60)
    _new_run(monkeypatch)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert len(runs) == 2


def test_an_answer_from_the_future_or_without_a_time_is_asked_for_again(tmp_path, monkeypatch):
    runs = _ask_codex(monkeypatch, LISTING)
    home = make_home(tmp_path, FIXTURE)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    _age_the_stored_answer(home, -3600)  # the clock was set back
    _new_run(monkeypatch)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert len(runs) == 2
    from kitden.gateways import data_dir

    stored = data_dir(home) / "codex-plugins.json"
    stored.write_text(stored.read_text().replace("asked_at", "other"))
    _new_run(monkeypatch)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert len(runs) == 3


def test_a_stored_file_with_a_hard_link_does_not_stop_the_scan(tmp_path, monkeypatch):
    # Kitden does not write over a file with a hard link; it asks Codex again next time.
    import os

    from kitden.gateways import data_dir

    runs = _ask_codex(monkeypatch, LISTING)
    home = make_home(tmp_path, FIXTURE)
    folder = data_dir(home)
    folder.mkdir(parents=True)
    (tmp_path / "elsewhere.json").write_text("{}")
    os.link(tmp_path / "elsewhere.json", folder / "codex-plugins.json")
    assert str(_gmail(CodexAdapter(home, read_version=lambda: "0.163.0")).enabled) == "off"
    assert (tmp_path / "elsewhere.json").read_text() == "{}"
    _new_run(monkeypatch)
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert len(runs) == 2
