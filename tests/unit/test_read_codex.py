import shutil
from pathlib import Path

import pytest

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


def test_an_untrusted_project_has_no_instruction_files_listed(tmp_path, no_version):
    # checked 2026-11-25: Codex skips project files only when trust_level is "untrusted"; a
    # project entry with no trust_level is read (codex PR 39837, is_untrusted()).
    home = make_home(tmp_path, FIXTURE)
    config = home / ".codex/config.toml"
    plain = home / "work/plain"
    config.write_text(config.read_text() + f'\n[projects."{plain}"]\nnote = "no trust level"\n')
    for folder in (home / "work/api", home / "work/untrusted", plain):
        for name in ("AGENTS.md", "AGENTS.override.md"):
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text("x")
    (home / ".codex/AGENTS.override.md").write_text("x")
    scan = CodexAdapter(home, read_version=no_version).scan()
    found = _instructions(scan)
    for folder, listed in (("api", True), ("untrusted", False), ("plain", True)):
        paths = {i[4] for i in found if i[3] == str(home / "work" / folder)}
        names = {str(home / "work" / folder / n) for n in ("AGENTS.md", "AGENTS.override.md")}
        assert paths == (names if listed else set()), folder
    user = {i[4] for i in found if i[0] is Scope.USER}
    assert user == {str(home / ".codex" / n) for n in ("AGENTS.md", "AGENTS.override.md")}


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


def test_a_running_page_asks_codex_again_after_an_hour(tmp_path, monkeypatch):
    # `kitden serve` keeps the answer in memory; it must not outlive the hour either.
    import time
    from types import SimpleNamespace

    import kitden.clients.codex as codex

    runs = _ask_codex(monkeypatch, LISTING)
    home = make_home(tmp_path, FIXTURE)
    now = time.time()
    monkeypatch.setattr(codex, "time", SimpleNamespace(time=lambda: now))
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    for minutes in (30, 59):  # same process, no new run
        now = time.time() + minutes * 60
        _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert len(runs) == 1
    now = time.time() + 61 * 60
    _gmail(CodexAdapter(home, read_version=lambda: "0.163.0"))
    assert len(runs) == 2


# Skills in sub-folders of a skills folder, as Codex's own walk finds them (docs/clients.md).


def write_skill(folder: Path, name: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SKILL.md"
    path.write_text(f"---\nname: {name or folder.name}\ndescription: Does it.\n---\n")
    return path


def skills_of(home, no_version, **more):
    """Codex's skills: name -> item. A name listed twice fails the test that asks."""
    scan = CodexAdapter(home, read_version=no_version, **more).scan()
    items = [i for i in scan.items if i.kind is ItemKind.SKILL]
    assert len({i.name for i in items}) == len(items), sorted(i.name for i in items)
    return {i.name: i for i in items}


@pytest.fixture
def bare_home(tmp_path):
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    return home


def test_skills_in_sub_folders_are_listed_in_every_folder_codex_reads(bare_home, no_version):
    home = bare_home
    for name in ("api", "stranger"):
        write_skill(home / "work" / name / ".agents/skills/team" / f"{name}-nested")
    (home / ".codex/config.toml").write_text(
        f'[projects."{home}/work/api"]\ntrust_level = "trusted"\n'
        f'[projects."{home}/work/stranger"]\ntrust_level = "untrusted"\n'
    )
    write_skill(home / ".agents/skills/ops/deploy")
    write_skill(home / ".codex/skills/team/triage")
    found = skills_of(home, no_version)
    assert set(found) == {"deploy", "triage", "api-nested"}  # no row for the folders between
    assert found["deploy"].source.path == str(home / ".agents/skills/ops/deploy/SKILL.md")
    assert (found["deploy"].scope, found["deploy"].project) == (Scope.USER, None)
    assert (found["api-nested"].scope, found["api-nested"].project) == (
        Scope.PROJECT,
        str(home / "work/api"),
    )
    for item in found.values():
        assert CodexAdapter(home).item_actions(item) == ("skill.remove",)


def test_a_skill_inside_another_skills_folder_is_listed(bare_home, no_version):
    write_skill(bare_home / ".codex/skills/qdrant")
    write_skill(bare_home / ".codex/skills/qdrant/search-strategies/hybrid-search")
    assert set(skills_of(bare_home, no_version)) == {"qdrant", "hybrid-search"}


def test_codex_looks_six_folders_deep_and_skips_hidden_ones(bare_home, no_version):
    root = bare_home / ".agents/skills"
    write_skill(root / "1/2/3/4/5/six-deep")
    write_skill(root / "1/2/3/4/5/six/seven-deep")
    write_skill(root / ".system/hidden")
    write_skill(root / "team/.trash/hidden-too")
    assert set(skills_of(bare_home, no_version)) == {"six-deep"}


def test_a_linked_folder_is_searched_and_its_skills_keep_their_link(bare_home, no_version):
    home = bare_home
    root = home / ".agents/skills"
    real = write_skill(home / "elsewhere/pack/inside")
    single = write_skill(home / "elsewhere/single")
    write_skill(root / "team/own")
    (root / "pack").symlink_to(home / "elsewhere/pack")
    (root / "team/single").symlink_to(home / "elsewhere/single")
    (root / "team/loop").symlink_to(root)
    (root / "gone").symlink_to(home / "elsewhere/gone")
    found = skills_of(home, no_version)
    assert set(found) == {"inside", "single", "own"}
    assert found["inside"].source.path == str(real)
    assert found["inside"].source.link_path == str(root / "pack/inside")
    assert found["single"].source.path == str(single)
    assert found["single"].source.link_path == str(root / "team/single")
    assert found["own"].source.link_path is None
    adapter = CodexAdapter(home)
    assert [adapter.item_actions(found[n]) for n in ("inside", "single")] == [(), ()]


def test_a_skill_md_that_is_a_link_is_not_listed(bare_home, no_version):
    real = write_skill(bare_home / "elsewhere/real")
    folder = bare_home / ".agents/skills/linked"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").symlink_to(real)
    assert skills_of(bare_home, no_version) == {}


def test_a_skill_that_codex_finds_twice_is_one_row_the_real_folder(bare_home, no_version):
    home = bare_home
    shared = write_skill(home / ".codex/skills/team/shared")
    (home / ".agents/skills").mkdir(parents=True)
    (home / ".agents/skills/linked-team").symlink_to(home / ".codex/skills/team")
    beside = write_skill(home / ".agents/skills/z-real")
    (home / ".agents/skills/a-link").symlink_to(home / ".agents/skills/z-real")
    found = skills_of(home, no_version)
    assert {n: i.source.path for n, i in found.items()} == {
        "shared": str(shared),
        "z-real": str(beside),
    }
    assert [i.source.link_path for i in found.values()] == [None, None]


def test_a_nested_skill_can_be_off(bare_home, no_version):
    home = bare_home
    outer = write_skill(home / ".codex/skills/outer")
    inner = write_skill(home / ".codex/skills/outer/parts/inner")
    (home / ".codex/config.toml").write_text(
        f'[[skills.config]]\npath = "{inner}"\nenabled = false\n'
    )
    found = skills_of(home, no_version)
    # checked 2026-11-25 (codex-rs/ext/skills/src/host_outcome.rs): by the skill's own path, so
    # the outer skill stays on, and turning it off would leave the inner one.
    assert {n: str(i.enabled) for n, i in found.items()} == {"outer": "on", "inner": "off"}
    step = CodexAdapter(home).skill_rule_step(found["outer"])
    assert step.edit is not None and step.edit.after == {"path": str(outer), "enabled": False}


def test_a_skills_folder_with_very_many_folders_stops_at_codexs_limit(
    bare_home, no_version, monkeypatch
):
    root = bare_home / ".agents/skills"
    for n in range(6):
        write_skill(root / f"s{n}")
    monkeypatch.setattr("kitden.clients.codex.MAX_SKILL_FOLDERS", 4)  # the root counts as one
    assert set(skills_of(bare_home, no_version)) == {"s0", "s1", "s2"}
    monkeypatch.setattr("kitden.clients.codex.MAX_SKILL_FOLDERS", 2000)
    monkeypatch.setattr("kitden.clients.codex.MAX_SKILL_ENTRIES", 8)  # 6 folders, then 2 files
    assert set(skills_of(bare_home, no_version)) == {"s0", "s1"}


def test_a_folder_that_cannot_be_read_hides_only_itself(bare_home, no_version):
    root = bare_home / ".agents/skills"
    write_skill(root / "team/fine")
    locked = root / "locked"
    write_skill(locked / "inside")
    locked.chmod(0)
    try:
        assert set(skills_of(bare_home, no_version)) == {"fine"}
    finally:
        locked.chmod(0o755)
