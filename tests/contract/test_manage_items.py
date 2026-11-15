"""Adding and removing items through the page with the real clients, in a sandbox home
(checks 8, 11 to 16 and part of 22 of "Check before a release" in docs/development.md).

The plugin is this repository's own, `kitden@kitden`, from a copy of the checkout's marketplace
whose source is the checkout's plugins/kitden (`checkout_marketplace`): the clients copy the
plugin from that folder and clone nothing. "The client's list" is `claude plugin list --json`
or `codex plugin list --json`. No client is signed in, and the real home folder is never
touched. Run with: pytest -m contract
"""

import json
import os
import subprocess
import tomllib
from contextlib import ExitStack
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kitden.changes.backup import ChangeStore
from kitden.gateways import data_dir
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.contract.conftest import checkout_marketplace, need_command

pytestmark = pytest.mark.contract
ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
PLUGIN = "kitden@kitden"
# A closed port on this computer: a client that tries the server fails at once, offline too.
URL = "http://127.0.0.1:9/mcp"
TOKEN = "SENTINEL_SECRET_NOTES_TOKEN"


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A home with two projects both clients know, and the checkout's marketplace in both."""
    need_command("claude", tmp_path)
    need_command("codex", tmp_path)
    for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(name, raising=False)
    home = tmp_path / "home"
    projects = [home / "work/site", home / "work/other"]
    for folder in projects:
        (folder / ".claude").mkdir(parents=True)
    (home / ".claude").mkdir()
    (home / ".claude/settings.json").write_text("{}\n")
    known = {str(f): {"hasTrustDialogAccepted": True} for f in projects}
    (home / ".claude.json").write_text(json.dumps({"projects": known}, indent=2))
    (home / ".codex").mkdir()
    trust = "".join(f'[projects."{f}"]\ntrust_level = "trusted"\n\n' for f in projects)
    (home / ".codex/config.toml").write_text(trust)
    market = str(checkout_marketplace(tmp_path / "market"))
    client(home, "claude", "plugin", "marketplace", "add", market)
    client(home, "codex", "plugin", "marketplace", "add", market, "--json")
    return home


def client(home: Path, name: str, *args: str, cwd: Path | None = None, check: bool = True):
    """Run the real client in the sandbox home, in `cwd` or the home."""
    done = subprocess.run(
        [need_command(name, home), *args],
        env={**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")},
        cwd=cwd or home,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if check:
        assert done.returncode == 0, f"{name} {args}: {done.stdout}\n{done.stderr}"
    return done


def claude_list(home: Path, cwd: Path | None = None) -> dict[tuple[str, str], dict]:
    """Claude Code's list read in `cwd`, by (id, scope)."""
    listed = json.loads(client(home, "claude", "plugin", "list", "--json", cwd=cwd).stdout)
    return {(p["id"], p["scope"]): p for p in listed}


def codex_list(home: Path) -> dict[str, dict]:
    """Codex's installed plugins, by id."""
    listed = json.loads(client(home, "codex", "plugin", "list", "--json").stdout)
    return {p["pluginId"]: p for p in listed.get("installed", [])}


def listed(home: Path, name: str) -> dict[str, bool]:
    """The client's list as id -> on, for the user."""
    if name == "codex":
        return {i: bool(p.get("enabled")) for i, p in codex_list(home).items()}
    return {i: bool(p["enabled"]) for (i, scope), p in claude_list(home).items() if scope == "user"}


def loaded_in(home: Path, folder: Path) -> set[tuple[str, str]]:
    """What Claude Code's list, read in `folder`, says is on there: (id, scope)."""
    return {key for key, p in claude_list(home, folder).items() if p.get("projectEnabled")}


def config(home: Path) -> dict:
    return tomllib.loads((home / ".codex/config.toml").read_text())


def install(home: Path, name: str) -> None:
    """The plugin installed for the user with the client's own command."""
    if name == "codex":
        client(home, "codex", "plugin", "add", PLUGIN, "--json")
    else:
        client(home, "claude", "plugin", "install", PLUGIN, "-s", "user")


@pytest.fixture
def page(home):
    """The local page on the sandbox home, as `kitden open` serves it. Open it after the setup:
    its first scan sees what the clients wrote."""

    with ExitStack() as stack:

        def open_page() -> TestClient:
            app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
            opened = stack.enter_context(TestClient(app, base_url=ORIGIN, follow_redirects=False))
            opened.get("/?token=tok")
            return opened

        yield open_page


def preview(page, body: dict) -> dict:
    done = page.post("/api/changes/preview", json=body, headers=POST)
    assert done.status_code == 200, done.text
    return done.json()


def apply(page, change: dict) -> None:
    applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
    assert applied["state"] == "verified", applied.get("error")


def undo(page, change: dict) -> None:
    undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
    assert undone["state"] == "undone", undone.get("error")


def item_id(page, client_id: str, kind: str, name: str, scope: str = "user") -> str:
    items = page.get(f"/api/items?client={client_id}&kind={kind}&scope={scope}").json()
    return next(i["id"] for i in items if i["name"] == name)


def project_id(page, folder: Path) -> str:
    return next(p["id"] for p in page.get("/api/projects").json() if p["path"] == str(folder))


def remove_plugin(page, client_id: str, scope: str = "user") -> dict:
    target = {"item": item_id(page, client_id, "plugin", PLUGIN, scope)}
    change = preview(page, {"action": "plugin.remove", "targets": [target], "params": {}})
    apply(page, change)
    return change


CLIENTS = {"claude_code": "claude", "codex": "codex"}


@pytest.mark.parametrize("client_id", list(CLIENTS))
def test_a_removed_plugin_leaves_the_clients_list_and_undo_brings_it_back(home, page, client_id):
    name = CLIENTS[client_id]
    install(home, name)
    assert listed(home, name)[PLUGIN] is True
    page = page()

    change = remove_plugin(page, client_id)
    assert PLUGIN not in listed(home, name)

    undo(page, change)
    assert listed(home, name)[PLUGIN] is True


def turn_off(home: Path, name: str) -> None:
    """Claude Code's own command; Codex has none, so its table in config.toml says false."""
    if name == "codex":
        path = home / ".codex/config.toml"
        on = f'[plugins."{PLUGIN}"]\nenabled = true\n'
        assert on in path.read_text(), (
            "Codex's formatting of config.toml changed: no plugin table written as expected"
        )
        path.write_text(path.read_text().replace(on, on.replace("true", "false")))
    else:
        client(home, "claude", "plugin", "disable", PLUGIN, "-s", "user")


@pytest.mark.parametrize("client_id", list(CLIENTS))
def test_a_removed_off_plugin_comes_back_off(home, page, client_id):
    name = CLIENTS[client_id]
    install(home, name)
    turn_off(home, name)
    assert listed(home, name)[PLUGIN] is False
    page = page()

    change = remove_plugin(page, client_id)
    assert PLUGIN not in listed(home, name)

    undo(page, change)
    assert listed(home, name)[PLUGIN] is False


def test_a_project_only_plugin_is_uninstalled_in_its_project(home, page):
    site, other = home / "work/site", home / "work/other"
    client(home, "claude", "plugin", "install", PLUGIN, "-s", "project", cwd=site)
    assert (PLUGIN, "project") in loaded_in(home, site)
    page = page()
    seen_in_other = loaded_in(home, other)

    change = remove_plugin(page, "claude_code", scope="project")
    (step,) = change["steps"]
    assert step["command"].startswith(f"claude plugin uninstall {PLUGIN} -s project")
    (record,) = [r for r in ChangeStore(data_dir(home)).load() if r["id"] == change["id"]]
    assert record["steps"][0]["cwd"] == str(site)
    assert (PLUGIN, "project") not in loaded_in(home, site)
    seen_in_other |= loaded_in(home, other)

    undo(page, change)
    assert (PLUGIN, "project") in loaded_in(home, site)
    seen_in_other |= loaded_in(home, other)
    assert not {key for key in seen_in_other if key[0] == PLUGIN}


def test_codex_remove_deletes_the_plugins_table_and_add_writes_it_back(home, page):
    install(home, "codex")
    page = page()

    change = remove_plugin(page, "codex")
    assert PLUGIN not in config(home).get("plugins", {})

    undo(page, change)
    assert config(home)["plugins"][PLUGIN] == {"enabled": True}


def test_add_missing_adds_a_plugin_and_a_server_together_and_undo_removes_both(home, page):
    install(home, "claude")
    entry = json.dumps({"type": "stdio", "command": "echo", "args": ["notes"]})
    client(home, "claude", "mcp", "add-json", "-s", "user", "notes", entry)
    page = page()
    site = project_id(page, home / "work/site")
    chosen = [f"plugin:{PLUGIN}:codex", "mcp_server:notes:codex"]
    body = {"action": "project.align", "targets": [], "params": {"project": site, "chosen": chosen}}

    change = preview(page, body)
    apply(page, change)
    assert codex_list(home)[PLUGIN]["enabled"] is True
    assert PLUGIN in config(home)["plugins"]
    assert "notes" in config(home)["mcp_servers"]

    undo(page, change)
    assert PLUGIN not in codex_list(home)
    assert PLUGIN not in config(home).get("plugins", {})
    assert "notes" not in config(home).get("mcp_servers", {})
    servers = json.loads(client(home, "codex", "mcp", "list", "--json").stdout)
    assert "notes" not in {s["name"] for s in servers}


def test_add_to_this_project_shows_in_that_folder_only(home, page):
    site, other = home / "work/site", home / "work/other"
    page = page()
    params = {"plugin": PLUGIN, "project": project_id(page, site)}
    body = {"action": "plugin.install", "targets": [{"client": "claude_code"}], "params": params}

    change = preview(page, body)
    apply(page, change)
    assert (PLUGIN, "project") in loaded_in(home, site)
    assert not {key for key in loaded_in(home, other) if key[0] == PLUGIN}
    assert (PLUGIN, "user") not in claude_list(home, other)


def test_a_server_with_a_variable_header_is_listed_by_codex_with_the_variable(home, page):
    headers = {"Authorization": "Bearer ${NOTES_TOKEN}", "X-Team": "${NOTES_TEAM}"}
    entry = json.dumps({"type": "http", "url": URL, "headers": headers})
    client(home, "claude", "mcp", "add-json", "-s", "user", "notes", entry)
    page = page()
    target = item_id(page, "claude_code", "mcp_server", "notes")
    body = {"action": "mcp.add", "targets": [{"client": "codex"}], "params": {"item": target}}

    change = preview(page, body)
    apply(page, change)
    done = subprocess.run(
        [need_command("codex", home), "mcp", "list", "--json"],
        env={**os.environ, "HOME": str(home), "NOTES_TOKEN": TOKEN, "NOTES_TEAM": TOKEN},
        cwd=home,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    (server,) = [s for s in json.loads(done.stdout) if s["name"] == "notes"]
    assert server["transport"]["url"] == URL
    assert "NOTES_TOKEN" in done.stdout and "NOTES_TEAM" in done.stdout
    assert TOKEN not in done.stdout


def test_an_entry_kitden_wrote_itself_survives_the_clients_own_write(home, page):
    config_file = home / ".codex/config.toml"
    header = f'http_headers = {{ Authorization = "Bearer {TOKEN}" }}'
    config_file.write_text(
        config_file.read_text() + f'[mcp_servers.notes]\nurl = "{URL}"\n{header}\n'
    )
    page = page()
    target = item_id(page, "codex", "mcp_server", "notes")
    body = {"action": "mcp.add", "targets": [{"client": "claude_code"}], "params": {"item": target}}

    change = preview(page, body)
    (step,) = change["steps"]
    assert step["command"] is None  # Kitden's own edit: the token is in no command's arguments
    apply(page, change)
    other = json.dumps({"type": "stdio", "command": "echo", "args": ["other"]})
    client(home, "claude", "mcp", "add-json", "-s", "user", "other", other)
    assert URL in client(home, "claude", "mcp", "get", "notes").stdout
    kept = json.loads((home / ".claude.json").read_text())["mcpServers"]["notes"]
    assert kept["headers"] == {"Authorization": f"Bearer {TOKEN}"}

    undo(page, change)
    assert client(home, "claude", "mcp", "get", "notes", check=False).returncode != 0
    assert "other" in json.loads((home / ".claude.json").read_text())["mcpServers"]
    client(home, "claude", "mcp", "get", "other")
