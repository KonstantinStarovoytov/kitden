"""The Library's add panel: the plugins and skills the marketplaces offer, read on a demo home."""

import json
from dataclasses import replace

import pytest
from starlette.testclient import TestClient

from kitden.demo import build_demo_home, demo_adapters, demo_build
from kitden.demo.sample import MARKET
from kitden.model import ClientStatus
from kitden.views.skills import library_offers
from kitden.web.app import create_app


@pytest.fixture
def home(tmp_path):
    return build_demo_home(tmp_path, "medium")


def _offers(home):
    inventory = demo_build(home)()
    adapters = {a.id: a for a in demo_adapters(home)}
    return library_offers(inventory, adapters)


def _row(rows, row_id):
    return next(r for r in rows if r["id"] == row_id)


def test_library_offers_lists_plugins_and_skills_by_marketplace_with_no_paths(home):
    rows = _offers(home)
    keys = [(r["marketplace"].lower(), r["name"].lower()) for r in rows]
    assert keys == sorted(keys)
    assert {r["kind"] for r in rows} == {"plugin", "skill"}
    # Only what a marketplace offers: a client's own skills are on the map already.
    assert all(r["marketplace"] for r in rows)
    fields = {
        "id",
        "kind",
        "name",
        "marketplace",
        "count",
        "unit",
        "routes",
        "installed",
        "refusal",
    }
    for row in rows:
        assert set(row) <= fields, row
        assert "/" not in json.dumps(row), row

    # A plugin no client has: every installer that knows its marketplace can take it. Kitden read
    # one MCP server inside it, so it holds one item.
    db = _row(rows, f"db-tools@{MARKET}")
    assert (db["kind"], db["name"], db["marketplace"]) == ("plugin", "db-tools", MARKET)
    assert (db["routes"], db["installed"], db["refusal"]) == (
        {"claude_code": "ready", "codex": "ready"},
        [],
        None,
    )
    assert (db["count"], db["unit"]) == (1, "item")
    # One that holds only skills counts skills.
    sp = _row(rows, f"superpowers@{MARKET}")
    assert (sp["count"], sp["unit"], sp["installed"]) == (2, "skill", ["claude_code", "cursor"])

    # A skill inside a plugin: the clients that load it already, and the ones that can take a copy.
    skill = _row(rows, f"planning@superpowers@{MARKET}")
    assert (skill["kind"], skill["name"], skill["marketplace"]) == ("skill", "planning", MARKET)
    assert skill["routes"] == {"codex": "ready"}
    assert sorted(skill["installed"]) == ["claude_code", "cursor"]
    assert "count" not in skill and skill["refusal"] is None


def test_a_skill_that_needs_its_plugin_says_so(home):
    inventory = demo_build(home)()
    adapters = {a.id: a for a in demo_adapters(home)}
    folder = next(p for p in home.rglob("planning/SKILL.md") if "marketplaces" in str(p))
    folder.write_text(folder.read_text() + "\nRun ${CLAUDE_PLUGIN_ROOT}/scripts/go.sh\n")
    skill = _row(library_offers(inventory, adapters), f"planning@superpowers@{MARKET}")
    assert skill["routes"] == {}
    assert skill["refusal"] == "This skill needs the rest of its plugin. Add the plugin instead."


def test_a_plugin_no_client_here_can_get_says_so(home):
    inventory = demo_build(home)()
    adapters = {a.id: a for a in demo_adapters(home)}
    # Only clients Kitden found count: with neither installer found, nobody can get it.
    inventory.clients = [
        replace(c, status=ClientStatus.NOT_FOUND) if c.id in ("claude_code", "codex") else c
        for c in inventory.clients
    ]
    db = _row(library_offers(inventory, adapters), f"db-tools@{MARKET}")
    assert db["routes"] == {}
    assert db["refusal"] == "No client here can get db-tools."


def test_the_endpoint_answers_the_rows(home):
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url="http://127.0.0.1:47800", follow_redirects=False) as page:
        assert page.get("/api/library-offers").status_code == 401
        page.get("/?token=tok")
        answer = page.get("/api/library-offers").json()
    assert [r["id"] for r in answer["offers"]] == [r["id"] for r in _offers(home)]
