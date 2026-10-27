"""Overview: what needs attention, in plain words (redesign plan, Task 3)."""

import json
from dataclasses import replace

import pytest

from kitden.changes.actions import KITDEN_GATEWAY
from kitden.clients import version_cache
from kitden.demo import build_demo_home
from kitden.gateways import add_gateway
from kitden.model import FindingType, Gateway
from kitden.views.findings import find_findings, mark_gateways
from kitden.views.gateway_view import gateway_view
from kitden.views.inventory import build_inventory
from kitden.views.load_map import load_map
from kitden.views.overview import overview
from tests.conftest import CURSOR_DB, make_home, write_cursor_fixture_state
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
    data = overview(build_inventory(home), [], None)
    assert [c["name"] for c in _cards(data, "attention")] == ["docker-expert", "superpowers"]
    assert data["counts"]["attention"] == 2
    assert data["notes"] == 14  # 14 names with notes (each note here is about another name)


def test_no_card_shows_a_file_path(home, tmp_path):
    db = home / CURSOR_DB
    db.write_bytes(b"this is not a database")
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    for card in overview(inventory, [gateway], None, held=[])["cards"]:
        assert "/" not in card["name"] + card["line"], card


def test_unreadable_file_becomes_an_attention_card(tmp_path):
    home = make_home(tmp_path, "cursor/3.21.16")
    db = home / CURSOR_DB
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a database")
    first = overview(build_inventory(home), [], None)["cards"][0]
    assert first["name"] == "Could not read state.vscdb"
    assert first["line"] == (
        "The file format is not recognized, so items from Cursor may be missing or wrong."
    )


def test_untested_version_is_an_attention_card(home, monkeypatch):
    monkeypatch.setattr(
        version_cache, "cached_version", lambda home, c: "2.0.0" if c == "claude_code" else None
    )
    first = overview(build_inventory(home), [], None)["cards"][0]
    assert first["name"] == "Claude Code 2.0.0 is not tested"
    assert first["line"] == "Tested from 2.1.283, so some items may be missing or wrong."


def test_an_empty_home_has_no_cards(tmp_path):
    empty = tmp_path / "empty-home"
    empty.mkdir()
    data = overview(build_inventory(empty), [], None)
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
    data = overview(build_inventory(connected), [], None, held=held)
    gateway = sorted(x["client"] for x in data["map"]["links"] if x["to"] == "gateway")
    assert gateway == ["claude_code", "cursor"]


def test_an_old_entry_is_not_linked_to_the_gateway(connected):
    from kitden.changes import toml_edit

    config = connected / ".codex/config.toml"
    old = {"command": "/Users/me/.local/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    data = overview(build_inventory(connected), [], None, held=[])
    assert "codex" not in [x["client"] for x in data["map"]["links"] if x["to"] == "gateway"]


def test_a_registered_gateway_alone_gets_no_move_in_card(home):
    # The move cards say "Kitden's rules", so they need the Kitden gateway.
    inventory = build_inventory(home)
    gateway = Gateway(url="https://mcp.neon.tech/mcp")
    mark_gateways(inventory, [gateway])
    data = overview(inventory, [gateway], None)
    assert _cards(data, "improve") == []


def test_servers_outside_the_gateway_can_improve_and_need_no_attention(home):
    held = [{"name": "kept", "kind": "local", "tools": 0}]
    data = overview(build_inventory(home), [], None, held=held)
    assert _cards(data, "improve")
    assert all(c["action"]["label"] != "Move in…" for c in _cards(data, "attention"))
    assert data["counts"]["attention"] == 2  # the two duplicates only


def test_a_server_in_two_clients_is_one_card(home):
    # The cards are the Gateway page's rows: a row holds every client's entry.
    inventory = build_inventory(home)
    held = [{"name": "kept", "kind": "local", "tools": 0}]
    data = overview(inventory, [], None, held=held)
    rows = gateway_view(inventory, [], None, kitden=held)["groups"]
    moves = [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Move in…"]
    names = [c["name"] for c in moves]
    assert names and len(names) == len(set(names))
    for card in moves:
        row = next(r for g in ("move", "local") for r in rows[g] if r["name"] == card["name"])
        assert card["clients"] == row["columns"]


def test_old_kitden_entries_get_one_card(home):
    from kitden.changes import toml_edit

    config = home / ".codex/config.toml"
    old = {"command": "/Users/me/.local/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    data = overview(build_inventory(home), [], None)
    [card] = [c for c in data["cards"] if c["name"].startswith("Old Kitden")]
    assert card["name"] == "Old Kitden entry in Codex"
    assert data["counts"]["attention"] == 3


def test_overview_duplicate_points_at_a_row_the_map_has(home):
    inventory = build_inventory(home)
    by_id = {i.id: i for i in inventory.items}
    twice = next(
        f
        for f in find_findings(inventory, None)
        if f.type is FindingType.DUPLICATE_IN_CLIENT and by_id[f.items[0]].name.startswith("superp")
    )
    card = next(c for c in overview(inventory, [], None)["cards"] if c["name"] == "superpowers")
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
    data = overview(inventory, [], None, held=held)
    assert "github" not in [c["name"] for c in data["cards"]]


def test_duplicate_cards_are_in_name_order_then_client_order():
    from types import SimpleNamespace

    from kitden.model import ItemKind
    from kitden.views.overview import _duplicates

    def item(id, kind, name):
        return SimpleNamespace(id=id, kind=kind, name=name)

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


def test_notes_count_items_not_findings(tmp_path):
    home = build_demo_home(tmp_path, "medium")  # 16 notes about 14 names: docs has three
    assert overview(build_inventory(home), [], None)["notes"] == 14


def test_the_notes_count_is_the_rows_the_page_draws_also_with_a_gateway(home):
    add_gateway(home, Gateway(url="https://gw.example.test/mcp"))
    with page_for(home) as page:
        count = page.get("/api/overview").json()["notes"]
        findings = page.get("/api/findings").json()
    names = {n for f in findings if f["severity"] == "info" for n in f["names"]}
    assert any(f["type"] == "bypasses_gateway" for f in findings)
    assert count == len(names)


# Cards with one action, and the "Your setup" map (Phase 7, Task 1) -------------------------


def test_a_server_that_skips_the_gateway_is_a_move_in_card_with_its_body(home):
    inventory = build_inventory(home)
    held = [{"name": "kept", "kind": "local", "state": "on", "differs": False, "tools": 2}]
    data = overview(inventory, [], None, held=held)
    rows = gateway_view(inventory, [], None, kitden=held)["groups"]
    row = next(r for r in rows["move"] if r["name"] == "github")
    card = next(c for c in _cards(data, "improve") if c["name"] == "github")
    assert card == {
        "id": card["id"],
        "group": "improve",
        "icon": "globe",
        "name": "github",
        "line": "Skips the gateway, so Kitden's rules don't reach it.",
        "clients": row["columns"],
        "action": {
            "label": "Move in…",
            # The same body as the Gateway's "Move into the gateway…" (details.js moveBody).
            "body": {
                "action": "gateway.move",
                "targets": [{"item": i} for i in row["items"]],
                "params": {"gateway": KITDEN_GATEWAY},
            },
        },
        "focus": {"clients": row["columns"], "block": "gateway"},
    }
    # A local server gets the local icon.
    local = [r["name"] for r in rows["local"] if r["items"] and not r["stays"]]
    shown = {c["name"]: c for c in _cards(data, "improve")}
    for name in local:
        if name in shown:
            assert shown[name]["icon"] == "hard-drive"


def test_a_server_a_move_would_refuse_gets_no_card(home):
    inventory = build_inventory(home)
    for index, item in enumerate(inventory.items):
        if item.name == "github":
            inventory.items[index] = replace(item, stays_direct="It stays direct.")
    data = overview(inventory, [], None, held=[{"name": "kept", "kind": "local", "tools": 0}])
    assert "github" not in [c["name"] for c in data["cards"]]


def test_more_than_three_servers_give_one_more_card(tmp_path):
    # Review Focus: the large sample has dozens of servers outside the gateway.
    with demo_page(tmp_path, "large") as page:
        data = page.get("/api/overview").json()
        view = page.get("/api/gateway-view").json()
    rows = [
        r for g in ("move", "local") for r in view["groups"][g] if r["items"] and not r["stays"]
    ]
    assert len(rows) > 4
    moves = [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Move in…"]
    assert len(moves) == 3
    [more] = [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Show…"]
    assert more["name"] == f"{len(rows) - 3} more servers skip the gateway"
    assert more["line"] == "Kitden's rules don't reach them."
    assert more["group"] == "improve"
    assert more["action"] == {
        "label": "Show…",
        "go": {"view": "gateway", "sel": "group:outside", "mode": "list"},
    }
    assert more["focus"]["block"] == "gateway"
    assert set(more["clients"]) <= {"claude_code", "codex", "cursor"}


def test_four_servers_give_three_cards_and_one_more_server(home):
    from kitden.changes import toml_edit

    config = home / ".codex/config.toml"
    text = config.read_text()
    for name in ("one", "two", "three", "four"):
        text = toml_edit.set_value(text, ("mcp_servers", name), {"url": f"https://{name}.test/"})
    config.write_text(text)
    inventory = build_inventory(home)
    held = [{"name": "kept", "kind": "local", "tools": 0}]
    rows = gateway_view(inventory, [], None, kitden=held)["groups"]
    movable = [r for g in ("move", "local") for r in rows[g] if r["items"] and not r["stays"]]
    data = overview(inventory, [], None, held=held)
    names = [c["name"] for c in _cards(data, "improve")]
    left = len(movable) - 3
    assert f"{left} more {'server skips' if left == 1 else 'servers skip'} the gateway" in names


def test_a_client_not_connected_gets_a_connect_card(connected):
    held = [{"name": "github", "kind": "local", "state": "on", "differs": False, "tools": 3}]
    data = overview(build_inventory(connected), [], None, held=held)
    connect = [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect…"]
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
                "label": "Connect…",
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
    data = overview(build_inventory(connected), [], None, held=held)
    [card] = [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect…"]
    assert card["action"]["body"] == {
        "action": "setup_server.enable",
        "targets": [{"client": "codex"}],
        "params": {},
    }


def test_no_connect_card_while_the_gateway_holds_nothing(connected):
    data = overview(build_inventory(connected), [], None, held=[])
    assert not [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect…"]


def test_old_kitden_entries_card_adds_the_update_row(connected):
    from kitden.changes import toml_edit

    config = connected / ".codex/config.toml"
    old = {"command": "/Users/me/.local/bin/agentsetup", "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    inventory = build_inventory(connected)
    item = next(i for i in inventory.items if i.name == "agentsetup")
    data = overview(inventory, [], None, held=[{"name": "github", "kind": "local", "tools": 0}])
    [card] = [c for c in data["cards"] if c["name"].startswith("Old Kitden")]
    assert card["group"] == "attention"
    assert card["icon"] == "house"
    assert card["line"] == (
        "The working version, agentsetup, made it; update it so Codex starts kitden."
    )
    assert card["clients"] == ["codex"]
    # The Agents page's "Update to Kitden…" (agents.js update).
    assert card["action"] == {
        "label": "Update…",
        "body": {"action": "setup_server.update", "targets": [{"item": item.id}], "params": {}},
    }
    assert card["focus"] == {"clients": ["codex"], "block": "gateway"}
    # An old entry is updated, not connected a second time.
    assert not [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect…"]


def test_a_duplicate_card_opens_the_item(home):
    data = overview(build_inventory(home), [], None)
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


def test_unreadable_and_untested_cards_have_no_button(home, monkeypatch):
    monkeypatch.setattr(
        version_cache, "cached_version", lambda home, c: "2.0.0" if c == "claude_code" else None
    )
    (home / CURSOR_DB).write_bytes(b"this is not a database")
    data = overview(build_inventory(home), [], None)
    unread = next(c for c in data["cards"] if c["name"] == "Could not read state.vscdb")
    assert unread["action"] is None
    assert unread["icon"] == "file-text"
    assert unread["clients"] == ["cursor"]
    assert unread["focus"] == {"clients": ["cursor"], "block": None}
    untested = next(c for c in data["cards"] if c["name"] == "Claude Code 2.0.0 is not tested")
    assert untested["action"] is None
    assert untested["icon"] == {"client": "claude_code"}
    assert untested["line"] == "Tested from 2.1.283, so some items may be missing or wrong."
    assert data["counts"]["attention"] == len(_cards(data, "attention"))


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
    data = overview(inventory, [], None, held=held, adapters=adapters)
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
    on = {c["id"] for c in shared["clients"] if c["state"] == "on"}
    assert {x["client"] for x in data["map"]["links"] if x["to"] == "gateway"} == on
    assert data["counts"] == {
        "attention": len(_cards(data, "attention")),
        "clients": len(found),
        "projects": len(inventory.projects),
    }
    # A project with gateway rules of its own has its own rules too.
    other = next(p for p in inventory.projects if p not in ruled)
    more = overview(inventory, [], None, held=held, adapters=adapters, gateway_rules={other.path})
    assert more["map"]["own_rules"] == len(ruled) + 1


def test_the_map_links_a_connected_client_to_the_gateway(connected):
    data = overview(build_inventory(connected), [], None, held=[])
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
    (home / CURSOR_DB).write_bytes(b"this is not a database")
    config = home / ".codex/config.toml"
    old = {"command": str(home / ".local/bin/agentsetup"), "args": ["mcp"]}
    config.write_text(toml_edit.set_value(config.read_text(), ("mcp_servers", "agentsetup"), old))
    held = [{"name": "kept", "kind": "local", "tools": 1}]
    data = overview(build_inventory(home), [], None, held=held)
    kinds = {c["action"]["label"] for c in data["cards"] if c["action"]}
    assert {"Keep one…", "Update…", "Move in…", "Connect…"} <= kinds
    for text in _strings({"cards": data["cards"], "map": data["map"]}):
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
    data = overview(build_inventory(home), [], None, held=[])
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
    assert not [c for c in data["cards"] if c["action"] and c["action"]["label"] == "Connect…"]
