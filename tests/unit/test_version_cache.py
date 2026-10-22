"""The disk cache of client versions: keyed by the binary's path and modification time."""

import os
import stat

import pytest

from kitden.clients import version_cache
from kitden.clients.version_cache import (
    VERSIONS_FILE,
    cached_version,
    load_versions,
    refresh_versions,
    stale_clients,
)
from kitden.gateways import data_dir
from tests.conftest import fake_client_command


@pytest.fixture
def claude(tmp_path, monkeypatch):
    binary = fake_client_command(tmp_path, "claude", "echo '2.1.300 (Claude Code)'")
    commands = {"claude_code": [str(binary), "--version"]}
    monkeypatch.setattr(version_cache, "version_command", commands.get)
    return binary, commands


def test_a_cached_version_is_used_when_the_binary_is_unchanged(tmp_path, claude):
    assert refresh_versions(tmp_path, ["claude_code"]) == {"claude_code": "2.1.300"}
    assert cached_version(tmp_path, "claude_code") == "2.1.300"
    assert stale_clients(tmp_path, ["claude_code", "codex"]) == []  # codex has no command


def test_a_cache_entry_for_another_path_or_mtime_is_stale(tmp_path, claude):
    binary, commands = claude
    refresh_versions(tmp_path, ["claude_code"])

    later = binary.stat().st_mtime_ns + 5_000_000_000
    os.utime(binary, ns=(later, later))
    assert cached_version(tmp_path, "claude_code") is None
    assert stale_clients(tmp_path, ["claude_code"]) == ["claude_code"]

    refresh_versions(tmp_path, ["claude_code"])
    assert cached_version(tmp_path, "claude_code") == "2.1.300"
    moved = fake_client_command(tmp_path / "other", "claude", "echo 2.1.300")
    commands["claude_code"] = [str(moved), "--version"]
    assert cached_version(tmp_path, "claude_code") is None
    assert stale_clients(tmp_path, ["claude_code"]) == ["claude_code"]


def test_a_missing_client_has_no_entry_and_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(version_cache, "version_command", lambda client: None)
    assert refresh_versions(tmp_path, ["cursor"]) == {"cursor": None}
    assert load_versions(tmp_path) == {}
    assert stale_clients(tmp_path, ["cursor"]) == []


def test_a_failed_version_command_is_not_cached(tmp_path, monkeypatch):
    broken = fake_client_command(tmp_path, "codex", "echo 'not found' >&2; exit 1")
    monkeypatch.setattr(version_cache, "version_command", lambda c: [str(broken), "--version"])
    assert refresh_versions(tmp_path, ["codex"]) == {"codex": None}
    assert "codex" not in load_versions(tmp_path)
    assert stale_clients(tmp_path, ["codex"]) == ["codex"]


def test_a_version_command_that_times_out_is_not_cached(tmp_path, monkeypatch):
    slow = fake_client_command(tmp_path, "cursor", "exec sleep 5")
    monkeypatch.setattr(version_cache, "version_command", lambda c: [str(slow), "--version"])
    monkeypatch.setattr(version_cache, "VERSION_TIMEOUT_SECONDS", 0.2)
    assert refresh_versions(tmp_path, ["cursor"]) == {"cursor": None}
    assert load_versions(tmp_path) == {}


def test_a_broken_cache_reads_as_empty_and_is_private(tmp_path, claude):
    data_dir(tmp_path).mkdir(parents=True)
    (data_dir(tmp_path) / VERSIONS_FILE).write_text("{")
    assert load_versions(tmp_path) == {}
    assert cached_version(tmp_path, "codex") is None

    refresh_versions(tmp_path, ["claude_code"])
    assert stat.S_IMODE((data_dir(tmp_path) / VERSIONS_FILE).stat().st_mode) == 0o600
    assert stat.S_IMODE(data_dir(tmp_path).stat().st_mode) == 0o700
    assert cached_version(tmp_path, "claude_code") == "2.1.300"


def test_a_refresh_keeps_the_other_clients_entries(tmp_path, monkeypatch):
    claude = fake_client_command(tmp_path, "claude", "echo 2.1.300")
    codex = fake_client_command(tmp_path, "codex", "echo codex-cli 0.159.2")
    commands = {"claude_code": [str(claude), "--version"], "codex": [str(codex), "--version"]}
    monkeypatch.setattr(version_cache, "version_command", commands.get)
    refresh_versions(tmp_path, ["claude_code", "codex"])
    refresh_versions(tmp_path, ["codex"])
    assert cached_version(tmp_path, "claude_code") == "2.1.300"
    assert cached_version(tmp_path, "codex") == "0.159.2"


def test_a_retargeted_link_is_never_served_the_old_version(tmp_path, monkeypatch):
    old = fake_client_command(tmp_path / "old", "claude", "echo '2.1.300 (Claude Code)'")
    new = fake_client_command(tmp_path / "new", "claude", "echo '2.1.301 (Claude Code)'")
    same = old.stat().st_mtime_ns
    os.utime(new, ns=(same, same))  # the same modification time: only the target differs
    link = tmp_path / "claude"
    link.symlink_to(old)
    monkeypatch.setattr(version_cache, "version_command", lambda c: [str(link), "--version"])
    refresh_versions(tmp_path, ["claude_code"])
    assert cached_version(tmp_path, "claude_code") == "2.1.300"

    link.unlink()
    link.symlink_to(new)
    assert cached_version(tmp_path, "claude_code") is None
    assert stale_clients(tmp_path, ["claude_code"]) == ["claude_code"]
