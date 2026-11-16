"""The start measurement's building blocks: the sandbox it builds and its slow fake Codex.
The times themselves are checked by running the script; here only how it reads its budgets."""

import importlib.util
import json
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kitden.clients.codex import CodexAdapter
from kitden.demo import demo_build
from kitden.model import Enabled, ItemKind
from kitden.web.app import create_app

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("measure_start", ROOT / "scripts/measure-start.py")
measure_start = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure_start)
ORIGIN = "http://127.0.0.1:47800"


@contextmanager
def demo_page_on(home):
    """The demo page on a sample home built already, as Part 1's `demo_page` starts it."""
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        yield page


def test_the_sandbox_is_the_large_sample_with_fake_clients(tmp_path):
    home = measure_start.build_sandbox(tmp_path, slow=0)
    assert home == tmp_path / "home"
    servers = json.loads((home / ".claude.json").read_text())["mcpServers"]
    assert len([n for n in servers if n.startswith("bench-server-")]) == 50
    assert {p.name for p in (tmp_path / "bin").iterdir()} == {"claude", "codex", "cursor"}
    # A Codex plugin with no config.toml entry: the scan asks Codex's plugin list, the slow step.
    asked = []
    codex = CodexAdapter(home, lambda: "0.163.0", list_plugins=lambda: asked.append(1) or {})
    unknown = [
        i.name
        for i in codex.scan().items
        if i.kind is ItemKind.PLUGIN and i.enabled is Enabled.UNKNOWN
    ]
    assert asked == [1] and unknown == ["calendar@openai-curated-remote"]


def test_the_fake_codex_sleeps_then_answers(tmp_path):
    home = measure_start.build_sandbox(tmp_path, slow=0.5)
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


def test_the_probe_sample_has_twenty_servers(tmp_path):
    home = measure_start.build_probe(tmp_path)
    with demo_page_on(home) as page:
        view = page.get("/api/gateway-view").json()
    held = len(view["gateways"][0]["servers"])
    outside = sum(len(rows) for rows in view["groups"].values())
    assert held + outside == measure_start.PROBE_SERVERS
    # The added servers reach a client directly, in Claude Code and in Codex.
    probes = [r for rows in view["groups"].values() for r in rows if r["name"].startswith("probe-")]
    assert {c for row in probes for c in row["clients"]} == {"claude_code", "codex"}


def test_the_budgets_are_the_same_everywhere_unless_the_workflow_scales_them():
    plain = {"first usable": 2.0, "complete": 5.0, "demo (medium)": 2.0}
    assert measure_start.budgets({}) == plain
    assert measure_start.budgets({"KITDEN_START_BUDGET_SCALE": "1"}) == plain
    # The Intel Mac of the nightly gets twice the budgets.
    assert measure_start.budgets({"KITDEN_START_BUDGET_SCALE": "2"}) == {
        "first usable": 4.0,
        "complete": 10.0,
        "demo (medium)": 4.0,
    }


@pytest.mark.parametrize("value", ["", "0", "-2", "two", "nan", "inf"])
def test_a_scale_that_is_not_a_positive_number_stops_the_script(value):
    with pytest.raises(SystemExit) as stopped:
        measure_start.budgets({"KITDEN_START_BUDGET_SCALE": value})
    assert str(stopped.value) == (
        f"KITDEN_START_BUDGET_SCALE must be a positive number, not {value!r}."
    )


def test_a_time_over_its_budget_is_missed_and_twice_the_budget_still_has_a_limit():
    times = {"first usable": 2.5, "complete": 1.0, "demo (medium)": 0.5}
    assert measure_start.missed(times, measure_start.budgets({})) == ["first usable"]
    doubled = measure_start.budgets({"KITDEN_START_BUDGET_SCALE": "2"})
    assert measure_start.missed(times, doubled) == []
    assert measure_start.missed({**times, "complete": 10.5}, doubled) == ["complete"]


def test_the_script_says_which_budgets_it_uses():
    assert measure_start.budget_line(measure_start.budgets({})) == (
        "Budgets: first usable 2 s, complete 5 s, demo (medium) 2 s."
    )
    doubled = measure_start.budgets({"KITDEN_START_BUDGET_SCALE": "2"})
    assert measure_start.budget_line(doubled) == (
        "Budgets: first usable 4 s, complete 10 s, demo (medium) 4 s."
    )
