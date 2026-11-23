"""Which clients Kitden reads: the stored choice, the scan and the route."""

import json
import re

import pytest
from starlette.testclient import TestClient

from kitden.clients import choice
from kitden.clients.choice import clients_on, off_clients, set_client
from kitden.gateways import data_dir
from kitden.model import ClientStatus
from kitden.views.inventory import build_inventory, default_adapters
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
ALL = ("claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")


def _file(home):
    return data_dir(home) / choice.CHOICE_FILE


def test_no_file_means_none_is_off(tmp_path):
    home = make_home(tmp_path, *ALL)
    assert off_clients(home) == frozenset()
    assert clients_on(home) == ["claude_code", "codex", "cursor"]


@pytest.mark.parametrize("text", ["{not json", "[]", '{"off": "codex"}', '{"off": 3}', "null"])
def test_a_broken_file_means_none_is_off(tmp_path, text):
    home = make_home(tmp_path, *ALL)
    _file(home).parent.mkdir(parents=True, exist_ok=True)
    _file(home).write_text(text)
    assert off_clients(home) == frozenset()


def test_unknown_ids_are_ignored(tmp_path):
    home = make_home(tmp_path, *ALL)
    _file(home).parent.mkdir(parents=True, exist_ok=True)
    _file(home).write_text(json.dumps({"off": ["codex", "emacs", 7]}))
    assert off_clients(home) == {"codex"}


def test_set_client_saves_and_reads_back(tmp_path):
    home = make_home(tmp_path, *ALL)
    assert set_client(home, "codex", False) == {"codex"}
    assert set_client(home, "cursor", False) == {"codex", "cursor"}
    assert json.loads(_file(home).read_text()) == {"off": ["codex", "cursor"]}
    assert (_file(home).stat().st_mode & 0o777) == 0o600
    assert set_client(home, "codex", True) == {"cursor"}
    assert off_clients(home) == {"cursor"}


def test_the_last_client_that_is_on_stays_on(tmp_path):
    home = make_home(tmp_path, *ALL)
    set_client(home, "codex", False)
    set_client(home, "cursor", False)
    with pytest.raises(ValueError, match=re.escape(choice.LAST_ON)):
        set_client(home, "claude_code", False)
    assert off_clients(home) == {"codex", "cursor"}


def test_an_unknown_client_is_refused(tmp_path):
    home = make_home(tmp_path, *ALL)
    with pytest.raises(ValueError, match="Unknown client"):
        set_client(home, "emacs", False)
    assert not _file(home).exists()


def test_default_adapters_leave_out_an_off_client(tmp_path):
    home = make_home(tmp_path, *ALL)
    set_client(home, "codex", False)
    assert [a.id for a in default_adapters(home)] == ["claude_code", "cursor"]


def test_an_off_client_is_not_detected_or_scanned(tmp_path, monkeypatch):
    from kitden.clients.codex import CodexAdapter

    home = make_home(tmp_path, *ALL)
    set_client(home, "codex", False)
    called = []
    for name in ("detect", "scan", "_run_plugin_list"):
        monkeypatch.setattr(
            CodexAdapter, name, lambda self, *a, _n=name, **k: called.append(_n) or None
        )
    inventory = build_inventory(home)
    assert called == []
    status = {c.id: c.status for c in inventory.clients}
    assert status["codex"] is ClientStatus.OFF
    assert status["claude_code"] is ClientStatus.FOUND
    assert not [i for i in inventory.items if i.client == "codex"]
    assert not [p for p in inventory.problems if p.owner_client == "codex"]
    assert all("codex" not in p.known_by for p in inventory.projects)
    assert "codex" not in {c for c, _ in inventory.plugin_skills}


def test_claude_code_off_drops_the_desktop_tab(tmp_path):
    from kitden.clients.claude_code import DESKTOP, DESKTOP_CONFIG
    from kitden.system import claude_desktop_dir

    home = make_home(tmp_path, *ALL)
    config = claude_desktop_dir(home) / DESKTOP_CONFIG
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"mcpServers": {}}')
    assert DESKTOP in {c.id for c in build_inventory(home).clients}
    set_client(home, "claude_code", False)
    assert DESKTOP not in {c.id for c in build_inventory(home).clients}


def test_a_not_installed_client_stays_not_found(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    set_client(home, "cursor", False)
    status = {c.id: c.status for c in build_inventory(home).clients}
    assert status["codex"] is ClientStatus.NOT_FOUND
    assert status["cursor"] is ClientStatus.OFF


@pytest.fixture
def page(tmp_path):
    home = make_home(tmp_path, *ALL)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        c.home = home
        yield c


def _post(page, client, on):
    return page.post("/api/clients/choice", json={"client": client, "on": on}, headers=POST)


def test_the_route_turns_a_client_off_and_on(page):
    answer = _post(page, "codex", False)
    assert answer.status_code == 200
    assert {c["id"]: c["status"] for c in answer.json()}["codex"] == "off"
    assert {c["id"]: c["status"] for c in page.get("/api/clients").json()}["codex"] == "off"
    assert not [i for i in page.get("/api/items").json() if i["client"] == "codex"]
    assert off_clients(page.home) == {"codex"}
    answer = _post(page, "codex", True)
    assert {c["id"]: c["status"] for c in answer.json()}["codex"] == "found"
    assert [i for i in page.get("/api/items").json() if i["client"] == "codex"]


@pytest.mark.parametrize(
    "body",
    [
        {"client": "emacs", "on": False},
        {"client": "codex"},
        {"client": "codex", "on": "no"},
        {"on": True},
        {},
    ],
)
def test_the_route_refuses_what_it_cannot_use(page, body):
    answer = page.post("/api/clients/choice", json=body, headers=POST)
    assert answer.status_code == 400
    assert answer.json()["detail"]
    assert off_clients(page.home) == frozenset()


def test_the_route_refuses_the_last_client_that_is_on(page):
    assert _post(page, "codex", False).status_code == 200
    assert _post(page, "cursor", False).status_code == 200
    answer = _post(page, "claude_code", False)
    assert answer.status_code == 400
    assert answer.json()["detail"] == "Keep at least one client on."


def test_the_route_needs_the_same_guards_as_other_posts(page):
    body = {"client": "codex", "on": False}
    assert page.post("/api/clients/choice", json=body).status_code in (400, 403)
    assert off_clients(page.home) == frozenset()


def test_the_route_needs_a_home(tmp_path):
    home = make_home(tmp_path, *ALL)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        answer = c.post("/api/clients/choice", json={"client": "codex", "on": False}, headers=POST)
        assert answer.status_code == 400


# Each view leaves an off client out and shows a not-installed one as it did.


@pytest.fixture
def off_page(page):
    assert _post(page, "codex", False).status_code == 200
    return page


def _ids(entries, key="id"):
    return [e[key] for e in entries]


def test_the_overview_map_and_lede_leave_an_off_client_out(off_page):
    overview = off_page.get("/api/overview").json()
    assert _ids(overview["map"]["clients"]) == ["claude_code", "cursor"]
    assert overview["counts"]["clients"] == 2
    assert not [link for link in overview["map"]["links"] if link["client"] == "codex"]


def test_the_library_map_leaves_an_off_client_out(off_page):
    answer = off_page.get("/api/library-map").json()
    assert _ids(answer["clients"]) == ["claude_code", "cursor"]
    assert "codex" not in {c for g in answer["groups"] for i in g["items"] for c in i["by"]}


def test_the_library_list_leaves_an_off_client_out(off_page):
    answer = off_page.get("/api/library-list").json()
    assert _ids(answer["columns"]) == ["claude_code", "cursor"]
    assert all("codex" not in row["cells"] for g in answer["groups"] for row in g["items"])


def test_the_gateway_view_leaves_an_off_client_out(off_page):
    view = off_page.get("/api/gateway-view").json()
    assert all("codex" not in columns for columns in view["connections"].values())
    assert all("codex" not in row["columns"] for g in view["groups"].values() for row in g)


def test_the_agents_page_leaves_an_off_client_out(off_page):
    assert _ids(off_page.get("/api/setup-server").json(), "client") == ["claude_code", "cursor"]


def test_the_instructions_map_and_context_leave_an_off_client_out(off_page):
    assert "codex" not in off_page.get("/api/instructions-map").text.lower()
    assert "codex" not in _ids(off_page.get("/api/context").json()["clients"], "client")


def test_the_clients_list_says_off(off_page):
    status = {c["id"]: c["status"] for c in off_page.get("/api/clients").json()}
    assert (status["claude_code"], status["codex"], status["cursor"]) == ("found", "off", "found")


def test_a_client_that_is_not_installed_keeps_its_place(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283")
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        before = c.get("/api/overview").json()["map"]["clients"]
        assert [(e["id"], e["on"]) for e in before] == [
            ("claude_code", True),
            ("codex", False),
            ("cursor", False),
        ]
        assert _post(c, "cursor", False).status_code == 200
        after = c.get("/api/overview").json()["map"]["clients"]
        assert [(e["id"], e["on"]) for e in after] == [("claude_code", True), ("codex", False)]


def _add(page, item_id, *clients):
    body = {
        "action": "mcp.add",
        "targets": [{"client": c} for c in clients],
        "params": {"item": item_id},
    }
    return page.post("/api/changes/preview", json=body, headers=POST)


def test_add_offers_follow_the_choice_at_once(page):
    """The page's own adapters follow the choice with no restart: nothing can target an off
    client, and an Add offer for it is gone."""
    github = next(
        i
        for i in page.get("/api/items?kind=mcp_server").json()
        if (i["client"], i["name"], i["scope"]) == ("claude_code", "github", "user")
    )

    def offers():
        rows = {r["name"]: r for r in page.get("/api/library?kind=mcp_server").json()["rows"]}
        return {c: cell["add"] for c, cell in rows["github"]["cells"].items()}

    assert offers()["codex"] is not None
    _post(page, "codex", False)
    assert "codex" not in offers()
    answer = _add(page, github["id"], "codex")
    assert answer.status_code == 422
    assert answer.json()["detail"] == "Codex is turned off in Kitden."
    assert "github" not in (page.home / ".codex/config.toml").read_text()
    _post(page, "codex", True)
    assert offers()["codex"] is not None
    assert _add(page, github["id"], "codex").status_code == 200


def test_no_restart_strip_for_an_off_client(tmp_path):
    from datetime import UTC, datetime, timedelta

    home = make_home(tmp_path, *ALL)
    long_ago = datetime.now(UTC) - timedelta(days=2)
    app = create_app(
        lambda: build_inventory(home),
        token="tok",
        port=47800,
        home=home,
        processes=lambda: [(long_ago, "codex"), (long_ago, "claude")],
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        entry = {
            "id": "c1",
            "time": datetime.now(UTC).isoformat(timespec="seconds"),
            "state": "verified",
            "steps": [
                {"client": "codex", "restart_note": "Restart Codex."},
                {"client": "claude_code", "restart_note": "Restart Claude Code."},
            ],
        }
        from kitden.changes.backup import ChangeStore

        ChangeStore(data_dir(home)).log(entry)
        assert {s["client"] for s in c.get("/api/restarts").json()} == {"claude_code", "codex"}
        _post(c, "codex", False)
        assert {s["client"] for s in c.get("/api/restarts").json()} == {"claude_code"}


def test_undo_of_a_change_to_an_off_client_waits_until_it_is_on(tmp_path):
    home = make_home(tmp_path, *ALL)
    write_cursor_fixture_state(home)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        neon = next(
            i
            for i in c.get("/api/items?client=cursor&kind=mcp_server").json()
            if i["name"] == "Neon"
        )
        body = {"action": "mcp.remove_direct", "targets": [{"item": neon["id"]}], "params": {}}
        change = c.post("/api/changes/preview", json=body, headers=POST).json()
        assert c.post(f"/api/changes/{change['id']}/apply", headers=POST).status_code == 200
        config = home / ".cursor/mcp.json"
        removed = config.read_bytes()

        assert _post(c, "cursor", False).status_code == 200
        # The change stays in the list.
        assert change["id"] in [e["id"] for e in c.get("/api/changes").json()]
        answer = c.post(f"/api/changes/{change['id']}/undo", headers=POST)
        assert answer.status_code == 422
        assert answer.json()["detail"] == "Turn Cursor on to undo this."
        assert config.read_bytes() == removed  # nothing was written

        assert _post(c, "cursor", True).status_code == 200
        answer = c.post(f"/api/changes/{change['id']}/undo", headers=POST)
        assert answer.status_code == 200
        assert answer.json()["state"] == "undone"
        assert config.read_bytes() != removed


def test_a_preview_made_before_a_client_was_turned_off_is_not_applied(tmp_path):
    home = make_home(tmp_path, *ALL)
    write_cursor_fixture_state(home)
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        neon = next(
            i
            for i in c.get("/api/items?client=cursor&kind=mcp_server").json()
            if i["name"] == "Neon"
        )
        body = {"action": "mcp.remove_direct", "targets": [{"item": neon["id"]}], "params": {}}
        change = c.post("/api/changes/preview", json=body, headers=POST).json()
        config = home / ".cursor/mcp.json"
        before = config.read_bytes()

        assert _post(c, "cursor", False).status_code == 200
        answer = c.post(f"/api/changes/{change['id']}/apply", headers=POST)
        assert answer.status_code == 422
        assert answer.json()["detail"] == "Turn Cursor on to apply this."
        assert config.read_bytes() == before  # nothing was written


# `kitden scan` and `kitden show`


def test_scan_says_a_client_is_turned_off(tmp_path, capsys):
    from kitden.cli import main

    home = make_home(tmp_path, *ALL)
    write_cursor_fixture_state(home)
    set_client(home, "codex", False)
    assert main(["scan", "--home", str(home)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "Codex: turned off in Kitden" in lines
    # The line has no version and no items under it, and the others are read as before.
    at = lines.index("Codex: turned off in Kitden")
    assert not lines[at + 1].startswith("  ")
    assert any(line.startswith("Cursor ") for line in lines)
    assert any(line.startswith("Claude Code ") for line in lines)


def test_an_off_client_keeps_its_place_in_the_list(tmp_path):
    home = make_home(tmp_path, *ALL)
    write_cursor_fixture_state(home)
    set_client(home, "codex", False)
    listed = [
        c.id for c in build_inventory(home).clients if c.id in ("claude_code", "codex", "cursor")
    ]
    assert listed == ["claude_code", "codex", "cursor"]
    # Adapters passed in follow the choice too, as the demo's do.
    passed = build_inventory(home, default_adapters(home), [])
    assert {c.id: c.status for c in passed.clients}["codex"] is ClientStatus.OFF


def test_scan_json_lists_an_off_client_with_status_off(tmp_path, capsys):
    from kitden.cli import main

    home = make_home(tmp_path, *ALL)
    set_client(home, "codex", False)
    assert main(["scan", "--json", "--home", str(home)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert {c["id"]: c["status"] for c in data["clients"]}["codex"] == "off"
    assert not [i for i in data["items"] if i["client"] == "codex"]


def test_scan_does_not_ask_an_off_client_for_its_version(tmp_path, monkeypatch, capsys):
    from kitden.cli import main
    from kitden.clients import version_cache

    home = make_home(tmp_path, *ALL)
    set_client(home, "codex", False)
    asked = []
    monkeypatch.setattr(
        version_cache, "version_command", lambda client: asked.append(client) or None
    )
    main(["scan", "--json", "--home", str(home)])
    assert "codex" not in asked
    assert "claude_code" in asked


def test_show_setup_names_an_off_client(tmp_path, capsys):
    from kitden.cli import main

    home = make_home(tmp_path, *ALL)
    set_client(home, "codex", False)
    assert main(["show", "setup", "--client", "codex", "--home", str(home)]) == 2
    out = capsys.readouterr()
    assert "Codex is turned off in Kitden." in out.err
    assert "Unknown or missing" not in out.err
    assert main(["show", "setup", "--client", "nope", "--home", str(home)]) == 2
    assert "Unknown or missing client: nope" in capsys.readouterr().err


def test_the_first_scan_has_no_step_for_an_off_client(tmp_path):
    import time

    home = make_home(tmp_path, *ALL)
    set_client(home, "codex", False)
    app = create_app(
        lambda **options: build_inventory(home, **options),
        token="tok",
        port=47800,
        home=home,
        first_scan_later=True,
        quick_first=True,
        version_refresh=dict,
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        c.get("/?token=tok")
        for _ in range(100):
            view = c.get("/api/progress").json()
            if view["ready"] and all(s["done"] for s in view["steps"]):
                break
            time.sleep(0.05)
        names = [s["name"] for s in view["steps"]]
        assert "Codex" not in names
        assert "Codex plugins" not in names
        assert {"Claude Code", "Cursor"} <= set(names)
