"""The Kitden gateway on the page: held servers, the gateway card, tool rules and refreshes."""

import asyncio
import json
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import anyio
import pytest
from mcp import Client
from starlette.testclient import TestClient

import kitden.web.app as page_app
from kitden import mcp_server
from kitden.changes.json_splice import ABSENT
from kitden.gateways import data_dir
from kitden.local_gateway import proxy
from kitden.local_gateway.settings import (
    SETTINGS_FILE,
    allowed_tools,
    load_settings,
    load_tools,
    save_tools,
)
from kitden.local_gateway.views import (
    gateway_items,
    held_servers,
    refresh_tools,
    rules_steps,
    strict_steps,
    tool_hint,
    tools_view,
)
from kitden.views.gateway_view import gateway_view
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

AT_ONCE = (
    "A tool turned off is refused at once; a call already running is not stopped. The client "
    "shows the new list in a new session."
)
KITDEN = "/opt/kitden/bin/kitden"
FILES = {"command": "npx", "args": ["files-mcp"], "env": {"FILES_TOKEN": "SENTINEL_SECRET_FILES"}}
ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
ECHO = Path(__file__).parents[1] / "fixtures/fake_mcp/echo_server.py"
ECHO_TOOLS = ["clash", "echo", "refuse", "slow", "where"]
WAIT = 30  # seconds a background refresh may take in a test


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
        cells = {c: (cell["state"], cell["route"]) for c, cell in row["cells"].items()}
        assert cells == {
            "claude_code": ("gw", "through the Kitden gateway"),
            "codex": ("none", None),
            "cursor": ("gw", "through the Kitden gateway"),
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
        "servers": [
            {
                "name": "files",
                "kind": "local",
                "state": "on",
                "differs": False,
                "origin": "default",
                "origin_from": None,
                "plain_secrets": True,
                "tools": None,
                "tool_list": [],
                "on_count": 0,
                "on_in": 0,
                "on_elsewhere": 0,
                "projects": 0,
            }
        ],
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
    save_tools(home, "docs", [tool("search"), tool("read")])

    with page_for(home) as page:
        everywhere = page.get("/api/gateway-view").json()["gateways"][0]["servers"]
        there = page.get(f"/api/gateway-view?project={project_id(page, website)}").json()
    listed = [
        {
            "name": name,
            "title": None,
            "state": "on",
            "effective": "on",
            "hint": "unknown",
            "origin": "default",
            "origin_from": None,
            "own_in": 0,
        }
        for name in ("search", "read")
    ]
    assert everywhere == [
        {
            "name": "docs",
            "kind": "remote",
            "state": "on",
            "differs": False,
            "origin": "default",
            "origin_from": None,
            "plain_secrets": False,
            "tools": 2,
            "tool_list": listed,
            "on_count": 2,
            "on_in": 0,
            "on_elsewhere": 0,
            "projects": 0,
        },
        {
            "name": "files",
            "kind": "local",
            "state": "off",
            "differs": False,
            "origin": "global",
            "origin_from": None,
            "plain_secrets": True,
            "tools": None,
            "tool_list": [],
            "on_count": 0,
            "on_in": 1,  # website turns it on
            "on_elsewhere": 0,
            "projects": 1,
        },
    ]
    assert there["gateways"][0]["servers"][1] == {
        "name": "files",
        "kind": "local",
        "state": "on",
        "differs": True,
        "origin": "project",
        "origin_from": None,
        "plain_secrets": True,
        "tools": None,
        "tool_list": [],
        "on_count": 0,
        "on_in": 0,
        "on_elsewhere": 0,
        "projects": 1,
    }
    assert "SENTINEL_SECRET_FILES" not in json.dumps(there)


SETTINGS = {
    "servers": {"github": {"url": "https://example.com/mcp"}, "notion": {"command": "notion"}},
    "rules": {"global": {}, "projects": {}},
}


def test_held_rows_count_known_tools():
    rows = held_servers(SETTINGS, [], {"github": [tool("a"), tool("b")]})
    assert {r["name"]: r["tools"] for r in rows} == {"github": 2, "notion": None}


def test_held_tools_count_the_projects_with_their_own_rule():
    # The map tags a tool with how many known projects have a rule of their own for it. A rule
    # for the whole server, or in a folder Kitden does not know, is not one.
    settings = {
        "servers": {"files": {"command": "files"}},
        "rules": {
            "global": {"files": {"tools": {"read_file": "off"}}},
            "projects": {
                "/w/a": {"files": {"tools": {"read_file": "on"}}},
                "/w/b": {"files": {"tools": {"read_file": "off"}}},
                "/w/c": {"files": {"server": "on"}},
                "/w/gone": {"files": {"tools": {"read_file": "on", "write_file": "on"}}},
            },
        },
    }
    chains = {path: [path] for path in ("/w/a", "/w/b", "/w/c")}
    tools = {"files": [tool("read_file"), tool("write_file")]}
    for chain in ([], ["/w/a"]):
        listed = held_servers(settings, chain, tools, chains)[0]["tool_list"]
        assert {t["name"]: t["own_in"] for t in listed} == {"read_file": 2, "write_file": 0}
    assert held_servers(settings, [], tools)[0]["tool_list"][0]["own_in"] == 0


def test_tools_view_names_the_tools_each_project_has_its_own_rule_for():
    # The tool panel lists the projects with a rule of their own for a tool, as the map counts
    # them (own_in): a folder that only follows its parent's rule, or a rule for the whole
    # server, is not one. The page knows each project by its id; the rules by its folder.
    settings = {
        "servers": {"files": {"command": "files"}},
        "rules": {
            "global": {"files": {"tools": {"read_file": "off"}}},
            "projects": {
                "/w/a": {"files": {"tools": {"read_file": "on"}}},
                "/w/b": {"files": {"tools": {"read_file": "off"}}},
                "/w/c": {"files": {"server": "on"}},
            },
        },
    }
    chains = {
        "a": ["/w/a"],
        "web": ["/w/a/web", "/w/a"],
        "b": ["/w/b"],
        "c": ["/w/c"],
        "none": [],
    }
    tools = {"files": [tool("read_file"), tool("write_file")]}
    view = tools_view(settings, tools, "files", [], chains=chains)
    assert {p["id"]: (p["tools"]["read_file"], p["own"]) for p in view["projects"]} == {
        "a": ("on", ["read_file"]),
        "web": ("on", []),
        "b": ("off", ["read_file"]),
        "c": ("off", []),
        "none": ("off", []),
    }


def test_an_empty_tool_list_shows_no_count():
    assert held_servers(SETTINGS, [], {"github": []})[0]["tools"] is None


def test_details_count_tools_only_for_servers_in_the_kitden_gateway(home):
    hold(home, {"files": FILES})
    add_kitden(home, "cursor")
    # Neon is a direct server: a name in the cache says nothing about it.
    save_tools(home, "files", [tool("read"), tool("write"), tool("list")])
    save_tools(home, "Neon", [tool("query")])

    with page_for(home) as page:
        files = page.get("/api/explain?name=files&kind=mcp_server").json()["definitions"]
        neon = page.get("/api/explain?name=Neon&kind=mcp_server").json()["definitions"]
    assert files and {d["tools"] for d in files} == {3}
    assert neon and {d["tools"] for d in neon} == {None}


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
            "title": None,
            "description": "The echo tool",
            "calls": None,
            "new": False,
            "state": "on",
            "differs": False,
            "follows": None,
            "origin": "default",
            "origin_from": None,
            "effective": "on",
            "hint": "unknown",
            "hint_from": None,
            "shared": "on",
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
                "note": "slow of echo will be off in website. " + AT_ONCE,
            }
        ]
        assert path.read_bytes() == before  # a preview writes nothing

        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified", applied
        # The Changes page names the rule's parts; the log keeps no values.
        logged = [e for e in page.get("/api/changes").json() if e["id"] == change["id"]]
        assert logged[0]["rule"] == {
            "project": "website",
            "server": "echo",
            "tool": "slow",
            "state": "off",
        }
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
            "slow of echo will be on in website, as in all projects. " + AT_ONCE
        )
        page.post(f"/api/changes/{follow['id']}/cancel", headers=POST)

        # The whole server, for all projects.
        server = preview(page, server="echo", tool=None, state="off", project=None).json()
        assert [(s["client"], s["name"]) for s in server["steps"]] == [("kitden", "echo")]
        assert server["after"][0]["word"] == "Off"
        assert server["after"][0]["note"] == ("echo will be off in all projects. " + AT_ONCE)
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


def test_a_rule_line_with_a_broken_record_stays_as_it_is(home):
    hold(home, {"echo": echo()})
    save_tools(home, "echo", [tool("echo"), tool("slow")])
    with page_for(home) as page:
        change = rule_preview(page, server="echo", tool="slow", state="off", project=None).json()
        assert page.post(f"/api/changes/{change['id']}/apply", headers=POST).status_code == 200
    record = data_dir(home) / "changes" / change["id"] / "change.json"
    for key in (["rules"], ["rules", "global", "echo"], ["rules", "global", "echo", "mode"]):
        saved = json.loads(record.read_text())
        saved["steps"][0]["edit"]["key"] = key
        record.write_text(json.dumps(saved))
        with page_for(home) as page:
            answer = page.get("/api/changes")
            assert answer.status_code == 200
            line = next(e for e in answer.json() if e["id"] == change["id"])
            assert "rule" not in line


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
        return {c: (cell["state"], cell["route"]) for c, cell in row["cells"].items()}

    with page_for(home) as page:
        pid = project_id(page, website)
        assert cells(page) == {
            c: ("off", "through the Kitden gateway") for c in ("claude_code", "codex", "cursor")
        }
        # Codex's own `kitden` entry is off, so it stays off there.
        assert cells(page, f"&project={pid}") == {
            "claude_code": ("gw", "through the Kitden gateway"),
            "codex": ("off", "through the Kitden gateway"),
            "cursor": ("gw", "through the Kitden gateway"),
        }
        findings = page.get("/api/findings", params={"project": website}).json()
        assert findings and not [f for f in findings if "held" in f["names"]]


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
        assert (cell["state"], cell["route"]) == ("off", "through the Kitden gateway")


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


READ_ONLY = {"show_setup", "list_findings", "explain_item", "list_projects"}


def know(home, *folders):
    """Claude Code knows these folders as projects."""
    path = home / ".claude.json"
    data = json.loads(path.read_text())
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        data["projects"][str(folder)] = {}
    path.write_text(json.dumps(data, indent=2))


def worktree_of(main, folder):
    """`folder` becomes a git worktree of `main`."""
    (main / ".git" / "worktrees" / folder.name).mkdir(parents=True)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".git").write_text(f"gitdir: {main}/.git/worktrees/{folder.name}\n")
    return folder


def chain_home(home):
    """website is a git repo; Claude Code knows its worktree website-wt and its subfolder web;
    website-fix is a worktree no client knows."""
    repo = home / "work/website"
    (repo / ".git").mkdir(parents=True)
    wt = worktree_of(repo, home / "work/website-wt")
    fix = worktree_of(repo, home / "work/website-fix")
    sub = repo / "packages/web"
    know(home, wt, sub)
    return repo, wt, fix, sub


def offered_in(home, folder, monkeypatch):
    """The upstream tools the Kitden gateway offers in a Claude Code session in `folder`."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(folder))
    known = mcp_server.known_projects(home)

    async def session():
        own = mcp_server.create_server(lambda: None)
        server = proxy.gateway_server(home, own, known=lambda: known)
        async with Client(server, mode="legacy") as client:
            return {t.name for t in (await client.list_tools()).tools}

    return anyio.run(session) - READ_ONLY


def test_rules_follow_enclosing_projects_on_the_page_and_in_the_gateway(home, monkeypatch):
    repo, wt, fix, sub = chain_home(home)
    rules = {
        "global": {},
        "projects": {
            str(repo): {"echo": {"tools": {"slow": "off"}}},
            str(wt): {"echo": {"tools": {"clash": "off"}}},
            str(sub): {"echo": {"tools": {"slow": "on", "where": "off"}}},
        },
    }
    hold(home, {"echo": echo()}, rules)
    save_tools(home, "echo", [tool(name) for name in ("echo", "slow", "clash", "where")])

    expected = {
        repo: {"echo", "clash", "where"},
        # A rule under a worktree's own key applies there, and so does its main checkout's.
        wt: {"echo", "where"},
        # A worktree no client knows gets its main checkout's rules.
        fix: {"echo", "clash", "where"},
        # A known subfolder keeps its parent's rule unless it has its own.
        sub: {"echo", "slow", "clash"},
    }
    for folder, tools in expected.items():
        assert offered_in(home, folder, monkeypatch) == tools, folder

    def states(page, folder):
        pid = project_id(page, str(folder))
        answer = page.get(f"/api/gateway/tools?server=echo&project={pid}").json()
        return {t["name"]: (t["state"], t["differs"]) for t in answer["tools"]}

    with page_for(home) as page:
        for folder in (repo, wt, sub):
            on = {name for name, (state, _) in states(page, folder).items() if state == "on"}
            assert on == expected[folder], folder
        # It differs where the project's own rule changes what it would get without it.
        assert states(page, wt) == {
            "echo": ("on", False),
            "slow": ("off", False),
            "clash": ("off", True),
            "where": ("on", False),
        }
        assert states(page, sub) == {
            "echo": ("on", False),
            "slow": ("on", True),
            "clash": ("on", False),
            "where": ("off", True),
        }
        # Without its own rule, web follows website, and the review says so.
        add_kitden(home, "cursor")
        page.post("/api/rescan", headers=POST)
        pid = project_id(page, str(sub))
        follow = rule_preview(page, server="echo", tool="slow", state=None, project=pid).json()
        assert (follow["after"][0]["state"], follow["after"][0]["word"]) == (
            "off",
            "Follows website",
        )
        assert follow["after"][0]["note"] == (
            "slow of echo will be off in web, as in website. " + AT_ONCE
        )


def test_a_row_names_what_it_follows_without_its_own_rule(home):
    repo, _, _, sub = chain_home(home)
    rules = {
        "global": {"echo": {"tools": {"where": "off"}}},
        "projects": {
            str(repo): {"echo": {"server": "on", "tools": {"slow": "off"}}},
            str(sub): {"echo": {"server": "off", "tools": {"slow": "on", "where": "on"}}},
        },
    }
    hold(home, {"echo": echo()}, rules)
    save_tools(home, "echo", [tool("echo"), tool("slow"), tool("where")])
    with page_for(home) as page:
        pid = project_id(page, str(sub))
        web = page.get(f"/api/gateway/tools?server=echo&project={pid}").json()
        everywhere = page.get("/api/gateway/tools?server=echo").json()
    # Without its own rule, web would follow website for the server and slow, and all projects
    # (None) for where.
    assert (web["state"], web["differs"], web["follows"]) == ("off", True, "website")
    assert [(t["name"], t["state"], t["differs"], t["follows"]) for t in web["tools"]] == [
        ("echo", "on", False, None),
        ("slow", "on", True, "website"),
        ("where", "on", True, None),
    ]
    assert everywhere["follows"] is None
    assert {t["follows"] for t in everywhere["tools"]} == {None}


def test_the_library_and_the_card_follow_enclosing_projects(home):
    repo, wt, _, sub = chain_home(home)
    rules = {"global": {}, "projects": {str(repo): {"files": {"server": "off"}}}}
    hold(home, {"files": FILES}, rules)
    add_kitden(home, "cursor")

    def cell(page, folder):
        pid = project_id(page, str(folder))
        rows = page.get(f"/api/library?kind=mcp_server&project={pid}").json()["rows"]
        return next(r for r in rows if r["name"] == "files")["cells"]["cursor"]["state"]

    def card(page, folder):
        pid = project_id(page, str(folder))
        servers = page.get(f"/api/gateway-view?project={pid}").json()["gateways"][0]["servers"]
        return [(s["state"], s["differs"]) for s in servers]

    with page_for(home) as page:
        assert [cell(page, f) for f in (repo, wt, sub)] == ["off", "off", "off"]
        assert cell(page, home / "work/api") == "gw"
        assert card(page, repo) == [("off", True)]
        assert card(page, sub) == [("off", False)]


def test_a_rule_for_all_projects_names_the_projects_with_their_own_rule(home):
    website, api = project(home, "website"), project(home, "api")
    rules = {"global": {}, "projects": {website: {"echo": {"tools": {"slow": "on"}}}}}
    hold(home, {"echo": echo()}, rules)
    save_tools(home, "echo", [tool("echo"), tool("slow")])
    add_kitden(home, "cursor")

    def note(page, **params):
        answer = rule_preview(page, **params).json()
        page.post(f"/api/changes/{answer['id']}/cancel", headers=POST)
        return answer["after"][0]["note"]

    with page_for(home) as page:
        assert note(page, server="echo", tool="slow", state="off", project=None) == (
            "slow of echo will be off in all projects. It stays on in website, which has its own "
            "rule. " + AT_ONCE
        )
        # A project whose own rule is the same is not named.
        assert note(page, server="echo", tool="slow", state="on", project=None) == (
            "slow of echo will be on in all projects. " + AT_ONCE
        )
    rules["projects"][api] = {"echo": {"server": "on", "tools": {"slow": "on"}}}
    rules["projects"][website]["echo"]["server"] = "on"
    hold(home, {"echo": echo()}, rules)
    with page_for(home) as page:
        assert note(page, server="echo", tool="slow", state="off", project=None) == (
            "slow of echo will be off in all projects. It stays on in api and website, which "
            "have their own rules. " + AT_ONCE
        )
        assert note(page, server="echo", tool=None, state="off", project=None) == (
            "echo will be off in all projects. It stays on in api and website, which have their "
            "own rules. " + AT_ONCE
        )


def test_a_tool_rule_says_when_its_server_is_off_there(home):
    website = project(home, "website")
    rules = {"global": {"echo": {"server": "off"}}, "projects": {}}
    hold(home, {"echo": echo()}, rules)
    save_tools(home, "echo", [tool("echo"), tool("slow")])
    add_kitden(home, "cursor")
    with page_for(home) as page:
        pid = project_id(page, website)
        change = rule_preview(page, server="echo", tool="slow", state="on", project=pid).json()
        assert change["after"][0]["note"] == (
            "slow of echo will be on in website, but echo is off there. " + AT_ONCE
        )
        page.post(f"/api/changes/{change['id']}/cancel", headers=POST)
        # Turning a tool off needs no such word.
        change = rule_preview(page, server="echo", tool="slow", state="off", project=pid).json()
        assert change["after"][0]["note"] == ("slow of echo will be off in website. " + AT_ONCE)


def test_unreadable_gateway_settings_are_a_problem_not_an_empty_gateway(home):
    path = data_dir(home) / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json")
    website = project(home, "website")
    with page_for(home) as page:
        card = page.get("/api/gateway-view").json()["gateways"][0]
        there = page.get(f"/api/gateway-view?project={project_id(page, website)}").json()
    assert (card["id"], card["servers"]) == ("kitden", [])
    assert card["problem"] == "Kitden could not read the gateway settings."
    # Its rules are not known either: the scope bar must not say the project has none.
    assert there["own_rules"] is None

    hold(home, {"files": FILES})
    with page_for(home) as page:
        assert "problem" not in page.get("/api/gateway-view").json()["gateways"][0]
        there = page.get(f"/api/gateway-view?project={project_id(page, website)}").json()
    assert there["own_rules"] == 0


def test_strict_on_writes_the_mode_and_an_on_for_every_offered_tool(home):
    rules = {"global": {"github": {"tools": {"create_issue": "off"}}}}
    hold(home, {"github": echo(), "notion": echo()}, rules)
    save_tools(home, "github", [tool("list_issues"), tool("create_issue")])
    steps = strict_steps(home, {"server": "github", "state": "on"}, load_tools(home))
    assert [(s.edit.key[-1], s.edit.after) for s in steps] == [
        ("mode", "strict"),
        ("list_issues", "on"),
    ]


def test_strict_on_without_a_tool_list_writes_the_mode_only(home):
    hold(home, {"notion": echo()})
    steps = strict_steps(home, {"server": "notion", "state": "on"}, {})
    assert [s.edit.key[-1] for s in steps] == ["mode"]


def test_strict_off_removes_the_mode_only(home):
    hold(home, {"github": echo()}, {"global": {"github": {"mode": "strict"}}})
    save_tools(home, "github", [tool("list_issues")])
    steps = strict_steps(home, {"server": "github", "state": "off"}, load_tools(home))
    assert [s.edit.key for s in steps] == [("rules", "global", "github", "mode")]
    assert steps[0].edit.after is ABSENT


def test_strict_steps_refuse_a_wrong_server_or_state(home):
    hold(home, {"github": echo()})
    for params, words in (
        ({"server": "nope", "state": "on"}, "Choose a server in the Kitden gateway."),
        ({"server": "github", "state": "maybe"}, "Choose on or off."),
    ):
        with pytest.raises(ValueError, match=words):
            strict_steps(home, params, {})


def test_tools_view_says_strict(home):
    rules = {"global": {"github": {"mode": "strict"}}}
    hold(home, {"github": echo()}, rules)
    save_tools(home, "github", [tool("list_issues")])
    assert tools_view(load_settings(home), load_tools(home), "github", [])["strict"] is True
    hold(home, {"github": echo()})
    assert tools_view(load_settings(home), load_tools(home), "github", [])["strict"] is False


def test_strict_on_keeps_the_tools_of_a_server_off_globally_but_on_in_a_project(home):
    website = project(home, "website")
    rules = {
        "global": {"github": {"server": "off", "tools": {"create_issue": "off"}}},
        "projects": {website: {"github": {"server": "on"}}},
    }
    hold(home, {"github": echo()}, rules)
    save_tools(home, "github", [tool("list_issues"), tool("create_issue")])
    steps = strict_steps(home, {"server": "github", "state": "on"}, load_tools(home))
    assert [(s.edit.key[-1], s.edit.after) for s in steps] == [
        ("mode", "strict"),
        ("list_issues", "on"),
    ]
    rules["global"]["github"]["mode"] = "strict"
    rules["global"]["github"]["tools"]["list_issues"] = "on"
    hold(home, {"github": echo()}, rules)
    offered = allowed_tools(load_settings(home), load_tools(home), [website])["github"]
    assert [t["name"] for t in offered] == ["list_issues"]


def test_in_strict_mode_an_unruled_tool_is_new_and_off(home):
    rules = {"global": {"github": {"mode": "strict", "tools": {"list_issues": "on"}}}}
    hold(home, {"github": echo()}, rules)
    save_tools(home, "github", [tool("list_issues"), tool("create_issue")])
    view = tools_view(load_settings(home), load_tools(home), "github", [])
    assert [(t["name"], t["state"], t["new"]) for t in view["tools"]] == [
        ("list_issues", "on", False),
        ("create_issue", "off", True),
    ]


def test_a_tool_with_a_project_rule_is_not_new(home):
    folder = project(home, "website")
    rules = {
        "global": {"github": {"mode": "strict"}},
        "projects": {folder: {"github": {"tools": {"create_issue": "on"}}}},
    }
    hold(home, {"github": echo()}, rules)
    save_tools(home, "github", [tool("create_issue")])
    view = tools_view(load_settings(home), load_tools(home), "github", [folder])
    assert [(t["state"], t["new"]) for t in view["tools"]] == [("on", False)]


def test_outside_strict_mode_no_tool_is_new(home):
    hold(home, {"github": echo()})
    save_tools(home, "github", [tool("list_issues")])
    view = tools_view(load_settings(home), load_tools(home), "github", [])
    assert not any(t["new"] for t in view["tools"])


@pytest.mark.parametrize(
    "tool, expected",
    [
        ({"name": "read_file", "annotations": {"readOnlyHint": True}}, ("reads", "server")),
        ({"name": "search", "annotations": {"readOnlyHint": False}}, ("writes", "server")),
        ({"name": "delete_file", "annotations": {"destructiveHint": True}}, ("writes", "server")),
        ({"name": "create_issue"}, ("may write", "name")),
        ({"name": "uploadFile"}, ("may write", "name")),
        ({"name": "search"}, ("unknown", None)),
        ({"name": "delete_repo", "annotations": {"title": "Delete"}}, ("may write", "name")),
        ({"name": "delete_repo", "annotations": {"openWorldHint": True}}, ("may write", "name")),
        ({"name": "search", "annotations": {"destructiveHint": False}}, ("writes", "server")),
        ({"name": "search", "annotations": {"idempotentHint": True}}, ("writes", "server")),
        ({"name": "edit_file"}, ("may write", "name")),
        ({"name": "push_files"}, ("may write", "name")),
        ({"name": "merge_pull_request"}, ("may write", "name")),
        ({"name": "add_issue_comment"}, ("may write", "name")),
    ],
)
def test_tool_hints_come_from_annotations_then_names(tool, expected):
    assert tool_hint({"description": "", "inputSchema": {}, **tool}) == expected


@pytest.mark.parametrize(
    "name", ["runway_status", "settle_bill", "posture", "putative", "address", "closet", "pushover"]
)
def test_verbs_match_whole_words_only(name):
    assert tool_hint({"name": name}) == ("unknown", None)


@pytest.mark.parametrize("name", ["issues.create", "pr-merge-run", "HTTPPost", "sendMail"])
def test_names_split_on_dots_dashes_and_capitals(name):
    assert tool_hint({"name": name}) == ("may write", "name")


def test_tools_view_says_each_tools_hint(home):
    hold(home, {"github": echo()})
    reads = {**tool("list_issues"), "annotations": {"readOnlyHint": True}}
    save_tools(home, "github", [reads, tool("create_issue")])
    tools = tools_view(load_settings(home), load_tools(home), "github", [])["tools"]
    assert [(t["hint"], t["hint_from"]) for t in tools] == [
        ("reads", "server"),
        ("may write", "name"),
    ]


def test_rules_steps_make_one_step_per_tool(home):
    hold(home, {"github": echo()})
    save_tools(home, "github", [tool("create_issue"), tool("delete_issue")])
    params = {"server": "github", "tools": ["create_issue", "delete_issue"], "state": "off"}
    steps = rules_steps(home, {**params, "project": None}, {})
    assert [s.edit.key[-1] for s in steps] == ["create_issue", "delete_issue"]
    assert {(s.edit.key[1], s.edit.after) for s in steps} == {("global", "off")}


def test_rules_steps_check_what_the_switch_checks(home):
    hold(home, {"github": echo()})
    save_tools(home, "github", [tool("create_issue")])
    base = {"server": "github", "tools": ["create_issue"], "state": "off", "project": None}
    for change, words in (
        ({"tools": []}, "Choose at least one tool."),
        ({"tools": "create_issue"}, "Choose at least one tool."),
        ({"server": "nope"}, "Choose a server in the Kitden gateway."),
        ({"tools": ["gone"]}, "Choose a tool of this server."),
        ({"state": None}, "Choose on or off."),
        ({"project": "p9"}, "Unknown project."),
    ):
        with pytest.raises(ValueError, match=words):
            rules_steps(home, {**base, **change}, {})


def test_tools_view_says_the_shared_state_beside_the_projects_one(home):
    website = project(home, "website")
    rules = {
        "global": {"github": {"tools": {"create_issue": "off"}}},
        "projects": {website: {"github": {"server": "off", "tools": {"create_issue": "on"}}}},
    }
    hold(home, {"github": echo()}, rules)
    save_tools(home, "github", [tool("list_issues"), tool("create_issue")])
    view = tools_view(load_settings(home), load_tools(home), "github", [website])
    # The shared state is what all projects get: the state with no project picked.
    assert (view["state"], view["shared"]) == ("off", "on")
    assert [(t["name"], t["state"], t["shared"]) for t in view["tools"]] == [
        ("list_issues", "on", "on"),
        ("create_issue", "on", "off"),
    ]
    shared = tools_view(load_settings(home), load_tools(home), "github", [])
    assert [t["shared"] for t in shared["tools"]] == [t["state"] for t in shared["tools"]]


def test_the_tools_api_says_each_rule_in_every_known_project(tmp_path):
    from tests.unit.test_demo_mode import demo_page

    with demo_page(tmp_path) as page:  # medium
        ids = {Path(p["path"]).name: p["id"] for p in page.get("/api/projects").json()}
        answer = page.get("/api/gateway/tools?server=files").json()
    states = {p["id"]: p for p in answer["projects"]}
    assert set(states) == set(ids.values())
    # atlas turns write_file off; atlas/web follows atlas; website follows all projects.
    write = {name: states[ids[name]]["tools"]["write_file"] for name in ("atlas", "web", "website")}
    assert write == {"atlas": "off", "web": "off", "website": "on"}
    assert states[ids["web"]]["tools"]["search_files"] == "off"
    assert {p["server"] for p in answer["projects"]} == {"on"}
    # The rule state, not the server's switch: the same words as the gateway decides there.
    assert set(states[ids["website"]]["tools"]) == {t["name"] for t in answer["tools"]}


def test_tools_view_without_chains_names_no_project(home):
    hold(home, {"github": echo()})
    save_tools(home, "github", [tool("list_issues")])
    assert tools_view(load_settings(home), load_tools(home), "github", [])["projects"] == []


def test_tools_view_carries_the_calls(home):
    hold(home, {"github": echo()})
    save_tools(home, "github", [tool("list_issues"), tool("other")])
    calls = {"github": {"list_issues": {"count": 3, "last": "2026-10-21T14:02Z"}}}
    tools = tools_view(load_settings(home), load_tools(home), "github", [], calls)["tools"]
    assert [t["calls"] for t in tools] == [calls["github"]["list_issues"], None]
