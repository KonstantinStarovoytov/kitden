import asyncio
import hashlib
import time

import pytest

from kitden.watch import Watcher, is_relevant


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
    time.sleep(1)  # macOS can report a write made just before watching started
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
    time.sleep(1)
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
