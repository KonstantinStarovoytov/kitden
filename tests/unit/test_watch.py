import asyncio
import hashlib

import pytest

from kitden.watch import Watcher, is_relevant
from tests.conftest import aged


@pytest.mark.parametrize(
    ("path", "want"),
    [
        ("/h/.codex/config.toml", True),
        ("/h/.claude.json", True),
        ("/h/.claude/skills/brandkit/SKILL.md", True),
        ("/h/.cursor/mcp.json", True),
        ("/h/.codex/sessions/2026/10/17/rollout.jsonl", False),
        ("/h/.codex/logs_2.sqlite-wal", False),
        ("/h/.codex/shell_snapshots/snap.sh", False),
        ("/h/.claude/projects/-Users-x/abc.jsonl", False),
        ("/h/.claude/skills/brandkit/notes.txt", False),
        ("/h/.claude/CLAUDE.md", True),
        ("/h/CLAUDE.local.md", True),
        ("/h/.codex/AGENTS.md", True),
        ("/h/.codex/AGENTS.override.md", True),
        ("/h/p/.cursorrules", True),
        ("/h/.claude/commands/git/push.md", True),
        ("/h/.claude/agents/reviewer.md", True),
        ("/h/.cursor/rules/style.mdc", True),
        ("/h/.claude/rules/style.md", True),
        ("/h/.claude/plans/notes.md", False),
    ],
)
def test_only_setup_files_trigger_a_rescan(path, want):
    assert is_relevant(path) is want


def _run(coro):
    return asyncio.run(asyncio.wait_for(coro, timeout=10))


def test_a_change_triggers_one_debounced_callback(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("a = 1\n")
    aged(config)  # written before watching: never reported
    calls = []

    async def scenario():
        watcher = Watcher([tmp_path], on_change=lambda: calls.append(1), debounce_ms=100)
        task = asyncio.create_task(watcher.run())
        await asyncio.sleep(0.5)
        config.write_text("a = 2\n")
        config.write_text("a = 3\n")
        for _ in range(40):
            if calls:
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.4)
        watcher.stop()
        await task

    _run(scenario())
    assert calls == [1]


def test_the_tools_own_write_is_ignored(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("a = 1\n")
    aged(config)
    calls = []
    new = b"a = 2\n"

    async def scenario():
        watcher = Watcher([tmp_path], on_change=lambda: calls.append(1), debounce_ms=100)
        task = asyncio.create_task(watcher.run())
        await asyncio.sleep(0.5)
        watcher.expect(config, hashlib.sha256(new).hexdigest())
        config.write_bytes(new)
        await asyncio.sleep(1.5)
        watcher.stop()
        await task

    _run(scenario())
    assert calls == []


def test_a_folder_made_after_the_start_is_rescanned_and_then_watched(tmp_path, monkeypatch):
    # Claude Code makes its folder on the first run, maybe after Kitden started.
    monkeypatch.setattr("kitden.watch.LATE_SECONDS", 0.1, raising=False)
    folder = tmp_path / "claude-work"
    calls = []

    async def until(count):
        for _ in range(40):
            if len(calls) >= count:
                break
            await asyncio.sleep(0.1)

    async def scenario():
        watcher = Watcher([folder], on_change=lambda: calls.append(1), debounce_ms=100)
        task = asyncio.create_task(watcher.run())
        await asyncio.sleep(0.3)
        assert calls == []
        folder.mkdir()
        await until(1)
        assert calls == [1]
        (folder / "settings.json").write_text("{}")
        await until(2)
        assert calls == [1, 1]
        watcher.stop()
        await task

    _run(scenario())


def test_the_wait_for_a_folder_ends_when_the_page_stops(tmp_path):
    async def scenario():
        watcher = Watcher([tmp_path / "none"], on_change=lambda: None)
        task = asyncio.create_task(watcher.run())
        await asyncio.sleep(0.1)
        watcher.stop()
        await asyncio.wait_for(task, 1)

    _run(scenario())
