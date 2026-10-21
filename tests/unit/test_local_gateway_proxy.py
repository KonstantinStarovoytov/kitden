"""The gateway inside `kitden mcp`: the tools of moved servers, per project.

Most tests start `kitden mcp` with the SDK's stdio client, on a sandbox home whose gateway
settings hold the fake server in tests/fixtures/fake_mcp.
"""

import hashlib
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anyio
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp_types import ListRootsResult, Root
from starlette.testclient import TestClient

import kitden.clients.base as base
import kitden.clients.codex as codex
from kitden import mcp_server
from kitden.gateways import data_dir
from kitden.local_gateway import proxy
from kitden.local_gateway.proxy import Upstreams, exposed_names
from kitden.local_gateway.settings import SETTINGS_FILE, load_settings, load_tools, save_tools
from kitden.mcp_server import create_server
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

ECHO = Path(__file__).parents[1] / "fixtures/fake_mcp/echo_server.py"
KITDEN = "/opt/kitden/bin/kitden"
READ_ONLY = {"show_setup", "list_findings", "explain_item", "list_projects"}
pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def home(tmp_path):
    """A sandbox home where Claude Code knows the project work/website."""
    return make_home(tmp_path, "claude_code/2.1.283")


def echo(name, *args):
    """A gateway entry that runs the fake server as `name`."""
    return {"command": sys.executable, "args": [str(ECHO), name, *args]}


def tool(name):
    return {"name": name, "description": f"The {name} tool", "inputSchema": {"type": "object"}}


def write_settings(home, servers, rules=None, **extra):
    path = data_dir(home) / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"servers": servers, "rules": rules or {}, **extra}))


def roots_of(folder):
    async def answer(context):
        return ListRootsResult(roots=[Root(uri=folder.as_uri())])

    return answer


def gateway(home, cwd=None, env=None, roots=None, errlog=None, mode="legacy"):
    """A client for `kitden mcp` started on `home`, as a client app starts it."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "kitden", "mcp", "--home", str(home)],
        env=env,
        cwd=cwd or home,
    )
    server = stdio_client(params, errlog=errlog) if errlog else params
    return Client(server, mode=mode, list_roots_callback=roots, read_timeout_seconds=60)


async def names_offered(client):
    return {t.name for t in (await client.list_tools()).tools}


def text(result):
    return result.content[0].text


async def test_upstream_tools_are_offered_beside_the_read_only_ones(home, tmp_path):
    started = tmp_path / "cached-started"
    write_settings(home, {"echo": echo("echo"), "cached": echo("cached", "--mark", str(started))})
    save_tools(home, "cached", [{**tool("from_cache"), "description": "Kept in the cache"}])

    async with gateway(home, mode="auto") as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}

    assert set(tools) == READ_ONLY | {"echo", "slow", "clash", "refuse", "where", "from_cache"}
    assert tools["echo"].input_schema["required"] == ["text"]
    # A known list is offered from the cache, and the server is not started for it.
    assert tools["from_cache"].description == "Kept in the cache"
    assert not started.exists()
    # A server whose list was not known yet was asked at once, and its list was kept.
    listed = [t["name"] for t in load_tools(home)["echo"]]
    assert listed == ["echo", "slow", "clash", "refuse", "where"]


def test_the_gateway_reads_known_projects_without_client_commands(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    write_settings(home, {"echo": echo("echo")})
    served, ran = {}, []

    def record(args, *rest, **options):
        ran.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    # Every client command would be found and run, and nothing is remembered from other tests.
    monkeypatch.setattr(subprocess, "run", record)
    monkeypatch.setattr(base, "version_command", lambda client: ["/bin/false"])
    monkeypatch.setattr(codex, "version_command", lambda client: ["/bin/false"])
    monkeypatch.setattr(base, "_VERSION_CACHE", {})
    monkeypatch.setattr(proxy, "run", lambda home, own, known: served.update(known=known))

    mcp_server.run(home)
    known = served["known"]()

    assert ran == []
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    assert sorted(known) == sorted(p.path for p in build_inventory(home).projects)
    assert str(home / "work/website") in known


async def test_without_servers_kitden_mcp_is_unchanged(home):
    asked = []

    async def roots(context):
        asked.append("roots")
        return ListRootsResult(roots=[])

    async with gateway(home, roots=roots) as client:
        assert await names_offered(client) == READ_ONLY
    assert asked == []


async def test_project_rules_decide_the_tools_of_a_session(home):
    website = home / "work/website"
    inside = website / "src"
    inside.mkdir()
    rules = {
        "global": {"echo": {"tools": {"slow": "off"}}},
        "projects": {str(website): {"echo": {"tools": {"slow": "on", "clash": "off"}}}},
    }
    write_settings(home, {"echo": echo("echo")}, rules)
    save_tools(home, "echo", [tool("echo"), tool("slow"), tool("clash")])

    async def offered(**how):
        async with gateway(home, **how) as client:
            return await names_offered(client) - READ_ONLY

    # Claude Code names the project in the env.
    assert await offered(env={"CLAUDE_PROJECT_DIR": str(website)}) == {"echo", "slow"}
    # Cursor names it as the first root; a folder inside a project belongs to it.
    assert await offered(roots=roots_of(inside)) == {"echo", "slow"}
    # Codex starts the gateway in the session folder.
    assert await offered(cwd=inside) == {"echo", "slow"}
    # Started in the home folder: no project, so the global rules.
    assert await offered() == {"echo", "clash"}
    # Started in a folder Kitden does not know (a Codex chat folder): the global rules too.
    chat = home.parent / "codex-chats/chat-1"
    chat.mkdir(parents=True)
    assert await offered(cwd=chat) == {"echo", "clash"}


async def test_kitdens_own_tools_see_the_servers_in_the_gateway(home, monkeypatch):
    website = home / "work/website"
    state = json.loads((home / ".claude.json").read_text())
    state["mcpServers"]["kitden"] = {"type": "stdio", "command": KITDEN, "args": ["mcp"]}
    # files is in the gateway, on only in website, and Claude Code has a direct copy too.
    state["mcpServers"]["files"] = {"type": "stdio", **echo("files")}
    (home / ".claude.json").write_text(json.dumps(state))
    rules = {
        "global": {"files": {"server": "off"}},
        "projects": {str(website): {"files": {"server": "on"}}},
    }
    write_settings(home, {"files": echo("files")}, rules)
    # `kitden mcp` as a client starts it, in this process so no client command runs.
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    served = {}
    monkeypatch.setattr(proxy, "run", lambda home, own, known: served.update(own=own))
    mcp_server.run(home)
    here = {"project_path": str(website)}
    setup = await served["own"].call_tool("show_setup", {"client": "claude_code", **here})
    found = await served["own"].call_tool("list_findings", here)

    views = setup.structured_content["views"]
    items = [i for view in views for i in view["items"] if i["name"] == "files"]
    assert [(i["scope"], i["via_gateway"]) for i in items] == [("project", "kitden")]
    # The page says the same.
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url="http://127.0.0.1:47800") as page:
        page.get("/?token=tok")
        shown = page.get("/api/findings", params={"project": str(website)}).json()
    assert [f["id"] for f in found.structured_content["findings"]] == [f["id"] for f in shown]


async def test_a_call_reaches_the_upstream_server(home):
    website = home / "work/website"
    entry = echo("echo", "${workspaceFolder}", "${CLAUDE_PROJECT_DIR}", "${CLAUDE_PROJECT_DIR:-.}")
    entry["env"] = {"ECHO_TOKEN": "SENTINEL_SECRET_GATEWAY_ENV"}
    write_settings(home, {"echo": entry}, path="/usr/bin:/bin")
    save_tools(home, "echo", [tool("echo"), tool("where"), tool("refuse")])
    env = {"CLAUDE_PROJECT_DIR": str(website), "LANG": "en_US.UTF-8", "KITDEN_OTHER": "x"}

    async with gateway(home, env=env) as client:
        await client.list_tools()
        said = await client.call_tool("echo", {"text": "hello"})
        where = json.loads(text(await client.call_tool("where", {})))
        refused = await client.call_tool("refuse", {"reason": "Give the text to look for."})
        projects = await client.call_tool("list_projects", {})

    assert not said.is_error and text(said) == "hello"
    # The server's own error answer reaches the model as it is, so the model can fix its call.
    assert refused.is_error and text(refused) == "Give the text to look for."
    # Kitden's read-only tools answer as they do without servers.
    assert not projects.is_error
    assert str(website) in {p["path"] for p in projects.structured_content["projects"]}
    # The server runs in the project, with the project in its arguments.
    assert Path(where["cwd"]).resolve() == website.resolve()
    assert where["args"][1:] == [str(website)] * 3
    # Its env: the home folder, the saved PATH, USER and LANG, and its own env; nothing else of
    # the client's env.
    assert where["home"] == str(home)
    assert where["path"] == "/usr/bin:/bin"
    assert {"HOME", "PATH", "USER", "LANG", "ECHO_TOKEN"} <= set(where["env"])
    assert "KITDEN_OTHER" not in where["env"] and "CLAUDE_PROJECT_DIR" not in where["env"]


async def test_a_tool_turned_off_during_a_session_is_refused_on_its_next_call(home):
    write_settings(home, {"echo": echo("echo")})
    save_tools(home, "echo", [tool("echo"), tool("where")])

    async with gateway(home) as client:
        await client.list_tools()
        said = await client.call_tool("echo", {"text": "hi"})
        off = {"global": {"echo": {"tools": {"echo": "off"}}}}
        write_settings(home, {"echo": echo("echo")}, off)
        answer = await client.call_tool("echo", {"text": "hi"})
        other = await client.call_tool("where", {})
        offered = await names_offered(client)

    assert not said.is_error and text(said) == "hi"
    assert answer.is_error and text(answer) == "echo is turned off in Kitden."
    # Only the switched-off tool is refused; the list stays as the session found it.
    assert not other.is_error
    assert {"echo", "where"} <= offered


async def test_a_broken_rules_file_keeps_the_rules_the_session_started_with(home):
    off = {"global": {"echo": {"tools": {"echo": "off"}}}}
    write_settings(home, {"echo": echo("echo")}, off)
    save_tools(home, "echo", [tool("echo"), tool("where")])

    async with gateway(home) as client:
        await client.list_tools()
        (data_dir(home) / SETTINGS_FILE).write_text("{ not json")
        refused = await client.call_tool("echo", {"text": "hi"})
        works = await client.call_tool("where", {})

    assert refused.is_error
    assert not works.is_error


async def test_the_gateway_says_once_that_the_tool_list_changed(home):
    write_settings(home, {"echo": echo("echo")})
    save_tools(home, "echo", [tool("echo"), tool("where")])
    heard = []

    async def listen(message):
        heard.append(repr(message))

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "kitden", "mcp", "--home", str(home)], cwd=home
    )
    async with Client(params, mode="legacy", message_handler=listen) as client:
        await client.list_tools()
        await client.call_tool("where", {})
        off = {"global": {"echo": {"tools": {"echo": "off"}}}}
        write_settings(home, {"echo": echo("echo")}, off)
        await client.call_tool("where", {})
        await client.call_tool("where", {})

    assert sum("tools/list_changed" in h for h in heard) == 1


async def test_a_local_server_starts_in_the_folder_the_session_names(home):
    website = home / "work/website"
    (website / ".git" / "worktrees" / "fix").mkdir(parents=True)
    worktree = home / "work/website-fix"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {website}/.git/worktrees/fix\n")
    # On only in website: a worktree of it gets its rules.
    rules = {
        "global": {"echo": {"server": "off"}},
        "projects": {str(website): {"echo": {"server": "on"}}},
    }
    entry = echo("echo", "${workspaceFolder}", "${CLAUDE_PROJECT_DIR}")
    write_settings(home, {"echo": entry}, rules)
    save_tools(home, "echo", [tool("where")])

    async def where(**how):
        async with gateway(home, **how) as client:
            assert "where" in await names_offered(client)
            found = json.loads(text(await client.call_tool("where", {})))
        return [Path(folder).resolve() for folder in (found["cwd"], *found["args"][1:])]

    # Claude Code names the worktree; Codex starts the gateway in it.
    assert await where(env={"CLAUDE_PROJECT_DIR": str(worktree)}) == [worktree.resolve()] * 3
    inside = worktree / "src"
    inside.mkdir()
    assert await where(cwd=inside) == [inside.resolve()] * 3

    # No folder named (Codex started in the home folder): the server starts in the home folder.
    write_settings(home, {"echo": echo("echo", "${workspaceFolder}")})
    assert await where() == [home.resolve()] * 2


async def test_a_slow_server_does_not_hold_up_the_list_or_other_servers(
    home, tmp_path, monkeypatch
):
    # In this process, so the timeouts can be short.
    monkeypatch.setattr(proxy, "START_TIMEOUT", 4)
    monkeypatch.setattr(proxy, "CALL_TIMEOUT", 5)
    started, waiting = tmp_path / "stuck-started", tmp_path / "slow-waiting"
    write_settings(
        home, {"alpha": echo("alpha"), "stuck": echo("stuck", "--mark", str(started), "--hang")}
    )
    save_tools(home, "alpha", [tool("echo"), tool("slow")])
    save_tools(home, "stuck", [tool("wait")])
    server = proxy.gateway_server(home, create_server(lambda: None), known=lambda: [])
    results = {}

    async with Client(server, mode="legacy") as client:
        # Every list is known: the list comes at once and no server starts for it.
        with anyio.fail_after(1):
            await client.list_tools()
        assert not started.exists()

        async def call(name, arguments):
            results[name] = await client.call_tool(name, arguments)

        async with anyio.create_task_group() as calls:
            calls.start_soon(call, "slow", {"seconds": 30, "note": str(waiting)})
            calls.start_soon(call, "wait", {})
            with anyio.fail_after(10):
                while not (started.exists() and waiting.exists()):
                    await anyio.sleep(0.05)
            # While stuck hangs at start and a call of alpha runs, the rest answers at once.
            with anyio.fail_after(1):
                said = await client.call_tool("echo", {"text": "hi"})
                await client.list_tools()
            assert results == {}

    assert text(said) == "hi"
    assert [(results[name].is_error, text(results[name])) for name in ("wait", "slow")] == [
        (True, "stuck did not start in 4 seconds."),
        (True, "alpha did not answer in 5 seconds."),
    ]


async def test_two_servers_with_one_tool_name_both_work_with_stable_names(home):
    write_settings(home, {"beta": echo("beta"), "alpha": echo("alpha")})

    async with gateway(home) as client:
        first = await names_offered(client)
        alpha = await client.call_tool("clash", {})
        beta = await client.call_tool("beta_clash", {})
    assert {"clash", "beta_clash", "echo", "beta_echo"} <= first
    assert (text(alpha), text(beta)) == ("alpha", "beta")

    # The next session, with the servers saved in the other order, gets the same names.
    write_settings(home, {"alpha": echo("alpha"), "beta": echo("beta")})
    async with gateway(home) as client:
        assert await names_offered(client) == first


async def test_a_tool_turned_off_in_a_project_does_not_rename_another(home, monkeypatch):
    website = home / "work/website"
    rules = {"global": {}, "projects": {str(website): {"alpha": {"tools": {"clash": "off"}}}}}
    write_settings(home, {"alpha": echo("alpha"), "beta": echo("beta")}, rules)
    save_tools(home, "alpha", [tool("clash"), tool("echo")])
    save_tools(home, "beta", [tool("clash")])

    async def offered(folder):
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(folder))
        own = create_server(lambda: None)
        server = proxy.gateway_server(home, own, known=lambda: [str(website)])
        async with Client(server, mode="legacy") as client:
            return await names_offered(client) - READ_ONLY

    assert await offered(home / "work") == {"clash", "echo", "beta_clash"}
    # beta's clash keeps its name where alpha's is off: one name is always one tool.
    assert await offered(website) == {"echo", "beta_clash"}


async def test_tools_keep_their_title_and_hints(home):
    hints = {"readOnlyHint": True, "destructiveHint": False}
    write_settings(home, {"docs": echo("docs")})
    save_tools(home, "docs", [{**tool("search"), "title": "Search docs", "annotations": hints}])
    server = proxy.gateway_server(home, create_server(lambda: None), known=lambda: [])
    async with Client(server, mode="legacy") as client:
        listed = {t.name: t for t in (await client.list_tools()).tools}
    assert listed["search"].title == "Search docs"
    assert listed["search"].annotations.read_only_hint is True
    assert listed["search"].annotations.destructive_hint is False


async def test_a_server_gets_the_start_time_its_codex_entry_had(home, monkeypatch):
    monkeypatch.setattr(proxy, "START_TIMEOUT", 1.5)
    stuck = {**echo("stuck", "--hang"), "startup_timeout_sec": 2}
    quick = {**echo("quick", "--hang"), "startup_timeout_sec": 0.5}
    async with Upstreams(home, {"servers": {"stuck": stuck, "quick": quick}}) as upstreams:
        waited = [await upstreams.call(name, "wait", {}) for name in ("stuck", "quick")]
    # The longer of the gateway's own time and the entry's own.
    assert [text(answer) for answer in waited] == [
        "stuck did not start in 2 seconds.",
        "quick did not start in 1.5 seconds.",
    ]


def test_a_server_name_with_other_characters_gets_a_clean_prefix():
    names = exposed_names({"a": [tool("clash")], "my.docs server": [tool("clash")]})
    assert names == {"clash": ("a", "clash"), "my_docs_server_clash": ("my.docs server", "clash")}


def test_servers_whose_names_clean_to_one_name_keep_every_tool():
    # All four become "a_b_" in front; Kitden's own list_projects is taken too.
    servers = ("a b", "a,b", "a.b", "a_b")
    tools = {server: [tool("search"), tool("list_projects")] for server in servers}
    names = exposed_names(tools, taken={"list_projects"})
    assert sorted(names.values()) == sorted(
        (s, t) for s in servers for t in ("search", "list_projects")
    )
    assert all(len(name) <= 54 for name in names)


async def test_the_instructions_say_which_tools_only_read(home):
    async with gateway(home) as client:
        plain = client.instructions
    write_settings(home, {"echo": echo("echo")})
    save_tools(home, "echo", [tool("echo")])
    async with gateway(home) as client:
        held = client.instructions
    assert plain == mcp_server.INSTRUCTIONS
    assert "Read-only: this tool cannot change settings." in plain
    assert "Read-only" not in held
    assert (
        "Kitden's own tools (show_setup, list_findings, explain_item, list_projects) only read"
        in held
    )
    assert "The other tools come from MCP servers moved into the Kitden gateway" in held


async def test_unreadable_settings_leave_kitden_mcp_as_it_was(home):
    path = data_dir(home) / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json")
    async with gateway(home) as client:
        assert await names_offered(client) == READ_ONLY


def test_exposed_names_stay_within_cursors_limit():
    long_server = "zz-a-very-long-server-name-for-gateway-tests"
    long_tool = "x" * 60
    allowed = {
        long_server: [tool("list_issues"), tool("search")],
        "github": [tool("list_issues"), tool(long_tool)],
        "linear": [tool("list_projects")],
    }

    names = exposed_names(allowed, taken={"list_projects"})

    def cut(name):
        return name[:45] + "_" + hashlib.sha1(name.encode()).hexdigest()[:8]

    assert names == {
        "list_issues": ("github", "list_issues"),
        cut(long_tool): ("github", long_tool),
        # A name Kitden's own tools use gets the server in front, like a clash.
        "linear_list_projects": ("linear", "list_projects"),
        cut(f"{long_server}_list_issues"): (long_server, "list_issues"),
        "search": (long_server, "search"),
    }
    # Cursor allows 60 characters for server and tool; the entry is named "kitden".
    assert all(len("kitden" + name) <= 60 for name in names)
    # The order the servers come in does not change any name.
    assert exposed_names(dict(reversed(allowed.items())), taken={"list_projects"}) == names


def test_a_prefixed_name_never_replaces_another_tool():
    allowed = {
        "atlassian": [tool("jira_search"), tool("search")],
        "jira": [tool("search")],
    }

    names = exposed_names(allowed)

    jira_search = "jira_search_" + hashlib.sha1(b"jira_search").hexdigest()[:8]
    assert names == {
        "jira_search": ("atlassian", "jira_search"),
        "search": ("atlassian", "search"),
        jira_search: ("jira", "search"),
    }


class FailingServer(ThreadingHTTPServer):
    """An MCP address that answers every request with an error, and notes what it got."""

    def __init__(self):
        self.headers_seen = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                server.headers_seen.append(self.headers.get("Authorization"))
                self.send_response(500)
                self.end_headers()

            do_GET = do_DELETE = do_POST

            def log_message(self, *args):
                pass

        super().__init__(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()


async def test_secrets_stay_out_of_errors_and_logs(home, tmp_path):
    remote = FailingServer()
    url = f"http://127.0.0.1:{remote.server_port}/mcp?key=SENTINEL_SECRET_GATEWAY_QUERY"
    headers = {"Authorization": "Bearer SENTINEL_SECRET_GATEWAY_HEADER"}
    write_settings(
        home,
        {
            "local": {
                "command": str(tmp_path / "no-such-server"),
                "env": {"LOCAL_TOKEN": "SENTINEL_SECRET_GATEWAY_ENV"},
            },
            "remote": {"url": url, "headers": headers},
            "remote-new": {"url": url, "headers": headers},
        },
    )
    save_tools(home, "local", [tool("local_tool")])
    save_tools(home, "remote", [tool("remote_tool")])
    log = tmp_path / "stderr.txt"

    try:
        with log.open("w") as errlog:
            async with gateway(home, errlog=errlog) as client:
                offered = await names_offered(client)
                answers = [
                    await client.call_tool("local_tool", {}),
                    await client.call_tool("remote_tool", {}),
                ]
    finally:
        remote.shutdown()

    assert offered == READ_ONLY | {"local_tool", "remote_tool"}
    assert [(a.is_error, text(a)) for a in answers] == [
        (True, "Kitden could not start local."),
        (True, "Kitden could not reach remote."),
    ]
    assert remote.headers_seen and set(remote.headers_seen) == {headers["Authorization"]}
    printed = log.read_text()
    # Each problem is one plain line on stderr.
    for line in (
        "Kitden could not reach remote-new.",
        "Kitden could not start local.",
        "Kitden could not reach remote.",
    ):
        assert f"{line}\n" in printed
    assert "SENTINEL" not in printed + json.dumps([text(a) for a in answers])


async def test_unreadable_projects_give_the_global_set(home, capsys):
    write_settings(home, {"echo": echo("echo")}, {"global": {"echo": {"tools": {"slow": "off"}}}})
    save_tools(home, "echo", [tool("echo"), tool("slow")])

    def unreadable():
        raise OSError("unreadable")

    server = proxy.gateway_server(home, create_server(lambda: None), known=unreadable)
    async with Client(server, mode="legacy") as client:
        assert await names_offered(client) - READ_ONLY == {"echo"}
    line = "Kitden could not read the known projects; this session gets the global set of tools."
    assert f"{line}\n" in capsys.readouterr().err


async def test_upstreams_work_only_inside_async_with(home):
    upstreams = Upstreams(home, load_settings(home) | {"servers": {"echo": echo("echo")}})
    with pytest.raises(RuntimeError, match="async with"):
        await upstreams.list_tools("echo")
    with pytest.raises(RuntimeError, match="async with"):
        await upstreams.call("echo", "echo", {"text": "hi"})

    # An error in the block reaches the task group, as with any task group.
    with pytest.raises(ExceptionGroup) as raised:
        async with Upstreams(home, load_settings(home)):
            raise ValueError("in the block")
    assert raised.group_contains(ValueError)


class FakeHttpServer(ThreadingHTTPServer):
    """A streamable HTTP MCP server: it starts, answers `refuse` with its own JSON-RPC error and
    `moved` with a redirect to another address."""

    def __init__(self, moved_to):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if "id" not in body:  # a notification
                    return self.answer(202)
                if body["method"] == "initialize":
                    version = body["params"]["protocolVersion"]
                    info = {"name": "fake", "version": "1"}
                    reply = {"protocolVersion": version, "capabilities": {}, "serverInfo": info}
                    return self.answer(200, {"result": reply}, body["id"])
                if body["params"]["name"] == "moved":
                    return self.answer(307, location=moved_to)
                error = {"code": -32602, "message": "Give the text to look for."}
                return self.answer(200, {"error": error}, body["id"])

            def do_GET(self):
                self.answer(405)

            do_DELETE = do_GET

            def answer(self, status, message=None, id=None, location=None):
                data = (
                    json.dumps({"jsonrpc": "2.0", "id": id, **message}).encode() if message else b""
                )
                self.send_response(status)
                if location:
                    self.send_header("Location", location)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        super().__init__(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()


async def test_a_servers_own_error_passes_but_a_transport_error_stays_plain(home):
    remote = FakeHttpServer("http://127.0.0.1:9/elsewhere?key=SENTINEL_SECRET_GATEWAY_REDIRECT")
    settings = {"servers": {"remote": {"url": f"http://127.0.0.1:{remote.server_port}/mcp"}}}
    try:
        async with Upstreams(home, settings) as upstreams:
            refused = await upstreams.call("remote", "refuse", {})
            moved = await upstreams.call("remote", "moved", {})
    finally:
        remote.shutdown()

    assert (refused.is_error, text(refused)) == (True, "Give the text to look for.")
    # The HTTP layer makes its own errors, and a refused redirect names the other address.
    assert (moved.is_error, text(moved)) == (True, "The call to remote failed.")
