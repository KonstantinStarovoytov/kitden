"""The start measurement's building blocks: the sandbox it builds and its slow fake Codex.
The budgets themselves are checked by running the script, not here."""

import importlib.util
import json
import subprocess
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("measure_start", ROOT / "scripts/measure-start.py")
measure_start = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure_start)


def test_the_sandbox_builder_makes_the_counts_asked(tmp_path):
    home = measure_start.build_sandbox(tmp_path, servers=40, plugins=10, skills=20, slow=0)

    claude = json.loads((home / ".claude.json").read_text())["mcpServers"]
    codex = tomllib.loads((home / ".codex/config.toml").read_text())["mcp_servers"]
    cursor = json.loads((home / ".cursor/mcp.json").read_text())["mcpServers"]
    added = [n for found in (claude, codex, cursor) for n in found if n.startswith("bench-")]
    assert len(added) == 40
    assert all(any(n.startswith("bench-") for n in found) for found in (claude, codex, cursor))

    cache = home / ".claude/plugins/cache/bench-market"
    assert len([p for p in cache.glob("*/1.0.0") if p.is_dir()]) == 10
    installed = json.loads((home / ".claude/plugins/installed_plugins.json").read_text())
    assert len([k for k in installed["plugins"] if k.endswith("@bench-market")]) == 10

    folders = [".claude/skills", ".agents/skills", ".cursor/skills"]
    skills = [p for f in folders for p in (home / f).glob("bench-skill-*/SKILL.md")]
    assert len(skills) == 20
    assert all(list((home / f).glob("bench-skill-*")) for f in folders)


def test_the_fake_codex_sleeps_then_answers(tmp_path):
    home = measure_start.build_sandbox(tmp_path, servers=3, plugins=1, skills=3, slow=0.5)
    codex = home.parent / "bin/codex"

    version = subprocess.run([codex, "--version"], capture_output=True, text=True, check=True)
    assert version.stdout.strip() == "codex-cli 0.163.0"
    started = time.monotonic()
    listing = subprocess.run(
        [codex, "plugin", "list", "--json"], capture_output=True, text=True, check=True
    )
    assert time.monotonic() - started >= 0.5
    assert json.loads(listing.stdout) == {"installed": []}
    assert {p.name for p in (home.parent / "bin").iterdir()} == {"claude", "codex", "cursor"}
