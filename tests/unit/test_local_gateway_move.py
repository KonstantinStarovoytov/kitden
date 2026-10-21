"""Moving servers from the clients into the Kitden gateway, in one review with Undo."""

import json
import re
import socket
import stat
import threading
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from starlette.testclient import TestClient

import kitden.clients.base as base
from kitden.changes import json_splice
from kitden.changes.actions import KITDEN_GATEWAY, local_move_steps, needs_sign_in
from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandResult
from kitden.changes.engine import Engine
from kitden.gateways import data_dir
from kitden.local_gateway.settings import SETTINGS_FILE, load_settings, save_tools, servers_on
from kitden.views.inventory import build_inventory, default_adapters
from kitden.views.setup_server import setup_server_state
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state

KITDEN = "/opt/kitden/bin/kitden"
FILES = {"command": "npx", "args": ["files-mcp"], "env": {"FILES_TOKEN": "SENTINEL_SECRET_FILES"}}
CODEX_FILES = """command = "npx"
args = ["files-mcp"]
env = { FILES_TOKEN = "SENTINEL_SECRET_FILES" }"""
ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}


class FakeClaude:
    """Acts like `claude mcp add-json` and `claude mcp remove` on the sandbox ~/.claude.json."""

    def __init__(self, home):
        self.path = home / ".claude.json"

    def __call__(self, command, cwd):
        text = self.path.read_text()
        if command[1:3] == ["mcp", "add-json"]:
            text = json_splice.set_value(text, ("mcpServers", command[-2]), json.loads(command[-1]))
        else:  # claude mcp remove -s <scope> <name>, run in the project for local scope
            scope, name = command[-2], command[-1]
            key = ("mcpServers", name)
            if scope == "local":
                key = ("projects", cwd, *key)
            text = json_splice.delete_value(text, key)
        self.path.write_text(text)
        return CommandResult(0, "")


class FakeRemote(ThreadingHTTPServer):
    """An MCP address that answers every request with `status` and keeps what it got."""

    def __init__(self, status, location=None):
        self.got = []
        got = self.got

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                got.append({"method": self.command, "headers": dict(self.headers), "body": body})
                self.send_response(status)
                if location:
                    self.send_header("Location", location)
                if status == 401:
                    self.send_header("WWW-Authenticate", 'Bearer resource_metadata="x"')
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_GET = do_POST

            def log_message(self, *args):
                pass

        super().__init__(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}/mcp"


@pytest.fixture(autouse=True)
def _no_versions(monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)


def new_home(folder):
    home = make_home(folder, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


@pytest.fixture
def home(tmp_path):
    return new_home(tmp_path)


def add_claude(home, name, entry, project=None):
    path = home / ".claude.json"
    data = json.loads(path.read_text())
    where = data if project is None else data["projects"][str(project)]
    where.setdefault("mcpServers", {})[name] = entry
    path.write_text(json.dumps(data, indent=2))


def add_codex(home, name, lines):
    path = home / ".codex/config.toml"
    path.write_text(path.read_text() + f"\n[mcp_servers.{name}]\n{lines}\n")


def add_cursor(home, name, entry):
    path = home / ".cursor/mcp.json"
    data = json.loads(path.read_text())
    data["mcpServers"][name] = entry
    path.write_text(json.dumps(data, indent=2))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def move(home, *wanted, command=KITDEN):
    """local_move_steps for the (client, name) or (client, name, scope) entries, as the page
    calls it."""
    inventory = build_inventory(home)
    items = [
        i
        for i in inventory.items
        if str(i.kind) == "mcp_server"
        and ((i.client, i.name) in wanted or (i.client, i.name, str(i.scope)) in wanted)
    ]
    assert items, wanted
    adapters = {a.id: a for a in default_adapters(home)}
    states = setup_server_state(inventory)
    added = {s["client"] for s in states if s["state"] in ("added", "plugin")}
    known = [p.path for p in inventory.projects]
    return local_move_steps(adapters, items, home, known, command, added_clients=added)


def apply(home, steps):
    engine = Engine(ChangeStore(data_dir(home)), run=FakeClaude(home))
    change = engine.preview("gateway.move", steps)
    engine.apply(change.id)
    assert str(change.state) == "verified", change.error
    return engine, change


def gateway_file(home):
    return data_dir(home) / SETTINGS_FILE


def claude(home):
    return json.loads((home / ".claude.json").read_text())


def codex(home):
    return tomllib.loads((home / ".codex/config.toml").read_text())


def cursor(home):
    return json.loads((home / ".cursor/mcp.json").read_text())


def tool(name):
    return {"name": name, "description": f"The {name} tool", "inputSchema": {"type": "object"}}


def test_moving_adds_the_server_removes_the_entries_and_adds_kitden_where_missing(
    home, monkeypatch
):
    monkeypatch.setenv("PATH", "/opt/tools/bin:/usr/bin:/bin")
    add_claude(home, "files", {"type": "stdio", **FILES})
    add_codex(home, "files", CODEX_FILES)
    add_cursor(home, "files", FILES)
    add_cursor(home, "kitden", {"command": KITDEN, "args": ["mcp"]})

    steps = move(home, ("claude_code", "files"), ("codex", "files"), ("cursor", "files"))
    assert KITDEN_GATEWAY == "kitden"
    assert [(s.client, s.name) for s in steps] == [
        ("kitden", "files"),
        ("kitden", "PATH"),
        ("claude_code", "files"),
        ("codex", "files"),
        ("cursor", "files"),
        ("claude_code", "kitden"),
        ("codex", "kitden"),
    ]
    assert steps[0].edit.key == ("servers", "files")
    apply(home, steps)

    # The gateway holds the server as the clients had it, without client-only keys.
    path = gateway_file(home)
    assert json.loads(path.read_text()) == {
        "servers": {"files": FILES},
        "path": "/opt/tools/bin:/usr/bin:/bin",
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "SENTINEL_SECRET_FILES" not in steps[0].edit.masked_diff
    assert "SENTINEL_SECRET_FILES" not in (data_dir(home) / "changes.log").read_text()

    # Each client lost its own entry; the clients without `kitden` got it.
    assert "files" not in claude(home)["mcpServers"]
    assert claude(home)["mcpServers"]["kitden"] == {
        "type": "stdio",
        "command": KITDEN,
        "args": ["mcp"],
    }
    assert "files" not in codex(home)["mcp_servers"]
    assert codex(home)["mcp_servers"]["kitden"] == {
        "command": KITDEN,
        "args": ["mcp"],
        "startup_timeout_sec": 30,
        "tool_timeout_sec": 300,
    }
    assert "files" not in cursor(home)["mcpServers"]
    assert cursor(home)["mcpServers"]["kitden"] == {"command": KITDEN, "args": ["mcp"]}


def test_apply_then_undo_puts_every_file_back(home):
    add_claude(home, "files", {"type": "stdio", **FILES})
    add_codex(home, "files", CODEX_FILES)
    files = [home / ".claude.json", home / ".codex/config.toml", home / ".cursor/mcp.json"]
    before = {path: path.read_bytes() for path in files}

    engine, change = apply(home, move(home, ("claude_code", "files"), ("codex", "files")))
    assert gateway_file(home).exists()
    assert {path: path.read_bytes() for path in files} != before

    engine.undo(change.id)
    assert str(change.state) == "undone", change.error
    assert {path: path.read_bytes() for path in files} == before
    assert not gateway_file(home).exists()


def refused(home, wanted, words):
    before = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match=f"^{re.escape(words)}$"):
        move(home, wanted)
    assert {p: p.read_bytes() for p in home.rglob("*") if p.is_file()} == before


def test_project_file_entries_and_shell_values_are_refused_with_reasons(home):
    for client, name in (("claude_code", "docs"), ("cursor", "site-db"), ("codex", "api-docs")):
        refused(home, (client, name), f"{name} is in the project's own files; it stays there.")

    shell = "{} reads values from your shell; it stays direct for now."
    api = {"type": "http", "url": "https://api.invalid/mcp"}
    add_claude(home, "api", {**api, "headers": {"Authorization": "Bearer ${API_KEY}"}})
    add_claude(home, "helped", {**api, "headersHelper": "/opt/bin/headers.sh"})
    add_codex(home, "tokened", 'url = "https://t.invalid/mcp"\nbearer_token_env_var = "TOKEN"')
    add_codex(home, "headed", 'url = "https://e.invalid/mcp"\nenv_http_headers = { X = "X_KEY" }')
    add_codex(home, "helper", 'url = "https://p.invalid/mcp"\nhttp_headers_helper = "/opt/h.sh"')
    add_codex(home, "passes", 'command = "npx"\nenv_vars = ["HOME_TOKEN"]')
    add_cursor(home, "dotenv", {"command": "npx", "envFile": "/opt/app/.env"})
    add_cursor(home, "envref", {"command": "npx", "env": {"KEY": "${env:KEY}"}})
    for client, name in (
        ("claude_code", "api"),
        ("claude_code", "helped"),
        ("codex", "tokened"),
        ("codex", "headed"),
        ("codex", "helper"),
        ("codex", "passes"),
        ("cursor", "dotenv"),
        ("cursor", "envref"),
    ):
        refused(home, (client, name), shell.format(name))

    add_codex(home, "folder", 'command = "npx"\ncwd = "/opt/app"')
    refused(home, ("codex", "folder"), "folder starts in its own folder; it stays direct for now.")

    add_claude(home, "stream", {"type": "sse", "url": "https://s.invalid/sse"})
    refused(
        home,
        ("claude_code", "stream"),
        "stream uses a connection the Kitden gateway does not support yet; "
        "it stays direct for now.",
    )

    add_cursor(home, "broken", {"command": "npx", "env": ["KEY=1"]})
    refused(home, ("cursor", "broken"), "broken could not be read from its file")
    add_cursor(home, "kitden", {"command": KITDEN, "args": ["mcp"]})
    refused(home, ("cursor", "kitden"), "Kitden's own entry stays in each client.")

    # A project placeholder in the arguments is filled in by the gateway, so it may move.
    add_cursor(home, "per-project", {"command": "npx", "args": ["p-mcp", "${workspaceFolder}"]})
    steps = move(home, ("cursor", "per-project"))
    assert steps[0].edit.after == {"command": "npx", "args": ["p-mcp", "${workspaceFolder}"]}


def test_two_different_entries_with_one_name_are_refused(home):
    add_claude(home, "files", {"type": "stdio", **FILES})
    add_codex(home, "files", CODEX_FILES.replace('["files-mcp"]', '["files-mcp", "--fast"]'))
    before = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}

    words = "files is set up differently in Claude Code and Codex; keep one first."
    with pytest.raises(ValueError, match=f"^{re.escape(words)}$"):
        move(home, ("claude_code", "files"), ("codex", "files"))
    # Nothing is half-moved: no step was made, no file changed.
    assert {p: p.read_bytes() for p in home.rglob("*") if p.is_file()} == before
    assert not gateway_file(home).exists()

    # Two entries in one client: the user's and one project's own.
    add_claude(home, "local-db", FILES)
    refused(
        home,
        ("claude_code", "local-db"),
        "local-db is set up differently in two places in Claude Code; keep one first.",
    )


def test_an_oauth_server_is_refused_after_a_401(home):
    oauth, plain = FakeRemote(401), FakeRemote(200)
    try:
        add_claude(home, "linear", {"type": "http", "url": oauth.url})
        words = "linear signs in with OAuth; it stays direct for now."
        refused(home, ("claude_code", "linear"), words)
        assert len(oauth.got) == 1
        assert json.loads(oauth.got[0]["body"])["method"] == "initialize"

        secret = {"Authorization": "Bearer SENTINEL_SECRET_PLAIN"}
        add_codex(home, "plain", f'url = "{plain.url}"\nhttp_headers = {json_inline(secret)}')
        steps = move(home, ("codex", "plain"))
        assert steps[0].edit.after == {"url": plain.url, "headers": secret}
        assert plain.got[0]["headers"]["Authorization"] == "Bearer SENTINEL_SECRET_PLAIN"
    finally:
        oauth.shutdown()
        plain.shutdown()


def json_inline(table):
    return "{ " + ", ".join(f'{k} = "{v}"' for k, v in table.items()) + " }"


def closed_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_the_sign_in_check_sends_the_headers_to_the_servers_own_address_only(home, monkeypatch):
    elsewhere, proxy = FakeRemote(200), FakeRemote(200)
    # Python follows a 302 of a POST with the same headers, unless told not to.
    moved = FakeRemote(302, location=elsewhere.url)
    for name in ("no_proxy", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
    for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy"):
        monkeypatch.setenv(name, f"http://127.0.0.1:{proxy.server_port}")
    secret = {"Authorization": "Bearer SENTINEL_SECRET_PROBE"}
    try:
        assert needs_sign_in(moved.url, secret) is False  # an answer, but not a sign-in
        assert len(moved.got) == 1
        assert moved.got[0]["headers"]["Authorization"] == "Bearer SENTINEL_SECRET_PROBE"
        assert elsewhere.got == [] and proxy.got == []  # no redirect followed, no proxy used
    finally:
        for server in (elsewhere, proxy, moved):
            server.shutdown()

    with pytest.raises(OSError):
        needs_sign_in("file:///etc/hosts", {})

    far = f"http://127.0.0.1:{closed_port()}/mcp"
    add_claude(home, "far", {"type": "http", "url": far, "headers": secret})
    with pytest.raises(ValueError) as error:
        move(home, ("claude_code", "far"))
    assert str(error.value) == "Kitden could not reach far."
    assert error.value.__cause__ is None


def test_codex_and_claude_rules_carry_over(home):
    website = str(home / "work/website")
    config = home / ".codex/config.toml"
    old = 'args = ["run", "aseprite-mcp"]\nenabled = false\n'
    new = old + 'enabled_tools = ["draw", "export"]\ndisabled_tools = ["export"]\n'
    config.write_text(config.read_text().replace(old, new))
    save_tools(home, "aseprite", [tool("draw"), tool("export"), tool("delete_all"), tool("layers")])
    user = json.loads((home / ".claude/settings.json").read_text())
    user["permissions"] = {"deny": ["mcp__aseprite__layers", "Bash(rm:*)", "mcp__other__x"]}
    write_json(home / ".claude/settings.json", user)
    write_json(
        home / "work/website/.claude/settings.json", {"permissions": {"deny": ["mcp__aseprite"]}}
    )
    write_json(
        home / "work/website/.claude/settings.local.json",
        {"permissions": {"deny": ["mcp__aseprite__draw"]}},
    )

    apply(home, move(home, ("codex", "aseprite")))
    saved = json.loads(gateway_file(home).read_text())
    assert saved["servers"] == {"aseprite": {"command": "uv", "args": ["run", "aseprite-mcp"]}}
    assert saved["rules"] == {
        "global": {
            "aseprite": {
                "server": "off",  # Codex had it turned off
                "tools": {"delete_all": "off", "layers": "off", "export": "off"},
            }
        },
        "projects": {website: {"aseprite": {"server": "off", "tools": {"draw": "off"}}}},
    }


def test_a_local_scope_server_is_on_only_in_its_project(home, tmp_path):
    website = str(home / "work/website")
    apply(home, move(home, ("claude_code", "local-db")))
    settings = load_settings(home)
    assert settings["servers"] == {
        "local-db": {"command": "uvx", "args": ["mcp-db", "--password", "SENTINEL_SECRET_DB"]}
    }
    assert settings["rules"] == {
        "global": {"local-db": {"server": "off"}},
        "projects": {website: {"local-db": {"server": "on"}}},
    }
    assert servers_on(settings, website) == ["local-db"]
    assert servers_on(settings, None) == []
    assert "local-db" not in claude(home)["projects"][website]["mcpServers"]

    # The same server at user level too: it is on everywhere, so no rule is needed.
    other = new_home(tmp_path / "other")
    local = claude(other)["projects"][str(other / "work/website")]["mcpServers"]["local-db"]
    add_claude(other, "local-db", local)
    both = (("claude_code", "local-db", "user"), ("claude_code", "local-db", "local"))
    apply(other, move(other, *both))
    assert load_settings(other)["rules"] == {"global": {}, "projects": {}}
    assert claude(other)["mcpServers"].keys() == {"github", "kitden"}


def test_an_existing_codex_kitden_entry_gets_the_timeouts_it_lacks(home):
    add_codex(home, "kitden", f'command = "{KITDEN}"\nargs = ["mcp"]\nstartup_timeout_sec = 45')
    steps = move(home, ("cursor", "n8n-mcp"))
    # Claude Code has no entry to move, so it gets no `kitden` entry here.
    assert [(s.client, s.name) for s in steps if s.client != "kitden"] == [
        ("cursor", "n8n-mcp"),
        ("cursor", "kitden"),
        ("codex", "kitden"),
    ]
    apply(home, steps)
    assert codex(home)["mcp_servers"]["kitden"] == {
        "command": KITDEN,
        "args": ["mcp"],
        "startup_timeout_sec": 45,
        "tool_timeout_sec": 300,
    }
    assert "# Owner comment: keep me" in (home / ".codex/config.toml").read_text()


def test_a_name_the_gateway_has_and_a_missing_kitden_command_are_refused(home):
    write_json(gateway_file(home), {"servers": {"aseprite": {"command": "uv"}}})
    refused(
        home,
        ("codex", "aseprite"),
        "The Kitden gateway already has aseprite. Remove the direct entry instead.",
    )

    words = "The setup server needs the absolute path of the kitden command"
    refused_without = pytest.raises(ValueError, match=f"^{re.escape(words)}$")
    with refused_without:
        move(home, ("cursor", "n8n-mcp"), command=None)
    # Where every client has `kitden` already, the command is not needed.
    add_cursor(home, "kitden", {"command": KITDEN, "args": ["mcp"]})
    assert move(home, ("cursor", "n8n-mcp"), command=None)


def test_the_review_names_every_client_that_offers_the_tools(home):
    add_claude(home, "kitden", {"type": "stdio", "command": KITDEN, "args": ["mcp"]})
    original = {n: (home / n).read_bytes() for n in (".claude.json", ".cursor/mcp.json")}
    app = create_app(
        lambda: build_inventory(home),
        token="tok",
        port=47800,
        home=home,
        run=FakeClaude(home),
        setup_command=lambda: KITDEN,
    )
    item = next(
        i for i in build_inventory(home).items if (i.client, i.name) == ("cursor", "n8n-mcp")
    )
    body = {
        "action": "gateway.move",
        "targets": [{"item": item.id}],
        "params": {"gateway": "kitden"},
    }
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        preview = page.post("/api/changes/preview", json=body, headers=POST)
        assert preview.status_code == 200, preview.json()
        change = preview.json()
        assert "SENTINEL" not in json.dumps(change)
        assert [(a["client"], a["word"]) for a in change["after"]] == [
            ("claude_code", "Via Kitden gateway"),
            ("cursor", "Via Kitden gateway"),
        ]
        assert [a.get("note") for a in change["after"]] == [
            "Claude Code and Cursor will offer its tools through Kitden. "
            "Applies to new sessions.",
            "Cursor's own switches for these tools do not carry over.",
        ]

        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert load_settings(home)["servers"]["n8n-mcp"]["env"] == {
            "N8N_API_KEY": "SENTINEL_SECRET_N8N"
        }
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
    assert {n: (home / n).read_bytes() for n in original} == original


def test_the_review_says_where_a_server_stays_on_or_off(home):
    app = create_app(
        lambda: build_inventory(home),
        token="tok",
        port=47800,
        home=home,
        run=FakeClaude(home),
        setup_command=lambda: KITDEN,
    )
    items = [
        i.id
        for i in build_inventory(home).items
        if (i.client, i.name) in (("claude_code", "local-db"), ("codex", "aseprite"))
    ]
    body = {
        "action": "gateway.move",
        "targets": [{"item": i} for i in items],
        "params": {"gateway": "kitden"},
    }
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        change = page.post("/api/changes/preview", json=body, headers=POST).json()
    assert [(a["client"], a["word"]) for a in change["after"]] == [
        ("claude_code", "Via Kitden gateway"),
        ("codex", "Via Kitden gateway"),
    ]
    assert change["after"][0]["note"] == (
        "Claude Code and Codex will offer their tools through Kitden. "
        "local-db is on only in its project. aseprite stays off, as it was. "
        "Applies to new sessions."
    )
