"""Overview: what needs attention, in plain words (redesign plan, Task 3)."""

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from kitden.clients import version_cache
from kitden.context.rules import codex_rule
from kitden.demo import build_demo_home
from kitden.model import Finding, FindingType, Severity
from kitden.views import words
from kitden.views.context_view import context_view
from kitden.views.findings import find_findings
from kitden.views.gateway_view import gateway_view
from kitden.views.inventory import build_inventory
from kitden.views.load_map import load_map
from kitden.views.overview import FOLD_FROM, GATEWAY_IS, note_count, overview
from kitden.views.setup_server import kitden_on, setup_server_state
from tests.conftest import cursor_db, make_home, write_cursor_fixture_state
from tests.unit.test_context_view import (
    CODEX_A,
    CODEX_B,
    CODEX_C,
    a_budget,
    before_the_chat,
    claude_chat,
    codex_chat,
    codex_home,
    rule_skills,
    skill,
    view,
    window_for,
    write_json,
)
from tests.unit.test_demo_mode import demo_page
from tests.unit.test_local_gateway_views import page_for


@pytest.fixture
def home(tmp_path):
    # Cursor first: its fixture also has .claude files, and the Claude Code ones must win.
    home = make_home(tmp_path, "cursor/3.21.16", "claude_code/2.1.283", "codex/0.159.2")
    write_cursor_fixture_state(home)
    return home


def _cards(data, group=None):
    return [c for c in data["cards"] if group is None or c["group"] == group]


def test_attention_cards_and_the_notes_count(home):
    data = overview(build_inventory(home), None)
    assert [c["name"] for c in _cards(data, "attention")] == ["docker-expert", "superpowers"]
    assert data["counts"]["attention"] == 2
    # The items with notes; those with the same words fold into one row each (FOLD_FROM or more).
    # Servers outside the gateway are not notes.
    assert data["notes"] == 3


def test_no_card_shows_a_file_path(home, tmp_path):
    db = cursor_db(home)
    db.write_bytes(b"this is not a database")
    inventory = build_inventory(home)
    for card in overview(inventory, None, held=[])["cards"]:
        assert "/" not in card["name"] + card["line"], card


def test_unreadable_file_becomes_an_attention_card(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16")
    db = cursor_db(home)
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a database")
    first = overview(build_inventory(home), None)["cards"][0]
    assert first["name"] == "Could not read state.vscdb"
    assert first["line"] == (
        "In your Cursor settings: the file format is not recognized, so items from Cursor may "
        "be missing or wrong."
    )
    # The card names no path; its button copies it (02-N05).
    assert first["action"] == {"label": "Copy path", "copy": str(db)}


def test_untested_version_is_an_attention_card(home, monkeypatch):
    monkeypatch.setattr(
        version_cache, "cached_version", lambda home, c: "2.0.0" if c == "claude_code" else None
    )
    first = overview(build_inventory(home), None)["cards"][0]
    assert first["name"] == "Claude Code 2.0.0 is not tested"
    assert first["line"] == "Tested from 2.1.283, so some items may be missing or wrong."


def test_an_empty_home_has_no_cards(tmp_path):
    empty = tmp_path / "empty-home"
    empty.mkdir()
    data = overview(build_inventory(empty), None)
    assert data["cards"] == [] and data["counts"]["attention"] == 0


def _add_kitden_entry(home, relative):
    path = home / relative
    data = json.loads(path.read_text())
    data.setdefault("mcpServers", {})["kitden"] = {"command": "kitden", "args": ["mcp"]}
    path.write_text(json.dumps(data))


@pytest.fixture
def connected(home):
    """Claude Code and Cursor have the kitden entry; Codex does not."""
    _add_kitden_entry(home, ".claude.json")
    _add_kitden_entry(home, ".cursor/mcp.json")
    return home


def test_a_turned_off_kitden_entry_is_not_linked_to_the_gateway(connected):
    codex = connected / ".codex/config.toml"
    off = '\n[mcp_servers.kitden]\ncommand = "kitden"\nargs = ["mcp"]\nenabled = false\n'
    codex.write_text(codex.read_text() + off)
    held = [{"name": "github", "kind": "local", "state": "on", "differs": False}]
    data = overview(build_inventory(connected), None, held=held)
    gateway = sorted(x["client"] for x in data["map"]["links"] if x["to"] == "gateway")
    assert gateway == ["claude_code", "cursor"]


def test_an_old_entry_is_not_linked_to_the_gateway(connected):
    from kitden.changes import toml_edit

    config = connected / ".codex/config.toml"
    old = {"command": "/Users/me/.local/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    data = overview(build_inventory(connected), None, held=[])
    assert "codex" not in [x["client"] for x in data["map"]["links"] if x["to"] == "gateway"]


def test_servers_outside_the_gateway_can_improve_and_need_no_attention(home):
    held = [{"name": "kept", "kind": "local", "tools": 0}]
    data = overview(build_inventory(home), None, held=held)
    assert _cards(data, "improve")
    assert all(c["action"]["label"] != "Move in…" for c in _cards(data, "attention"))
    assert data["counts"]["attention"] == 2  # the two duplicates only


def _gateway_card(data):
    [card] = [c for c in data["cards"] if c["name"].endswith("can move into the gateway")]
    return card


def test_the_servers_that_can_move_in_fold_into_one_card(home):
    """One card for every server a move can take (02-R05): it says what the gateway is, counts
    each server once (a server in two clients, or remote and local of one name) and opens the
    Gateway's List at the outside group. No Move in… card per server."""
    inventory = build_inventory(home)
    held = [{"name": "kept", "kind": "local", "tools": 0}]
    data = overview(inventory, None, held=held)
    rows = gateway_view(inventory, None, kitden=held)["groups"]
    movable = [r for g in ("move", "local") for r in rows[g] if r["items"] and not r["stays"]]
    names = {r["name"] for r in movable}
    card = _gateway_card(data)
    assert card == {
        "id": card["id"],
        "group": "improve",
        "icon": "server",
        "name": f"{len(names)} servers can move into the gateway",
        "line": GATEWAY_IS,
        "clients": card["clients"],
        "action": {
            "label": "Open in Gateway",
            "go": {"view": "gateway", "sel": "group:outside", "mode": "list"},
        },
        "focus": {"clients": card["clients"], "block": "gateway"},
    }
    assert set(card["clients"]) == {c for r in movable for c in r["columns"]}
    assert not [c for c in data["cards"] if (c["action"] or {}).get("label") == "Move in…"]


def test_a_remote_and_a_local_server_of_one_name_count_once():
    from kitden.views.overview import _move_ins

    def row(name, item):
        return {"name": name, "items": [item], "stays": None, "columns": ["codex"]}

    groups = {"move": [row("docs", "r1"), row("github", "g1")], "local": [row("docs", "l1")]}
    [card] = _move_ins(groups)
    assert card["name"] == "2 servers can move into the gateway"
    one = {"move": [row("docs", "r1")], "local": []}
    assert _move_ins(one)[0]["name"] == "1 server can move into the gateway"
    assert _move_ins({"move": [], "local": []}) == []


def test_a_server_a_move_would_refuse_is_not_counted(home):
    inventory = build_inventory(home)
    held = [{"name": "kept", "kind": "local", "tools": 0}]
    before = _gateway_card(overview(inventory, None, held=held))["name"]
    for index, item in enumerate(inventory.items):
        if item.name == "github":
            inventory.items[index] = replace(item, stays_direct="It stays direct.")
    after = _gateway_card(overview(inventory, None, held=held))["name"]
    assert int(after.split()[0]) == int(before.split()[0]) - 1


def test_a_picked_project_counts_its_own_servers(tmp_path):
    with demo_page(tmp_path) as page:
        ids = {Path(p["path"]).name: p["id"] for p in page.get("/api/projects").json()}
        shared = page.get("/api/overview").json()
        here = page.get(f"/api/overview?project={ids['website']}").json()
        view = page.get(f"/api/gateway-view?project={ids['website']}").json()
    names = {
        r["name"]
        for g in ("move", "local")
        for r in view["groups"][g]
        if r["items"] and not r["stays"]
    }
    assert _gateway_card(here)["name"] == f"{len(names)} servers can move into the gateway"
    # website has a server of its own that All projects does not count.
    assert _gateway_card(shared)["name"] == f"{len(names) - 1} servers can move into the gateway"


def test_old_kitden_entries_get_one_card(home):
    from kitden.changes import toml_edit

    config = home / ".codex/config.toml"
    old = {"command": "/Users/me/.local/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    data = overview(build_inventory(home), None)
    [card] = [c for c in data["cards"] if c["name"].startswith("Old Kitden")]
    assert card["name"] == "Old Kitden entry in Codex"
    assert data["counts"]["attention"] == 3


def test_kitden_entries_whose_program_is_gone_say_so(home, real_programs):
    from kitden.changes import toml_edit

    config = home / ".codex/config.toml"
    gone = {"command": str(home / "gone/bin/kitden"), "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "kitden"), gone))
    data = overview(build_inventory(home), None)
    [card] = [c for c in data["cards"] if c["name"].startswith("Old Kitden")]
    assert card["line"] == (
        "Its program is gone: Kitden was moved or removed. Update it so Codex starts this Kitden."
    )


def test_overview_duplicate_points_at_a_row_the_map_has(home):
    inventory = build_inventory(home)
    by_id = {i.id: i for i in inventory.items}
    twice = next(
        f
        for f in find_findings(inventory, None)
        if f.type is FindingType.DUPLICATE_IN_CLIENT and by_id[f.items[0]].name.startswith("superp")
    )
    card = next(c for c in overview(inventory, None)["cards"] if c["name"] == "superpowers")
    first = by_id[twice.items[0]]
    assert card["action"]["go"] == {"view": "library", "sel": f"{first.kind}:{first.name}"}
    assert first.name in {r.lookup for r in load_map(inventory, None)}


def test_a_server_without_a_removable_entry_gets_no_card(home):
    # The Gateway page shows "Move into the gateway…" only on rows Kitden can remove, so the
    # Overview offers only those rows too.
    inventory = build_inventory(home)
    held = [{"name": "kept", "kind": "local", "tools": 0}]
    for index, item in enumerate(inventory.items):
        if item.name == "github":
            inventory.items[index] = replace(item, actions=())
    data = overview(inventory, None, held=held)
    assert "github" not in [c["name"] for c in data["cards"]]


def test_duplicate_cards_are_in_name_order_then_client_order():
    from types import SimpleNamespace

    from kitden.model import ItemKind
    from kitden.views.overview import _duplicates

    def item(id, kind, name):
        source = SimpleNamespace(path=None, owner_client=None)
        return SimpleNamespace(id=id, kind=kind, name=name, source=source, actions=(), client="")

    items = [
        item("z", ItemKind.SKILL, "zeta"),
        item("a", ItemKind.PLUGIN, "alpha"),
        item("ts", ItemKind.SKILL, "tidy"),
        item("tp", ItemKind.PLUGIN, "tidy"),
    ]

    def twice(id, client):
        return SimpleNamespace(type=FindingType.DUPLICATE_IN_CLIENT, items=(id, id), client=client)

    # Found out of order: zeta, alpha, then "tidy" as a skill in Cursor and a plugin in Claude Code.
    findings = [twice("z", "codex"), twice("a", "cursor"), twice("ts", "cursor")]
    findings.append(twice("tp", "claude_code"))
    cards = _duplicates(SimpleNamespace(items=items), findings)
    assert [(c["name"], c["clients"]) for c in cards] == [
        ("alpha", ["cursor"]),
        ("tidy", ["claude_code"]),
        ("tidy", ["cursor"]),
        ("zeta", ["codex"]),
    ]


def test_notes_count_rows_not_findings(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # more notes than names: docs has two
    assert overview(build_inventory(home), None)["notes"] == 4


def test_the_notes_count_is_the_rows_the_page_draws(home):
    with page_for(home) as page:
        count = page.get("/api/overview").json()["notes"]
        findings = page.get("/api/findings").json()
    names = {n for f in findings if f["severity"] == "info" for n in f["names"]}
    assert count <= len(names)


def test_the_notes_do_not_count_servers_outside_the_gateway(home):
    """A third count of servers outside the gateway ("N items are not connected to the gateway")
    is gone (02-R06): the Can improve card says how many can move in, the Gateway shows them."""
    held = [{"name": "kept", "kind": "local", "tools": 0}]
    with page_for(home) as page:
        findings = page.get("/api/findings").json()
    assert not [f for f in findings if f["type"] == "bypasses_gateway"]
    data = overview(build_inventory(home), None, held=held)
    info = [f for f in find_findings(build_inventory(home), None) if f.severity is Severity.INFO]
    assert data["notes"] == note_count(info)


def _note(kind, *names):
    return Finding(kind, Severity.INFO, ("i",), "x", names=names)


def test_note_count_folds_repeats():
    # The same example as tests/frontend/overview.test.mjs ("items with the same words fold"):
    # five items that load from another client are one row, three with an unreadable state are
    # three rows, and "docs" with two notes is one row. Five rows in all.
    findings = [_note(FindingType.CROSS_LOADED, n) for n in "abcde"]
    findings += [_note(FindingType.UNKNOWN_STATE, n) for n in ("u1", "u2", "u3")]
    findings += [
        _note(FindingType.SAME_NAME_OTHER_SOURCE, "docs"),
        _note(FindingType.BYPASSES_GATEWAY, "docs"),
    ]
    assert FOLD_FROM == 4
    assert note_count(findings) == 5
    # Exactly four fold; three stay single.
    assert note_count(findings[:4]) == 1
    assert note_count(findings[:3]) == 3
    # Items with two notes in the same order fold too; the same notes in another order do not.
    both = [
        _note(kind, name)
        for name in "wxyz"
        for kind in (FindingType.CROSS_LOADED, FindingType.BYPASSES_GATEWAY)
    ]
    assert note_count(both) == 1
    assert note_count(both[:-2] + both[-1:] + both[-2:-1]) == 4


# Cards with one action, and the "Your setup" map (Phase 7, Task 1) -------------------------


def test_a_client_not_connected_gets_a_connect_card(connected):
    held = [{"name": "github", "kind": "local", "state": "on", "differs": False, "tools": 3}]
    data = overview(build_inventory(connected), None, held=held)
    connect = [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect"]
    assert connect == [
        {
            "id": connect[0]["id"],
            "group": "improve",
            "icon": {"client": "codex"},
            "name": "Codex",
            "line": "Not connected to the gateway yet.",
            "clients": ["codex"],
            # The Gateway's own Connect for this client (parts.js kitdenClients).
            "action": {
                "label": "Connect",
                "body": {
                    "action": "setup_server.register",
                    "targets": [{"client": "codex"}],
                    "params": {},
                },
            },
            "focus": {"clients": ["codex"], "block": "gateway"},
        }
    ]


def test_a_turned_off_codex_entry_is_turned_on_by_its_connect_card(connected):
    codex = connected / ".codex/config.toml"
    off = '\n[mcp_servers.kitden]\ncommand = "kitden"\nargs = ["mcp"]\nenabled = false\n'
    codex.write_text(codex.read_text() + off)
    held = [{"name": "github", "kind": "local", "tools": 0}]
    data = overview(build_inventory(connected), None, held=held)
    [card] = [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect"]
    assert card["action"]["body"] == {
        "action": "setup_server.enable",
        "targets": [{"client": "codex"}],
        "params": {},
    }


def test_no_connect_card_while_the_gateway_holds_nothing(connected):
    data = overview(build_inventory(connected), None, held=[])
    assert not [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect"]


def test_old_kitden_entries_card_adds_the_update_row(connected):
    from kitden.changes import toml_edit

    config = connected / ".codex/config.toml"
    old = {"command": "/Users/me/.local/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    inventory = build_inventory(connected)
    item = next(i for i in inventory.items if i.name == "agentsetup")
    data = overview(inventory, None, held=[{"name": "github", "kind": "local", "tools": 0}])
    [card] = [c for c in data["cards"] if c["name"].startswith("Old Kitden")]
    assert card["group"] == "attention"
    assert card["icon"] == "house"
    assert card["line"] == (
        "The working version, agentsetup, made it; update it so Codex starts kitden."
    )
    assert card["clients"] == ["codex"]
    # The Agents page's "Update to Kitden…" (agents.js update).
    assert card["action"] == {
        "label": "Update",
        "body": {"action": "setup_server.update", "targets": [{"item": item.id}], "params": {}},
    }
    assert card["focus"] == {"clients": ["codex"], "block": "gateway"}
    # An old entry is updated, not connected a second time.
    assert not [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect"]


def test_a_duplicate_card_opens_the_item(home):
    data = overview(build_inventory(home), None)
    card = next(c for c in data["cards"] if c["name"] == "superpowers")
    assert card["group"] == "attention"
    assert card["icon"] == "puzzle"
    assert card["line"] == "Two copies of one plugin load; keep one."
    assert card["clients"] == ["cursor"]
    assert card["action"]["label"] == "Keep one…"
    assert card["action"]["go"]["view"] == "library"
    assert card["action"]["go"]["sel"].startswith("plugin:superpowers")
    assert card["focus"] == {"clients": ["cursor"], "block": "library"}
    skill = next(c for c in data["cards"] if c["name"] == "docker-expert")
    assert skill["icon"] == "sparkles"
    assert skill["clients"] == ["codex", "cursor"]
    assert skill["line"] == "Two copies of one skill load; keep one."


def test_an_unreadable_card_copies_its_path_and_an_untested_one_has_no_button(home, monkeypatch):
    monkeypatch.setattr(
        version_cache, "cached_version", lambda home, c: "2.0.0" if c == "claude_code" else None
    )
    (cursor_db(home)).write_bytes(b"this is not a database")
    data = overview(build_inventory(home), None)
    unread = next(c for c in data["cards"] if c["name"] == "Could not read state.vscdb")
    assert unread["action"]["label"] == "Copy path"
    assert unread["icon"] == "file-text"
    assert unread["clients"] == ["cursor"]
    assert unread["focus"] == {"clients": ["cursor"], "block": None}
    untested = next(c for c in data["cards"] if c["name"] == "Claude Code 2.0.0 is not tested")
    assert untested["action"] is None
    assert untested["icon"] == {"client": "claude_code"}
    assert untested["line"] == "Tested from 2.1.283, so some items may be missing or wrong."
    assert data["counts"]["attention"] == len(_cards(data, "attention"))


def test_the_overview_reads_the_catalogs_once_however_many_projects(tmp_path, monkeypatch):
    # With 26 projects the Overview took 12 s on a real setup: it built the whole Library map,
    # catalogs and all, for each project, only to count the projects with rules of their own.
    from kitden.demo import demo_adapters
    from kitden.views import library_map as module

    home = build_demo_home(tmp_path, "medium")
    adapters = {a.id: a for a in demo_adapters(home)}
    inventory = build_inventory(home, list(adapters.values()), [])
    assert len(inventory.projects) > 1
    calls = []
    real = module.catalog
    monkeypatch.setattr(module, "catalog", lambda *a, **k: calls.append(1) or real(*a, **k))
    overview(inventory, None, held=[], adapters=adapters)
    assert len(calls) == 1


def test_the_map_counts_servers_tools_plugins_skills_and_own_rules(tmp_path):
    from kitden.demo import demo_adapters
    from kitden.views.library_map import library_map

    home = build_demo_home(tmp_path, "medium")
    atlas = home / "work/atlas"
    atlas.joinpath(".claude").mkdir(parents=True, exist_ok=True)
    (atlas / ".claude/settings.local.json").write_text(
        json.dumps({"skillOverrides": {"brandkit": "off"}})
    )
    adapters = {a.id: a for a in demo_adapters(home)}
    inventory = build_inventory(home, list(adapters.values()), [])
    held = [
        {"name": "a", "kind": "local", "tools": 4},
        {"name": "b", "kind": "remote", "tools": None},
        {"name": "c", "kind": "remote", "tools": 7},
    ]
    data = overview(inventory, None, held=held, adapters=adapters)
    shared = library_map(inventory, adapters, None)
    items = [i for g in shared["groups"] for i in g["items"]]

    def own(project):
        answer = library_map(inventory, adapters, project.path)
        return any(
            any(i["here"].values())
            for g in answer["groups"]
            for i in g["items"]
            if i["kind"] in ("plugin", "skill")
        )

    ruled = [p for p in inventory.projects if own(p)]
    assert str(atlas) in [p.path for p in ruled]
    found = [c for c in inventory.clients if str(c.status) == "found"]
    assert data["map"] == {
        "clients": [
            {
                "id": c.id,
                "name": c.display_name,
                "version": c.version,
                "tested": c.version_supported,
                "on": True,
            }
            for c in found
        ],
        "gateway": {"servers": 3, "tools": 11, "unread": False},
        "library": {
            "plugins": sum(i["kind"] == "plugin" for i in items),
            "skills": sum(i["kind"] == "skill" for i in items),
        },
        "links": data["map"]["links"],
        "projects": len(inventory.projects),
        "own_rules": len(ruled),
    }
    # A client links to the Library when it loads a plugin or skill, and to the gateway while
    # its kitden entry is on.
    loads = {c for i in items for c, how in i["by"].items() if how == "on"}
    assert {x["client"] for x in data["map"]["links"] if x["to"] == "library"} == loads
    # The Library map's client states say what a client loads, so the gateway links are the
    # clients whose kitden entry is on (the Gateway's "Connected").
    on = {e["client"] for e in setup_server_state(inventory) if kitden_on(e)}
    assert {x["client"] for x in data["map"]["links"] if x["to"] == "gateway"} == on
    assert data["counts"] == {
        "attention": len(_cards(data, "attention")),
        "clients": len(found),
        "projects": len(inventory.projects),
    }
    # A project with gateway rules of its own has its own rules too.
    other = next(p for p in inventory.projects if p not in ruled)
    more = overview(inventory, None, held=held, adapters=adapters, gateway_rules={other.path})
    assert more["map"]["own_rules"] == len(ruled) + 1


def test_the_map_links_a_connected_client_to_the_gateway(connected):
    data = overview(build_inventory(connected), None, held=[])
    gateway = sorted(x["client"] for x in data["map"]["links"] if x["to"] == "gateway")
    assert gateway == ["claude_code", "cursor"]


def _strings(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)
    elif isinstance(value, str):
        yield value


def test_no_card_or_map_field_holds_a_path(home, monkeypatch):
    from kitden.changes import toml_edit

    monkeypatch.setattr(
        version_cache, "cached_version", lambda home, c: "2.0.0" if c == "claude_code" else None
    )
    (cursor_db(home)).write_bytes(b"this is not a database")
    config = home / ".codex/config.toml"
    old = {"command": str(home / ".local/bin/agentsetup"), "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    held = [{"name": "kept", "kind": "local", "tools": 1}]
    data = overview(build_inventory(home), None, held=held)
    kinds = {c["action"]["label"] for c in data["cards"] if c["action"]}
    assert {"Keep one…", "Update", "Open in Gateway", "Connect"} <= kinds
    # "Copy path" holds the path for the clipboard; nothing the card shows does.
    shown = [c | {"action": c["action"] and {**c["action"], "copy": None}} for c in data["cards"]]
    for text in _strings({"cards": shown, "map": data["map"]}):
        assert str(home) not in text and not text.startswith(("/", "~")), text
        assert "\\" not in text and "/." not in text, text


def test_the_page_answers_the_map_with_the_library_and_gateway_rules(tmp_path):
    from pathlib import Path

    with demo_page(tmp_path) as page:
        data = page.get("/api/overview").json()
        projects = page.get("/api/projects").json()
        library = page.get("/api/library-map").json()
        kitden = page.get("/api/gateway-view").json()["gateways"][0]
        ruled = set()
        for project in projects:
            answer = page.get(f"/api/library-map?project={project['id']}").json()
            here = any(
                any(i["here"].values())
                for g in answer["groups"]
                for i in g["items"]
                if i["kind"] in ("plugin", "skill")
            )
            if here or project["own_rules"]:
                ruled.add(Path(project["path"]).name)
    # atlas and web have gateway rules; website turns a plugin off in its own settings.
    assert {"atlas", "web", "website"} <= ruled
    assert data["map"]["own_rules"] == len(ruled)
    assert data["map"]["projects"] == data["counts"]["projects"] == len(projects)
    items = [i for g in library["groups"] for i in g["items"]]
    assert data["map"]["library"] == {
        "plugins": sum(i["kind"] == "plugin" for i in items),
        "skills": sum(i["kind"] == "skill" for i in items),
    }
    assert data["map"]["gateway"] == {
        "servers": len(kitden["servers"]),
        "tools": sum(s["tools"] or 0 for s in kitden["servers"]),
        "unread": False,
    }


def test_a_client_not_on_this_mac_is_on_the_map_but_off_and_unlinked(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    data = overview(build_inventory(home), None, held=[])
    on = {c["id"]: c["on"] for c in data["map"]["clients"]}
    assert on["claude_code"] is True
    assert on.get("cursor") is not True
    assert all(x["client"] == "claude_code" for x in data["map"]["links"])
    assert data["counts"]["clients"] == sum(on.values())


def test_unreadable_gateway_settings_need_attention_and_claim_nothing(home):
    # A broken gateway.json reads as empty: the page says it could not read it, counts it, shows
    # no "0 servers" and offers no move into that gateway.
    from kitden.gateways import data_dir
    from kitden.local_gateway.settings import SETTINGS_FILE
    from tests.unit.test_local_gateway_views import page_for

    path = data_dir(home) / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json")
    with page_for(home) as page:
        data = page.get("/api/overview").json()
    [card] = [c for c in data["cards"] if c["name"] == "Could not read the Kitden gateway settings"]
    assert card["group"] == "attention" and card["action"] is None
    assert card["icon"] == "file-text"
    assert card["line"] == (
        "Kitden can't read gateway.json, so the gateway's servers and rules are not known."
    )
    assert card["focus"] == {"clients": [], "block": "gateway"}
    assert str(home) not in card["line"] and "/" not in card["line"]
    assert data["counts"]["attention"] >= 1
    assert data["map"]["gateway"] == {"servers": None, "tools": None, "unread": True}
    assert not [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Move in…"]
    assert not [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect"]


# Context: a card when the last chat's skill list did not fit

LONG = "Use it when the task needs a careful plan. " * 30


def _context_home(tmp_path):
    home = tmp_path / "home"
    for root in (".claude", ".codex", ".cursor"):
        (home / root).mkdir(parents=True)
    return home


def _context_cards(home, project=None, **kwargs):
    """The gauge cards of the Overview on `home`, given the Context page's client cards."""
    inventory = build_inventory(home)
    folder = str(project) if project else None
    clients = context_view(inventory, home, home / ".codex", folder, {})["clients"]
    data = overview(inventory, folder, context_cards=clients, **kwargs)
    return [c for c in data["cards"] if c["icon"] == "gauge"]


def _claude_chat_with_names_only(home, folder="/work/a"):
    """A chat of four skills where two showed only a name (a budget of 2,100 characters)."""
    for name in ("alpha", "beta", "gamma", "delta"):
        skill(home / ".claude/skills", name, LONG[:1000])
    write_json(home / ".claude/settings.json", {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "2100"}})
    sent = {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None}
    claude_chat(home, sent, model="claude-sonnet-4-6", folder=folder)


def _codex_chat(home, kind):
    """A Codex chat where two descriptions were cut short, or one skill was left out."""
    paths = codex_home(home, window=1)
    if kind == "cut":
        budget = a_budget(paths, lambda fit: fit.cap is not None and fit.cap >= 30)
        cap = codex_rule(rule_skills(paths), budget).cap
        lines = [
            f"- alpha: {CODEX_A[:cap]} (file: {paths['alpha']})",
            f"- beta: {CODEX_B[: cap - 1]} (file: {paths['beta']})",
            f"- gamma: {CODEX_C} (file: {paths['gamma']})",
        ]
    else:
        budget = a_budget(paths, lambda fit: fit.sent == {"alpha": 0, "beta": 0, "gamma": None})
        lines = [f"- alpha: (file: {paths['alpha']})", f"- beta: (file: {paths['beta']})"]
    codex_home(home, window=window_for(budget))
    before_the_chat(Path(paths["gamma"]))  # a skill written after the chat was not left out
    codex_chat(home, lines, at="2026-11-07T12:00:00Z")


def test_a_claude_list_that_showed_only_names_gets_a_card(tmp_path):
    home = _context_home(tmp_path)
    _claude_chat_with_names_only(home)
    [card] = _context_cards(home)
    assert card["group"] == "attention"
    assert (
        card["line"]
        == "2 skills showed only a name in your last Claude Code chat. " + words.LIMIT_NOT_FIXED
    )
    assert card["clients"] == ["claude_code"]
    assert card["action"] == {
        "label": "Open in Context",
        "go": {"view": "context", "sel": "client:claude_code"},
    }


def test_a_codex_list_that_was_cut_gets_a_card(tmp_path):
    home = _context_home(tmp_path)
    _codex_chat(home, "cut")
    [card] = _context_cards(home)
    # Context's suggested limit is the card's one press, with its cost (05-P3).
    # The cost counts the skills' file paths, which differ from one machine to the next.
    assert re.fullmatch(
        r"2 skills were cut short in your last Codex chat\. Set to 500 tokens fits them: about "
        r"\d+ more tokens in every chat\.",
        card["line"],
    ), card["line"]
    assert card["clients"] == ["codex"]
    assert card["action"] == {
        "label": "Set to 500 tokens",
        "body": {
            "action": "skill.limit",
            "targets": [{"client": "codex"}],
            "params": {"tokens": 500},
        },
    }


def test_a_codex_list_that_left_a_skill_out_says_so(tmp_path):
    home = _context_home(tmp_path)
    _codex_chat(home, "out")
    [card] = _context_cards(home)
    assert card["line"].startswith("1 skill was left out of your last Codex chat. Set to ")


def test_a_list_that_fits_gets_no_card(tmp_path):
    home = _context_home(tmp_path)
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(home, {"alpha": "Does alpha."})
    paths = codex_home(home, window=272_000)
    codex_chat(home, [f"- alpha: {CODEX_A} (file: {paths['alpha']})"])
    assert _context_cards(home) == []


def test_cursor_and_clients_without_a_chat_get_no_card(tmp_path):
    home = _context_home(tmp_path)
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    skill(home / ".cursor/skills-cursor", "beta", "Does beta.")
    assert _context_cards(home) == []


def test_the_skill_list_card_comes_first(tmp_path):
    # What hurts most first: a list that cut skills costs every chat (02-N06).
    home = _context_home(tmp_path)
    _claude_chat_with_names_only(home)
    back = [{"name": "docs", "client": "codex", "app": None}]
    data = overview(
        build_inventory(home),
        None,
        came_back=back,
        context_cards=view(home).values(),
    )
    assert [c["icon"] for c in data["cards"]] == ["gauge", "server"]
    assert data["counts"]["attention"] == 2


def test_a_picked_project_gets_the_card_of_its_own_last_chat(tmp_path):
    home = _context_home(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    _claude_chat_with_names_only(home, folder=str(project))
    assert [c["line"] for c in _context_cards(home, project)] == [
        "2 skills showed only a name in your last Claude Code chat. " + words.LIMIT_NOT_FIXED
    ]
    # Another project has no chat of its own.
    other = tmp_path / "other"
    other.mkdir()
    assert _context_cards(home, other) == []


def test_the_page_passes_the_context_cards_to_the_overview(tmp_path):
    from tests.unit.test_local_gateway_views import page_for

    home = _context_home(tmp_path)
    _claude_chat_with_names_only(home)
    with page_for(home) as page:
        cards = page.get("/api/overview").json()["cards"]
    [card] = [c for c in cards if c["icon"] == "gauge"]
    assert (
        card["line"]
        == "2 skills showed only a name in your last Claude Code chat. " + words.LIMIT_NOT_FIXED
    )


def test_a_context_read_that_fails_leaves_the_rest_of_the_overview(tmp_path, monkeypatch):
    import kitden.web.app as web_app
    from tests.unit.test_local_gateway_views import page_for

    def broken(*args, **kwargs):
        raise OverflowError("a chat log Kitden does not understand")

    monkeypatch.setattr(web_app, "context_view", broken)
    home = _context_home(tmp_path)
    _claude_chat_with_names_only(home)
    with page_for(home) as page:
        answer = page.get("/api/overview")
    assert answer.status_code == 200
    assert not [c for c in answer.json()["cards"] if c["icon"] == "gauge"]
    assert "counts" in answer.json()


def test_four_cards_of_one_kind_fold_into_one_row(home, monkeypatch):
    # 02-N06: 35 "Keep one…" cards came before the skill list cards. From four on, one row
    # with a count holds them, and the lede still counts each.
    from kitden.views import overview as view_module

    def copies(inventory, findings):
        return [
            view_module._card(
                f"d{i}", "attention", "sparkles", f"s{i}", "x", ["codex"], None, "library"
            )
            for i in range(5)
        ]

    monkeypatch.setattr(view_module, "_duplicates", copies)
    data = overview(build_inventory(home), None)
    [row] = [c for c in data["cards"] if c.get("cards")]
    assert row["name"] == "5 skills load more than once"
    assert row["line"] == "Open the list to keep one copy of each."
    assert row["action"] == {"label": "Show", "fold": True}
    assert [c["name"] for c in row["cards"]] == [f"s{i}" for i in range(5)]
    assert data["counts"]["attention"] == 5


def test_three_cards_of_one_kind_stay_cards():
    from kitden.views.overview import _card, _fold

    cards = [_card(str(i), "attention", "puzzle", "p", "x", [], None, "library") for i in range(3)]
    assert _fold(cards, "duplicate") == cards


def test_an_unreadable_file_in_a_project_names_the_project(tmp_path):
    # 02-N05: the sample's first card named no project and did nothing.
    home = build_demo_home(tmp_path, "medium")
    cards = overview(build_inventory(home), None)["cards"]
    card = next(c for c in cards if c["name"] == "Could not read mcp.json")
    assert card["line"].startswith("In project website: the file has a syntax error")
    path = home / "work/website/.cursor/mcp.json"
    assert card["action"] == {"label": "Copy path", "copy": str(path)}


def test_after_apply_the_skill_list_card_says_a_new_chat_shows_it_and_needs_no_attention(tmp_path):
    # Round 3, row 5 (05-P3): the card stayed, counted as needing attention.
    from tests.unit.test_skill_limit import cut_chat

    home = _context_home(tmp_path)
    cut_chat(home)
    [card] = _context_cards(home)
    assert card["group"] == "attention" and card["action"]["label"] == "Set to 1.1%"
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.011})
    [card] = _context_cards(home)
    assert card["group"] == "improve"
    assert card["line"] == (
        "The limit was changed after this chat: it is 1.1% now. Start a new chat to see the new "
        "list."
    )
    assert card["action"]["label"] == "Open in Context"
    inventory = build_inventory(home)
    clients = context_view(inventory, home, home / ".codex", None, {})["clients"]
    assert overview(inventory, None, context_cards=clients)["counts"]["attention"] == 0


def test_a_skill_list_card_with_no_offer_gives_contexts_reason():
    # Round 3, row 5 (04-C11): Codex's card said nothing of why there is no fix.
    from kitden.views import words
    from kitden.views.overview import _context

    why = words.CODEX_LIMIT_NOT_ENOUGH.format(n="10,000")
    card = {
        "client": "codex",
        "lamp": "warn",
        "windows": [{"result": {"misfit": {"kind": "cut", "n": 31}}}],
        "limit": {"offer": None, "why": why},
        "now": None,
        "changed": [],
    }
    [out] = _context([card])
    assert out["line"] == f"31 skills were cut short in your last Codex chat. {why}"
    assert out["group"] == "attention"


def test_a_largest_share_that_leaves_some_says_so_on_the_card():
    from kitden.views.overview import _context

    offer = {
        "fraction": 0.04,
        "label": "Set to 4%",
        "say": "",
        "cost": "About 24,000 more",
        "leaves": 21,
    }
    card = {
        "client": "claude_code",
        "lamp": "warn",
        "windows": [{"result": {"misfit": {"kind": "name", "n": 45}}}],
        "limit": {"offer": offer, "param": "fraction", "why": None},
        "now": None,
        "changed": [],
    }
    [out] = _context([card])
    assert out["line"] == (
        "45 skills showed only a name in your last Claude Code chat. Set to 4% leaves 21 with "
        "only a name: about 24,000 more."
    )


def test_a_skill_and_a_server_of_one_name_are_two_note_rows():
    """sentry the skill loads from another client; sentry the server is in two clients. One
    row would say both of one thing (02-R07): each kind is its own row."""
    skill = Finding(
        FindingType.CROSS_LOADED, Severity.INFO, ("s",), "x", names=("sentry",), kinds=("skill",)
    )
    server = Finding(
        FindingType.SAME_IN_OTHER_CLIENTS,
        Severity.INFO,
        ("m",),
        "x",
        names=("sentry",),
        kinds=("mcp_server",),
    )
    assert note_count([skill, server]) == 2
