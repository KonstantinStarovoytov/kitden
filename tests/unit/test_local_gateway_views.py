"""The Kitden gateway on the page: held servers, the gateway card, tool rules and refreshes."""

import asyncio
import json
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import kitden.clients.base as base
import kitden.web.app as page_app
from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE, load_settings, load_tools, save_tools
from kitden.local_gateway.views import gateway_items, refresh_tools
from kitden.views.gateway_view import gateway_view
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

KITDEN = "/opt/kitden/bin/kitden"
FILES = {"command": "npx", "args": ["files-mcp"], "env": {"FILES_TOKEN": "SENTINEL_SECRET_FILES"}}
ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
ECHO = Path(__file__).parents[1] / "fixtures/fake_mcp/echo_server.py"
ECHO_TOOLS = ["clash", "echo", "refuse", "slow", "where"]
WAIT = 30  # seconds a background refresh may take in a test


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


@pytest.fixture
def home(tmp_path):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def echo(*more):
    return {"command": sys.executable, "args": [str(ECHO), "echo", *more]}


def hold(home, servers, rules=None):
    """Write the gateway settings as a verified move would leave them."""
    path = data_dir(home) / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"servers": servers, "rules": rules or {}}, indent=2))


def add_entry(home, client, name, entry):
    path = home / (".claude.json" if client == "claude_code" else ".cursor/mcp.json")
    data = json.loads(path.read_text())
    data.setdefault("mcpServers", {})[name] = entry
    path.write_text(json.dumps(data, indent=2))


def add_kitden(home, *clients):
    for client in clients:
        entry = {"command": KITDEN, "args": ["mcp"]}
        add_entry(
            home, client, "kitden", {"type": "stdio", **entry} if client == "claude_code" else entry
        )


def tool(name):
    return {"name": name, "description": f"The {name} tool", "inputSchema": {"type": "object"}}


def project(home, name):
    return str(home / "work" / name)


@contextmanager
def page_for(home, build=None, **options):
    """The local page on `home`, as `kitden open` serves it."""
    app = create_app(
        build or (lambda: build_inventory(home)),
        token="tok",
        port=47800,
        home=home,
        setup_command=lambda: KITDEN,
        **options,
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        yield page


def project_id(page, path):
    return next(p["id"] for p in page.get("/api/projects").json() if p["path"] == path)


def until(check, seconds=WAIT):
    deadline = time.monotonic() + seconds
    while not check():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.1)


def test_held_servers_show_via_kitden_gateway_in_connected_clients(home):
    hold(home, {"files": FILES})
    add_kitden(home, "claude_code", "cursor")  # Codex has no `kitden` entry

    items = gateway_items(build_inventory(home), load_settings(home), home)
    assert [(i.client, i.name, i.via_gateway) for i in items] == [
        ("claude_code", "files", "kitden"),
        ("cursor", "files", "kitden"),
    ]
    source = items[0].source
    assert (source.path, source.key_path) == (str(data_dir(home) / SETTINGS_FILE), "servers.files")

    with page_for(home) as page:
        library = page.get("/api/library?kind=mcp_server")
        row = next(r for r in library.json()["rows"] if r["name"] == "files")
        cells = {c: (cell["state"], cell["where"]) for c, cell in row["cells"].items()}
        assert cells == {
            "claude_code": ("gw", "Kitden gateway"),
            "codex": ("none", None),
            "cursor": ("gw", "Kitden gateway"),
        }
        # Codex reaches it once it has the `kitden` entry: the Gateway page sets that up.
        assert row["cells"]["codex"]["reason"] == (
            "Set up the Kitden gateway in Codex on the Gateway page."
        )
        assert "SENTINEL_SECRET_FILES" not in library.text
        assert "SENTINEL_SECRET_FILES" not in page.get("/api/items").text


def test_the_kitden_gateway_is_listed_and_local_servers_can_move(home):
    hold(home, {"files": FILES})
    add_kitden(home, "cursor")

    def row(view, group, name):
        return next(r for r in view["groups"][group] if r["name"] == name)

    with page_for(home) as page:
        view = page.get("/api/gateway-view").json()
    assert view["gateways"][0] == {
        "id": "kitden",
        "kind": "kitden",
        "name": "Kitden gateway",
        "where": "On this Mac",
        "movable": True,
        "servers": [{"name": "files", "kind": "local", "state": "on", "differs": False}],
    }
    assert view["connections"]["kitden"] == {"claude_code": [], "codex": [], "cursor": ["files"]}
    assert view["used"] == ["kitden"]
    local = row(view, "local", "n8n-mcp")
    assert local["movable"] is True
    assert local["items"]
    assert row(view, "move", "Neon")["movable"] is True

    # Without the Kitden gateway and with no gateway that takes servers, nothing can move.
    alone = gateway_view(build_inventory(home), [], None)
    assert alone["gateways"] == []
    assert row(alone, "local", "n8n-mcp")["movable"] is False
    assert row(alone, "move", "Neon")["movable"] is False


def test_the_kitden_card_lists_every_held_server_with_its_state_in_the_project(home):
    website = project(home, "website")
    docs = {"url": "https://docs.example.com/mcp"}
    # No client has the `kitden` entry, and files is off everywhere but website: the card still
    # lists both, so they can be found and switched.
    rules = {
        "global": {"files": {"server": "off"}},
        "projects": {website: {"files": {"server": "on"}}},
    }
    hold(home, {"files": FILES, "docs": docs}, rules)

    with page_for(home) as page:
        everywhere = page.get("/api/gateway-view").json()["gateways"][0]["servers"]
        there = page.get(f"/api/gateway-view?project={project_id(page, website)}").json()
    assert everywhere == [
        {"name": "docs", "kind": "remote", "state": "on", "differs": False},
        {"name": "files", "kind": "local", "state": "off", "differs": False},
    ]
    assert there["gateways"][0]["servers"][1] == {
        "name": "files",
        "kind": "local",
        "state": "on",
        "differs": True,
    }
    assert "SENTINEL_SECRET_FILES" not in json.dumps(there)


def test_tools_api_marks_project_differences(home):
    website, api = project(home, "website"), project(home, "api")
    rules = {
        "global": {"echo": {"tools": {"slow": "off"}}},
        "projects": {
            website: {"echo": {"server": "off", "tools": {"slow": "off", "clash": "off"}}},
            # A rule removed with "Follows all projects" leaves an empty object behind.
            api: {"echo": {"tools": {}}},
        },
    }
    hold(home, {"echo": echo()}, rules)
    save_tools(home, "echo", [tool("echo"), tool("slow"), tool("clash")])

    def rows(answer):
        return [(t["name"], t["state"], t["differs"]) for t in answer["tools"]]

    with page_for(home) as page:
        everywhere = page.get("/api/gateway/tools?server=echo").json()
        assert {k: everywhere[k] for k in ("server", "state", "differs", "problem")} == {
            "server": "echo",
            "state": "on",
            "differs": False,
            "problem": None,
        }
        assert everywhere["tools"][0] == {
            "name": "echo",
            "description": "The echo tool",
            "state": "on",
            "differs": False,
        }
        assert rows(everywhere) == [
            ("echo", "on", False),
            ("slow", "off", False),
            ("clash", "on", False),
        ]

        there = page.get(f"/api/gateway/tools?server=echo&project={project_id(page, website)}")
        assert (there.json()["state"], there.json()["differs"]) == ("off", True)
        # slow is off there as it is everywhere, so it does not differ.
        assert rows(there.json()) == [
            ("echo", "on", False),
            ("slow", "off", False),
            ("clash", "off", True),
        ]

        empty = page.get(f"/api/gateway/tools?server=echo&project={project_id(page, api)}").json()
        assert (empty["state"], empty["differs"]) == ("on", False)
        assert rows(empty) == rows(everywhere)

        assert page.get("/api/gateway/tools?server=nope").status_code == 404
        assert page.get("/api/gateway/tools?server=echo&project=nope").status_code == 404


def test_a_rule_change_previews_applies_and_undoes(home):
    website = project(home, "website")
    hold(home, {"echo": echo()})
    save_tools(home, "echo", [tool("echo"), tool("slow")])
    add_kitden(home, "cursor")
    path = data_dir(home) / SETTINGS_FILE
    before = path.read_bytes()

    def preview(page, **params):
        body = {"action": "gateway.rule", "params": params}
        return page.post("/api/changes/preview", json=body, headers=POST)

    with page_for(home) as page:
        pid = project_id(page, website)
        answer = preview(page, server="echo", tool="slow", state="off", project=pid)
        assert answer.status_code == 200, answer.json()
        change = answer.json()
        assert change["action"] == "gateway.rule"
        assert [(s["client"], s["name"]) for s in change["steps"]] == [("kitden", "slow")]
        assert change["after"] == [
            {
                "client": "cursor",
                "state": "off",
                "word": "Off",
                "note": "slow of echo will be off in website. Applies to new sessions.",
            }
        ]
        assert path.read_bytes() == before  # a preview writes nothing

        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified", applied
        rules = load_settings(home)["rules"]
        assert rules["projects"] == {website: {"echo": {"tools": {"slow": "off"}}}}
        assert rules["global"] == {}
        tools = page.get(f"/api/gateway/tools?server=echo&project={pid}").json()["tools"]
        assert [(t["name"], t["state"], t["differs"]) for t in tools] == [
            ("echo", "on", False),
            ("slow", "off", True),
        ]
        again = preview(page, server="echo", tool="slow", state="off", project=pid)
        assert again.status_code == 422
        assert again.json()["detail"] == "The Kitden gateway has this already. Nothing to change."

        # Back to what all projects use: the review says what that is.
        follow = preview(page, server="echo", tool="slow", state=None, project=pid).json()
        assert follow["after"][0]["word"] == "Follows all projects"
        assert follow["after"][0]["state"] == "on"
        assert follow["after"][0]["note"] == (
            "slow of echo will be on in website, as in all projects. Applies to new sessions."
        )
        page.post(f"/api/changes/{follow['id']}/cancel", headers=POST)

        # The whole server, for all projects.
        server = preview(page, server="echo", tool=None, state="off", project=None).json()
        assert [(s["client"], s["name"]) for s in server["steps"]] == [("kitden", "echo")]
        assert server["after"][0]["word"] == "Off"
        assert server["after"][0]["note"] == (
            "echo will be off in all projects. Applies to new sessions."
        )
        page.post(f"/api/changes/{server['id']}/cancel", headers=POST)

        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone", undone
        assert path.read_bytes() == before

        for params, words in (
            (
                {"server": "nope", "tool": None, "state": "off"},
                "Choose a server in the Kitden gateway.",
            ),
            ({"server": "echo", "tool": "nope", "state": "off"}, "Choose a tool of this server."),
            ({"server": "echo", "tool": "slow", "state": "maybe"}, "A rule is on or off"),
            ({"server": "echo", "tool": "slow", "state": None}, "Choose on or off."),
            (
                {"server": "echo", "tool": "slow", "state": "off", "project": "nope"},
                "Unknown project.",
            ),
        ):
            refused = preview(page, **params)
            assert refused.status_code == 422
            assert refused.json()["detail"] == words
        assert path.read_bytes() == before


def rule_preview(page, **params):
    body = {"action": "gateway.rule", "params": params}
    return page.post("/api/changes/preview", json=body, headers=POST)


def test_a_rule_for_a_tool_the_server_lost_can_follow_all_projects(home):
    website = project(home, "website")
    hold(home, {"echo": echo()}, {"projects": {website: {"echo": {"tools": {"gone": "off"}}}}})
    save_tools(home, "echo", [tool("echo")])
    add_kitden(home, "cursor")
    with page_for(home) as page:
        pid = project_id(page, website)
        reset = rule_preview(page, server="echo", tool="gone", state=None, project=pid)
        assert reset.status_code == 200, reset.json()
        assert reset.json()["after"][0]["word"] == "Follows all projects"
        again = rule_preview(page, server="echo", tool="gone", state="off", project=pid)
        assert again.json()["detail"] == "Choose a tool of this server."


def test_a_rule_review_says_when_no_client_uses_the_gateway(home):
    hold(home, {"echo": echo()})
    save_tools(home, "echo", [tool("slow")])
    with page_for(home) as page:
        pid = project_id(page, project(home, "website"))
        change = rule_preview(page, server="echo", tool="slow", state="off", project=pid).json()
    assert change["after"] == [
        {"note": "slow of echo will be off in website. No client uses the Kitden gateway yet."}
    ]


def test_the_library_follows_the_server_rules(home):
    website = project(home, "website")
    # Moved from Claude Code's local scope: off for all projects, on in its project.
    rules = {
        "global": {"held": {"server": "off"}},
        "projects": {website: {"held": {"server": "on"}}},
    }
    hold(home, {"held": echo()}, rules)
    add_kitden(home, "claude_code", "cursor")
    codex = home / ".codex/config.toml"
    codex.write_text(
        codex.read_text() + f'\n[mcp_servers.kitden]\ncommand = "{KITDEN}"\nenabled = false\n'
    )

    def cells(page, query=""):
        rows = page.get(f"/api/library?kind=mcp_server{query}").json()["rows"]
        row = next(r for r in rows if r["name"] == "held")
        return {c: (cell["state"], cell["where"]) for c, cell in row["cells"].items()}

    with page_for(home) as page:
        pid = project_id(page, website)
        assert cells(page) == {
            c: ("off", "Kitden gateway") for c in ("claude_code", "codex", "cursor")
        }
        # Codex's own `kitden` entry is off, so it stays off there.
        assert cells(page, f"&project={pid}") == {
            "claude_code": ("gw", "Kitden gateway"),
            "codex": ("off", "Kitden gateway"),
            "cursor": ("gw", "Kitden gateway"),
        }
        findings = page.get(f"/api/findings?project={pid}").json()
        assert not [f for f in findings if "held" in f["names"]]


def test_a_carried_codex_off_reads_off(home):
    command, args = json.dumps(sys.executable), json.dumps([str(ECHO), "echo"])
    codex = home / ".codex/config.toml"
    codex.write_text(
        codex.read_text() + f"\n[mcp_servers.echo]\ncommand = {command}\nargs = {args}\n"
        "enabled = false\n"
    )
    with page_for(home) as page:
        items = page.get("/api/items?client=codex&kind=mcp_server").json()
        body = {
            "action": "gateway.move",
            "targets": [{"item": next(i["id"] for i in items if i["name"] == "echo")}],
            "params": {"gateway": "kitden"},
        }
        change = page.post("/api/changes/preview", json=body, headers=POST).json()
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified", applied
        rows = page.get("/api/library?kind=mcp_server").json()["rows"]
        cell = next(r for r in rows if r["name"] == "echo")["cells"]["codex"]
        assert (cell["state"], cell["where"]) == ("off", "Kitden gateway")


def test_watcher_rescans_never_start_servers(home, monkeypatch):
    mark = home / "started"
    hold(home, {"echo": echo("--mark", str(mark))})
    asked = []
    refresh = page_app.refresh_tools

    async def counted(*args, **kwargs):
        asked.append(args)
        return await refresh(*args, **kwargs)

    monkeypatch.setattr(page_app, "refresh_tools", counted)
    builds = []

    def build():
        builds.append(1)
        return build_inventory(home)

    config = home / ".cursor/mcp.json"
    time.sleep(1)
    with page_for(home, build, watch_folders=[home / ".cursor"], debounce_ms=100) as page:
        time.sleep(0.5)
        config.write_text(config.read_text())
        until(lambda: len(builds) >= 2)
        time.sleep(1)
        assert asked == []
        assert not mark.exists()
        assert "echo" not in load_tools(home)

        # The Rescan button lists each held server, in the background.
        assert page.post("/api/rescan", headers=POST).status_code == 200
        until(lambda: "echo" in load_tools(home))
        assert mark.exists()
        assert len(asked) == 1


def test_a_verified_move_refreshes_the_tool_list(home):
    add_entry(home, "cursor", "echo", echo())
    with page_for(home) as page:
        item = next(
            i["id"]
            for i in page.get("/api/items?client=cursor&kind=mcp_server").json()
            if i["name"] == "echo"
        )
        body = {
            "action": "gateway.move",
            "targets": [{"item": item}],
            "params": {"gateway": "kitden"},
        }
        change = page.post("/api/changes/preview", json=body, headers=POST).json()
        assert "echo" not in load_tools(home)
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified", applied
        until(lambda: "echo" in load_tools(home))
        assert sorted(t["name"] for t in load_tools(home)["echo"]) == ECHO_TOOLS
        tools = page.get("/api/gateway/tools?server=echo").json()["tools"]
        assert sorted(t["name"] for t in tools) == ECHO_TOOLS


def test_a_failed_refresh_keeps_the_old_list_and_says_why(home):
    hold(home, {"broken": {"command": str(home / "no-such-server")}, "echo": echo()})
    save_tools(home, "broken", [tool("old")])

    with page_for(home) as page:
        answer = page.post("/api/gateway/tools/refresh", headers=POST)
        assert answer.status_code == 202
        until(lambda: page.get("/api/gateway/tools?server=broken").json()["problem"])
        broken = page.get("/api/gateway/tools?server=broken").json()
        assert broken["problem"] == "Kitden could not start broken."
        assert [t["name"] for t in broken["tools"]] == ["old"]
        assert sorted(t["name"] for t in load_tools(home)["echo"]) == ECHO_TOOLS
        assert page.get("/api/gateway/tools?server=echo").json()["problem"] is None


def test_one_server_that_breaks_does_not_stop_the_others(home, monkeypatch):
    from kitden.local_gateway import proxy

    hold(home, {"first": echo(), "second": echo()})

    class Breaks(proxy.Upstreams):
        """Closing fails after listing the first server."""

        async def list_tools(self, server):
            self.server = server
            return await super().list_tools(server)

        async def __aexit__(self, *exc_info):
            await super().__aexit__(*exc_info)
            if self.server == "first":
                raise RuntimeError("closing failed")

    monkeypatch.setattr(proxy, "Upstreams", Breaks)
    found = asyncio.run(refresh_tools(home))
    assert found == {"first": "first did not list its tools.", "second": None}
    assert "first" not in load_tools(home)
    assert sorted(t["name"] for t in load_tools(home)["second"]) == ECHO_TOOLS


def test_the_page_hears_when_a_refresh_ends_even_after_a_failure(home, monkeypatch):
    async def fails(*args):
        raise RuntimeError("broken")

    monkeypatch.setattr(page_app, "refresh_tools", fails)
    with page_for(home) as page:
        queue = page.app.state.events.subscribe()
        page.post("/api/gateway/tools/refresh", headers=POST)
        until(lambda: not queue.empty())
        assert queue.get_nowait() == "gateway_tools"


def test_a_refresh_asked_while_one_waits_is_not_queued_again(home, monkeypatch):
    started, release = threading.Event(), threading.Event()
    calls = []

    async def slow(home, names=None):
        calls.append(names)
        started.set()
        await asyncio.to_thread(release.wait, WAIT)
        return {}

    monkeypatch.setattr(page_app, "refresh_tools", slow)
    with page_for(home) as page:
        page.post("/api/gateway/tools/refresh", headers=POST)
        assert started.wait(WAIT)
        for _ in range(3):  # the first waits; the other two join it
            page.post("/api/gateway/tools/refresh", headers=POST)
        release.set()
        until(lambda: len(calls) == 2)
        time.sleep(0.3)
        assert calls == [None, None]
