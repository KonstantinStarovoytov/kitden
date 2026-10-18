"""Secret and network sweep (T063, SC-004, FR-006, FR-038).

Runs every output path with fixtures full of SENTINEL_SECRET_ values: page responses (including
change previews of entries that hold secrets), the change log and backup manifests,
`scan --json`, and every MCP tool. No sentinel may appear, and the tool's own process must not
open a network connection. Client commands the tool starts (for example `--version`) are separate
programs and are replaced by stand-ins here.
"""

import json
import socket

import pytest
from mcp import Client
from starlette.testclient import TestClient

import kitden.cli as cli
import kitden.clients.base as base
from kitden.gateways import data_dir
from kitden.mcp_server import create_server
from kitden.views.inventory import build_inventory
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
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
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
        assert len(changes) >= 5
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
        ]:
            outputs.append(page.get(path).text)
        for item in page.get("/api/items?kind=mcp_server").json():
            outputs.append(page.get(f"/api/explain?name={item['name']}&kind=mcp_server").text)
        for project in page.get("/api/projects").json():
            outputs.append(page.get(f"/api/projects/{project['id']}/effective").text)
            outputs.append(page.get(f"/api/findings?project={project['path']}").text)
        for item in page.get("/api/items").json():
            if item["kind"] in ("plugin", "marketplace"):
                outputs.append(page.get(f"/api/commands?item={item['id']}").text)
    return outputs


async def _mcp_outputs(home) -> list[str]:
    server = create_server(lambda: build_inventory(home), cwd=lambda: str(home))
    outputs = []
    async with Client(server) as client:
        projects = (await client.call_tool("list_projects", {})).structured_content["projects"]
        calls = [("list_projects", {}), ("show_setup", {}), ("list_findings", {})]
        for project in projects:
            calls += [
                ("show_setup", {"project_path": project["path"]}),
                ("list_findings", {"project_path": project["path"]}),
            ]
        for name in ["github", "local-db", "langfuse-data", "n8n-mcp"]:
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
    outputs = _page_outputs(home)
    store = data_dir(home)
    outputs.append((store / "changes.log").read_text())
    outputs += [p.read_text() for p in store.glob("changes/*/manifest.json")]

    cli.main(["scan", "--json", "--home", str(home)])
    outputs.append(capsys.readouterr().out)

    outputs += await _mcp_outputs(home)

    leaked = [text for text in outputs if "SENTINEL" in text]
    assert leaked == []
    assert network_attempts == []
