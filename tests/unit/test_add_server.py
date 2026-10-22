"""Add a direct MCP server one client has to another client (spec 3.4)."""

import json
import tomllib

import pytest

import kitden.clients.base as base
from kitden.gateways import data_dir
from tests.conftest import make_home, write_cursor_fixture_state
from tests.unit.test_api_changes import FakeClaude
from tests.unit.test_local_gateway_move import add_claude, add_cursor
from tests.unit.test_local_gateway_views import POST, add_kitden, page_for


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "read_command_version", lambda client: None)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    return home


def _add(page, item_id, *clients):
    body = {
        "action": "mcp.add",
        "targets": [{"client": c} for c in clients],
        "params": {"item": item_id},
    }
    return page.post("/api/changes/preview", json=body, headers=POST)


def _item(page, who, name, scope="user"):
    items = page.get("/api/items?kind=mcp_server").json()
    return next(i for i in items if (i["client"], i["name"], i["scope"]) == (who, name, scope))


def _rows(page):
    return {r["name"]: r for r in page.get("/api/library?kind=mcp_server").json()["rows"]}


def test_the_library_offers_add_for_a_direct_server_another_client_lacks(home):
    with page_for(home) as page:
        rows = _rows(page)
        github = _item(page, "claude_code", "github")["id"]
        for client in ("codex", "cursor"):
            add = rows["github"]["cells"][client]["add"]
            assert (add["action"], add["label"], add["item"]) == ("mcp.add", "+ Add", github)
            assert rows["github"]["cells"][client]["reason"] is None
        n8n = _item(page, "cursor", "n8n-mcp")["id"]  # a local server is copied too
        assert rows["n8n-mcp"]["cells"]["claude_code"]["add"]["item"] == n8n
        # Names match exactly: Cursor's Neon is not Codex's neon.
        neon = _item(page, "codex", "neon")["id"]
        assert rows["neon"]["cells"]["cursor"]["add"]["item"] == neon
        # A server that is turned off has no source to copy.
        assert rows["aseprite"]["cells"]["claude_code"]["add"] is None
        # A project entry is shown only in a project view; it is no source.
        assert "docs" not in rows


def test_adding_a_server_to_another_client_previews_applies_and_undoes(home):
    config = home / ".codex/config.toml"
    before = config.read_bytes()
    with page_for(home) as page:
        change = _add(page, _item(page, "claude_code", "github")["id"], "codex").json()
        assert [(s["client"], s["name"]) for s in change["steps"]] == [("codex", "github")]
        assert "http_headers" in change["steps"][0]["diff"]
        assert "[secret]" in change["steps"][0]["diff"]
        assert "SENTINEL" not in json.dumps(change)
        assert change["after"] == [
            {
                "client": "codex",
                "state": "on",
                "word": "Loads",
                "note": "This makes a second copy of a secret in ~/.codex/config.toml.",
            }
        ]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        assert "SENTINEL" not in json.dumps(applied)
        text = config.read_text()
        assert tomllib.loads(text)["mcp_servers"]["github"] == {
            "url": "https://api.githubcopilot.com/mcp/",
            "http_headers": {"Authorization": "Bearer SENTINEL_SECRET_GITHUB"},
        }
        assert "# Owner comment: keep me" in text
        assert _rows(page)["github"]["cells"]["codex"]["state"] == "on"
        assert "SENTINEL" not in page.get("/api/changes").text
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
    assert config.read_bytes() == before
    records = list((data_dir(home) / "changes").glob("*/change.json"))
    assert records and all(
        "SENTINEL" not in json.dumps([s.get("command") for s in json.loads(r.read_text())["steps"]])
        for r in records
    )


def test_a_codex_entry_goes_to_claude_code_with_its_type(home):
    original = (home / ".claude.json").read_bytes()
    with page_for(home, run=FakeClaude(home)) as page:
        change = _add(page, _item(page, "codex", "neon")["id"], "claude_code", "cursor").json()
        assert change["steps"][0]["command"] == (
            'claude mcp add-json -s user neon {"type": "http", "url": "https://mcp.neon.tech/mcp"}'
        )
        assert [a["client"] for a in change["after"]] == ["claude_code", "cursor"]
        assert all("note" not in a for a in change["after"])  # no secret in it
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified"
        cursor = json.loads((home / ".cursor/mcp.json").read_text())["mcpServers"]
        assert cursor["neon"] == {"url": "https://mcp.neon.tech/mcp"}
        assert cursor["Neon"] == {"url": "https://mcp.neon.tech/mcp"}  # its own entry stays
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone"
    assert (home / ".claude.json").read_bytes() == original


def test_a_reference_is_kept_or_refused(home):
    add_claude(
        home,
        "api",
        {
            "type": "http",
            "url": "https://api.invalid/mcp",
            "headers": {"Authorization": "Bearer ${API_KEY}"},
        },
    )
    add_claude(home, "shelled", {"type": "stdio", "command": "npx", "args": ["x", "${TOKEN}"]})
    with page_for(home) as page:
        change = _add(page, _item(page, "claude_code", "api")["id"], "codex").json()
        assert "bearer_token_env_var" in change["steps"][0]["diff"]
        assert "note" not in change["after"][0]  # a reference is no secret
        refused = _add(page, _item(page, "claude_code", "shelled")["id"], "codex")
        assert (refused.status_code, refused.json()["detail"]) == (
            422,
            "Codex cannot read `${TOKEN}` from your shell; put the value in.",
        )


def test_project_entries_and_kitdens_own_entry_are_refused(home):
    add_kitden(home, "claude_code")
    per_project = "It is already per project; copy the file into the project instead."
    with page_for(home) as page:
        docs = _item(page, "claude_code", "docs", scope="project")
        answer = _add(page, docs["id"], "codex")
        assert (answer.status_code, answer.json()["detail"]) == (422, per_project)
        local = _item(page, "claude_code", "local-db", scope="local")
        assert _add(page, local["id"], "codex").json()["detail"] == per_project
        kitden = _item(page, "claude_code", "kitden")
        assert _add(page, kitden["id"], "codex").json()["detail"] == (
            "Kitden's own entry stays in each client."
        )
        rows = _rows(page)
        assert all(c["add"] is None for c in rows["kitden"]["cells"].values())


def test_an_unknown_item_or_no_client_is_refused(home):
    with page_for(home) as page:
        github = _item(page, "claude_code", "github")["id"]
        none = _add(page, github)
        assert (none.status_code, none.json()["detail"]) == (422, "Choose at least one client")
        unknown = _add(page, "nope", "codex")
        assert unknown.status_code == 422


def test_a_name_the_client_has_is_refused(home):
    add_cursor(home, "github", {"url": "https://other.invalid/mcp"})
    before = (home / ".cursor/mcp.json").read_bytes()
    with page_for(home) as page:
        answer = _add(page, _item(page, "claude_code", "github")["id"], "cursor")
    assert (answer.status_code, answer.json()["detail"]) == (422, "Cursor already has github.")
    assert (home / ".cursor/mcp.json").read_bytes() == before
