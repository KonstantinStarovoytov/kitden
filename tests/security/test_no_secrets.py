"""Secret and network sweep (T063, SC-004, FR-006, FR-038).

Runs every output path with fixtures full of SENTINEL_SECRET_ values: page responses (including
change previews of entries that hold secrets), the change log and backup manifests,
`scan --json`, and every MCP tool. No sentinel may appear, and the tool's own process must not
open a network connection. Client commands the tool starts (for example `--version`) are separate
programs and are replaced by stand-ins here. The same sweep runs on each size of the demo's sample,
whose fake secrets all start with `DEMO_SECRET_`.
"""

import json
import socket
from urllib.parse import quote

import pytest
from mcp import Client
from starlette.testclient import TestClient

import kitden.cli as cli
from kitden.demo import DEMO_SECRET, SIZES, build_demo_home, demo_build
from kitden.gateways import data_dir
from kitden.local_gateway.settings import load_settings
from kitden.mcp_server import create_server
from kitden.views.inventory import build_inventory, default_adapters
from kitden.views.library import KINDS
from kitden.web.app import create_app
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_api_changes import FakeClaude

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
LOCAL = {"127.0.0.1", "::1", "localhost", "testserver", None}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def network_attempts(monkeypatch):
    attempts: list = []
    real_connect = socket.socket.connect
    real_lookup = socket.getaddrinfo

    def connect(self, address):
        if isinstance(address, tuple) and address[0] not in LOCAL:
            attempts.append(address)
            raise OSError("network is blocked in this test")
        return real_connect(self, address)

    def lookup(host, *args, **kwargs):
        if host not in LOCAL:
            attempts.append(host)
            raise OSError("network is blocked in this test")
        return real_lookup(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    return attempts


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def _page_outputs(home) -> list[str]:
    outputs: list[str] = []
    app = create_app(
        lambda: build_inventory(home),
        token="tok",
        port=47800,
        home=home,
        run=FakeClaude(home),
        setup_command=lambda: "/opt/kitden/bin/kitden",
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")

        def post(path, body=None):
            response = page.post(path, json=body, headers=POST)
            outputs.append(response.text)
            return response.json()

        gateway = post(
            "/api/gateways",
            {"url": "http://127.0.0.1:12008/mcp", "auth": "env_key", "key_env_var": "GW_KEY"},
        )
        targets = [{"client": c} for c in ("claude_code", "codex", "cursor")]
        changes = [
            post(
                "/api/changes/preview",
                {
                    "action": "gateway.connect",
                    "targets": targets,
                    "params": {"gateway": gateway["id"], "name": "gw"},
                },
            ),
            post(
                "/api/changes/preview",
                {"action": "setup_server.register", "targets": targets, "params": {}},
            ),
        ]
        # Removing entries that hold secrets shows them in a diff: it must be masked.
        for item in page.get("/api/items?kind=mcp_server").json():
            user_level = item["client"] != "claude_code" or item["scope"] == "user"
            if item["secret_present"] and "mcp.remove_direct" in item["actions"] and user_level:
                body = {
                    "action": "mcp.remove_direct",
                    "targets": [{"item": item["id"]}],
                    "params": {},
                }
                changes.append(post("/api/changes/preview", body))
        # A server put back from the Kitden gateway: `claude mcp add-json` carries its entry.
        held = {"command": "npx", "env": {"FILES_TOKEN": "SENTINEL_SECRET_HELD"}}
        settings = data_dir(home) / "gateway.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({"servers": {"held-files": held}}))
        body = {
            "action": "gateway.put_back",
            "targets": [{"client": "claude_code"}],
            "params": {"server": "held-files"},
        }
        changes.append(post("/api/changes/preview", body))
        # A server copied to another client: the diff, the log and the record hold its entry.
        items = page.get("/api/items?kind=mcp_server").json()
        copies = (("claude_code", "github", "codex"), ("codex", "langfuse-data", "claude_code"))
        for who, name, client in copies:
            item = next(i for i in items if (i["client"], i["name"]) == (who, name))
            body = {
                "action": "mcp.add",
                "targets": [{"client": client}],
                "params": {"item": item["id"]},
            }
            changes.append(post("/api/changes/preview", body))
        assert len(changes) >= 8
        for change in changes:
            post(f"/api/changes/{change['id']}/apply")
            post(f"/api/changes/{change['id']}/undo")

        for path in [
            "/api/clients",
            "/api/items",
            "/api/projects",
            "/api/problems",
            "/api/findings",
            "/api/changes",
            "/api/gateways",
            "/api/overview",
            "/api/map",
            "/api/gateway-view",
            "/api/library-map",
            "/api/instructions-map",
            "/api/market-servers",
            "/api/library-offers",
        ]:
            outputs.append(page.get(path).text)
        for item in page.get("/api/items?kind=mcp_server").json():
            outputs.append(page.get(f"/api/explain?name={item['name']}&kind=mcp_server").text)
        # Instruction files: Details shows their first lines.
        outputs.append(page.get("/api/library?kind=instructions").text)
        for tab in ("plugin", "instructions"):
            outputs.append(page.get(f"/api/library-list?kind={tab}").text)
        projects = [f"&project={p['id']}" for p in page.get("/api/projects").json()]
        for query in ["", *projects]:
            explained = page.get(f"/api/explain?name=CLAUDE.md&kind=instructions{query}").text
            assert "[secret]" in explained  # the preview is there, masked
            outputs.append(explained)
        for project in page.get("/api/projects").json():
            outputs.append(page.get(f"/api/projects/{project['id']}/effective").text)
            outputs.append(page.get(f"/api/library-map?project={project['id']}").text)
            outputs.append(page.get(f"/api/instructions-map?project={project['id']}").text)
            outputs.append(page.get(f"/api/findings?project={project['path']}").text)
        for item in page.get("/api/items").json():
            if item["kind"] in ("plugin", "marketplace"):
                outputs.append(page.get(f"/api/commands?item={item['id']}").text)
    return outputs


async def _mcp_outputs(build, home, names) -> list[str]:
    """Every MCP tool's answer on what `build` reads, with `explain_item` asked for `names`."""
    server = create_server(build, cwd=lambda: str(home))
    outputs = []
    async with Client(server) as client:
        projects = (await client.call_tool("list_projects", {})).structured_content["projects"]
        calls = [("list_projects", {}), ("show_setup", {}), ("list_findings", {})]
        for project in projects:
            calls += [
                ("show_setup", {"project_path": project["path"]}),
                ("list_findings", {"project_path": project["path"]}),
            ]
        for name in names:
            calls.append(("explain_item", {"name": name}))
        for tool, arguments in calls:
            result = await client.call_tool(tool, arguments)
            outputs.append(
                json.dumps(result.structured_content)
                + json.dumps([c.model_dump() for c in result.content])
            )
    return outputs


@pytest.mark.anyio
async def test_no_secret_in_any_output_and_no_network(home, network_attempts, capsys):
    # An imported file holds a secret: the Instructions map names the import, never its text.
    # A token written after `@` is hidden in the name and the path, found or missing.
    claude = home / ".claude/CLAUDE.md"
    named = "ghp_SENTINEL_SECRET_IN_A_FILE_NAME"
    claude.write_text(claude.read_text() + f"@notes.md @{named}.md @ghp_SENTINEL_SECRET_MISSING\n")
    (home / ".claude/notes.md").write_text("api_key = SENTINEL_SECRET_IMPORTED\n")
    (home / f".claude/{named}.md").write_text("# Named\n")
    outputs = _page_outputs(home)
    assert any('"name":"notes.md"' in text for text in outputs)
    store = data_dir(home)
    outputs.append((store / "changes.log").read_text())
    outputs += [p.read_text() for p in store.glob("changes/*/manifest.json")]
    # A change record keeps the entry for Undo, but its commands only masked.
    for record in store.glob("changes/*/change.json"):
        steps = json.loads(record.read_text())["steps"]
        outputs.append(json.dumps([s["command"] for s in steps]))

    cli.main(["scan", "--json", "--home", str(home)])
    outputs.append(capsys.readouterr().out)

    names = ["github", "local-db", "langfuse-data", "n8n-mcp", "CLAUDE.md"]
    outputs += await _mcp_outputs(lambda: build_inventory(home), home, names)

    leaked = [text for text in outputs if "SENTINEL" in text]
    assert leaked == []
    # The key a move compares entries by is made from their secrets too: it stays server-side.
    keys = {i.entry_key for i in build_inventory(home).items if i.entry_key}
    assert keys
    assert not any(key in text for text in outputs for key in [*keys, "entry_key"])
    # The instruction file holds a sentinel on its secret line, and it never shows.
    assert "SENTINEL_SECRET_INSTRUCTIONS" in (home / ".claude/CLAUDE.md").read_text()
    assert not any("SENTINEL_SECRET_INSTRUCTIONS" in text for text in outputs)
    assert network_attempts == []


def _demo_outputs(home) -> list[str]:
    """Every page answer of the demo on a sample: the reads for all projects and each one, every
    Library tab, Details of each item with a secret and each instruction file, the held servers'
    tools, and the changes that show an entry with a secret (remove, and moving to the Keychain)."""
    outputs: list[str] = []
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")

        def get(path):
            response = page.get(path)
            assert response.status_code == 200, (path, response.text)
            outputs.append(response.text)
            return response.json()

        def post(path, body=None):
            response = page.post(path, json=body, headers=POST)
            assert response.status_code == 200, (path, response.text)
            outputs.append(response.text)
            return response.json()

        for path in ["/api/clients", "/api/items", "/api/projects", "/api/problems"]:
            get(path)
        for path in ["/api/changes", "/api/gateways", "/api/about"]:
            get(path)
        projects = page.get("/api/projects").json()
        for project in [None, *projects]:
            query = f"?project={project['id']}" if project else ""
            for path in [
                "/api/overview",
                "/api/map",
                "/api/gateway-view",
                "/api/library-map",
                "/api/instructions-map",
            ]:
                get(path + query)
            get("/api/findings" + (f"?project={quote(project['path'])}" if project else ""))
        for kind in KINDS:
            for project in [None, projects[0]]:
                get(f"/api/library?kind={kind}" + (f"&project={project['id']}" if project else ""))
        for tab in ("plugin", "instructions"):
            for project in [None, projects[0]]:
                where = f"&project={project['id']}" if project else ""
                get(f"/api/library-list?kind={tab}&show=diff{where}")
        items = page.get("/api/items").json()
        explained = {
            (i["name"], i["kind"])
            for i in items
            if i["secret_present"] or i["kind"] == "instructions"
        }
        for name, kind in sorted(explained):
            get(f"/api/explain?name={quote(name)}&kind={kind}")
        held = load_settings(home)["servers"]
        for server in held:
            get(f"/api/gateway/tools?server={quote(server)}")
        changes = []
        for item in page.get("/api/items?kind=mcp_server").json():
            user_level = item["client"] != "claude_code" or item["scope"] == "user"
            if item["secret_present"] and "mcp.remove_direct" in item["actions"] and user_level:
                body = {"action": "mcp.remove_direct", "targets": [{"item": item["id"]}]}
                changes.append(post("/api/changes/preview", {**body, "params": {}}))
        assert changes
        for change in changes:
            assert post(f"/api/changes/{change['id']}/apply")["state"] == "verified"
            assert post(f"/api/changes/{change['id']}/undo")["state"] == "undone"
        if "files" in held:  # medium and large: its token is kept plain
            body = {"action": "gateway.keychain", "targets": [], "params": {"server": "files"}}
            post("/api/changes/preview", body)
        # The Changes page now lists them.
        assert len(get("/api/changes")) >= len(changes)
    return outputs


@pytest.mark.anyio
@pytest.mark.parametrize("size", SIZES)
async def test_no_demo_secret_in_any_output_of_a_sample(tmp_path, size, network_attempts):
    home = build_demo_home(tmp_path, size)
    written = "".join(
        p.read_text(errors="ignore")
        for p in tmp_path.rglob("*")
        if p.is_file() and not p.is_symlink()
    )
    assert written.count(DEMO_SECRET) >= {"small": 2, "medium": 6, "large": 6}[size]
    outputs = _demo_outputs(home)
    store = data_dir(home)
    outputs.append((store / "changes.log").read_text())
    outputs += [p.read_text() for p in store.glob("changes/*/manifest.json")]
    for record in store.glob("changes/*/change.json"):
        outputs.append(json.dumps([s["command"] for s in json.loads(record.read_text())["steps"]]))
    build = demo_build(home)
    names = sorted(
        {i.name for i in build().items if i.secret_present or str(i.kind) == "instructions"}
    )
    outputs += await _mcp_outputs(build, home, names)
    assert [text for text in outputs if DEMO_SECRET in text] == []
    assert network_attempts == []


@pytest.mark.parametrize(
    "entry",
    [
        {"command": "npx", "args": ["files-mcp"], "env": {"FILES_TOKEN": "SENTINEL_SECRET_ENV"}},
        {"type": "http", "url": "https://x.test/mcp", "headers": {"X-Key": "SENTINEL_SECRET_H"}},
        {"command": "npx", "args": ["files-mcp", "--token", "SENTINEL_SECRET_ARG"]},
        {"type": "http", "url": "https://x.test/mcp?api_key=SENTINEL_SECRET_URL"},
    ],
)
def test_no_client_command_carries_a_secret(home, entry):
    """A command's arguments are visible to `ps` while it runs: a secret never goes there."""
    for adapter in default_adapters(home, quick=True):
        step = adapter.add_server_step("files", entry)
        assert step.edit is not None and step.edit.after == entry
        for command in (step.command, step.undo_command):
            assert "SENTINEL" not in json.dumps(command), adapter.id


@pytest.mark.parametrize(
    "source",
    [
        "https://me:SENTINEL_SECRET_PW@git.example.test/market.git",
        "https://git.example.test/market.git?token=SENTINEL_SECRET_Q",
        "https://x-access-token:ghp_SENTINELSECRETTOKEN0123@github.com/team/market",
    ],
)
def test_a_marketplace_source_with_a_secret_is_not_put_in_a_command(home, source):
    """`marketplace add <source>` shows its source to `ps`: one with a secret is refused."""
    for adapter in default_adapters(home, quick=True):
        if adapter.id not in ("claude_code", "codex"):
            continue
        words = "Claude Code" if adapter.id == "claude_code" else "Codex"
        reason = f"Its source holds a password or token; add it in {words} by hand."
        with pytest.raises(ValueError) as refused:
            adapter.marketplace_add_step("market", source)
        assert str(refused.value) == reason
        assert "SENTINEL" not in reason


def test_a_plain_marketplace_source_still_runs_the_command(home):
    for adapter in default_adapters(home, quick=True):
        if adapter.id in ("claude_code", "codex"):
            step = adapter.marketplace_add_step("market", "team/market")
            assert step.command is not None and "team/market" in step.command
