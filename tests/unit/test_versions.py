import pytest

from kitden.clients.versions import (
    highest_version,
    is_supported,
    parse_version,
    version_command,
)


@pytest.mark.parametrize(
    ("client", "output", "want"),
    [
        ("claude_code", "2.1.283 (Claude Code)\n", "2.1.283"),
        ("codex", "codex-cli 0.159.2\n", "0.159.2"),
        ("cursor", "3.21.16\n1a2b3c4d\narm64\n", "3.21.16"),
        ("codex", "command not found", None),
        ("cursor", "", None),
    ],
)
def test_parse_version_reads_each_client_format(client, output, want):
    assert parse_version(client, output) == want


@pytest.mark.parametrize(
    ("client", "version", "want"),
    [
        ("claude_code", "2.1.283", True),
        ("claude_code", "2.1.282", False),
        ("claude_code", "2.1.1000", True),  # numeric, not text, comparison
        ("codex", "0.159.2", True),
        ("codex", "0.158.9", False),
        ("cursor", "3.21.16", True),
        ("cursor", "3.9.0", False),
        ("cursor", None, False),
    ],
)
def test_is_supported_compares_with_minimum(client, version, want):
    assert is_supported(client, version) is want


def test_highest_version_ignores_non_version_names():
    assert highest_version(["2.1.295", "2.1.299", "latest", ".DS_Store", "2.1.30"]) == "2.1.299"
    assert highest_version(["notes"]) is None


def test_version_command_uses_path_when_available():
    def which(name):
        return "/usr/local/bin/claude" if name == "claude" else None

    assert version_command("claude_code", which=which, exists=lambda p: False) == [
        "/usr/local/bin/claude",
        "--version",
    ]


def test_version_command_falls_back_to_bundled_codex():
    bundled = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
    assert version_command("codex", which=lambda n: None, exists=lambda p: p == bundled) == [
        bundled,
        "--version",
    ]


def test_version_command_is_none_when_client_missing():
    assert version_command("cursor", which=lambda n: None, exists=lambda p: False) is None


def test_version_commands_are_cached_for_a_while(monkeypatch):
    import subprocess

    import kitden.clients.base as base
    import kitden.clients.version_cache as version_cache

    runs = []

    def fake_run(command, **kwargs):
        runs.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="codex-cli 0.159.2\n")

    now = [1000.0]
    monkeypatch.setattr(version_cache, "version_command", lambda c: ["/bin/codex", "--version"])
    monkeypatch.setattr(version_cache.subprocess, "run", fake_run)
    monkeypatch.setattr(base.time, "monotonic", lambda: now[0])
    base._VERSION_CACHE.clear()

    assert base.read_command_version("codex") == "0.159.2"
    assert base.read_command_version("codex") == "0.159.2"
    assert len(runs) == 1
    now[0] += base.VERSION_CACHE_SECONDS + 1
    base.read_command_version("codex")
    assert len(runs) == 2
