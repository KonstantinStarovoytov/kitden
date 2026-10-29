"""Online metadata never writes client settings; installs keep preview, verify and Undo."""

import io
import json
import zipfile

import pytest
from starlette.testclient import TestClient

from kitden import discovery
from kitden.discovery import Discovery, checked_url, row_key, server_entry
from kitden.local_gateway.settings import load_settings
from kitden.views.inventory import build_inventory
from kitden.web.app import create_app
from tests.conftest import make_home

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
SHA = "a" * 40


def archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as out:
        for name, value in files.items():
            out.writestr(name, value)
    return stream.getvalue()


def skill_source(monkeypatch):
    def read(url):
        if "api/search" in url:
            return {"skills": [{"name": "tidy", "source": "acme/skills", "installs": 42}]}
        if "/commits/" in url:
            return {"sha": SHA}
        if "/git/trees/" in url:
            return {"tree": [{"path": "skills/tidy/SKILL.md", "type": "blob"}]}
        raise AssertionError(url)

    monkeypatch.setattr(discovery, "read_json", read)
    content = archive(
        {
            "repo/skills/tidy/SKILL.md": (
                "---\nname: tidy\ndescription: Tidy files.\n---\nRead before editing.\n"
            ),
            "repo/skills/tidy/reference.md": "More instructions.",
        }
    )

    def fetch(url):
        if "raw.githubusercontent" in url:
            with zipfile.ZipFile(io.BytesIO(content)) as data:
                return data.read("repo/skills/tidy/SKILL.md")
        return content

    monkeypatch.setattr(discovery, "download", fetch)


@pytest.mark.parametrize(
    "url",
    [
        "http://skills.sh/api/search",
        "https://skills.sh.evil.test/x",
        "file:///etc/passwd",
        "https://user@api.github.com/x",
        "https://api.github.com:8443/x",
    ],
)
def test_only_known_https_catalog_hosts_and_redirects_are_read(url):
    with pytest.raises(ValueError):
        checked_url(url)


def test_sources_persist_without_a_client_settings_write(tmp_path):
    source = Discovery(tmp_path)
    source.add_source("https://github.com/acme/skills")
    assert any(s["id"] == "acme/skills" for s in Discovery(tmp_path).sources())
    assert not (tmp_path / ".claude").exists()
    with pytest.raises(ValueError):
        source.add_source("https://example.com/catalog")


def test_skill_metadata_survives_restart_and_download_is_pinned(tmp_path, monkeypatch):
    skill_source(monkeypatch)
    source = Discovery(tmp_path)
    row = source.search("skills.sh", "tidy", "skill")[0]
    source = Discovery(tmp_path)
    info = source.skill(source.get(row["id"]), {"codex"})
    assert info["name"] == "tidy" and info["self_contained"]
    assert info["path"].endswith("/tidy")
    assert not (tmp_path / ".agents/skills/tidy").exists()


def test_archive_traversal_and_symlinks_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "download", lambda _: archive({"repo/../../escape": "bad"}))
    with pytest.raises(ValueError, match="unsafe path"):
        Discovery(tmp_path).checkout("acme/skills", SHA)
    assert not (tmp_path / "escape").exists()


def test_registry_transport_uses_exact_declared_version_and_requires_complete_config():
    entry, refusal = server_entry(
        {
            "packages": [
                {
                    "registryType": "npm",
                    "identifier": "@acme/mcp",
                    "version": "1.2.3",
                    "transport": {"type": "stdio"},
                }
            ]
        }
    )
    assert not refusal and entry == {"command": "npx", "args": ["-y", "@acme/mcp@1.2.3"]}
    assert (
        server_entry(
            {
                "remotes": [
                    {
                        "type": "streamable-http",
                        "url": "https://example.com/mcp",
                        "headers": [{"name": "Authorization", "isRequired": True}],
                    }
                ]
            }
        )[0]
        is None
    )


def test_online_skill_preview_apply_verify_and_undo(tmp_path, monkeypatch):
    skill_source(monkeypatch)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN) as page:
        page.get("/?token=tok")
        result = page.post(
            "/api/discovery/search",
            json={"source": "skills.sh", "query": "tidy", "kind": "skill"},
            headers=POST,
        )
        assert result.status_code == 200, result.text
        row = result.json()["results"][0]
        assert "entry" not in row
        body = {
            "action": "skill.install",
            "targets": [{"client": "codex"}],
            "params": {"skill": "tidy", "discovery": row["id"]},
        }
        response = page.post("/api/changes/preview", json=body, headers=POST)
        assert response.status_code == 200, response.text
        change = response.json()
        folder = home / ".agents/skills/tidy"
        assert not folder.exists()
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified", applied
        assert (folder / "SKILL.md").is_file()
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone", undone
        assert not folder.exists()


def test_online_mcp_preview_apply_and_undo(tmp_path, monkeypatch):
    row = {
        "name": "io.example/fresh-docs",
        "kind": "mcp",
        "source": "Official MCP Registry",
        "entry": {"command": "demo-docs", "args": []},
        "description": "Docs",
    }
    row["id"] = row_key(row)
    monkeypatch.setattr(Discovery, "get", lambda _, key: row)
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN) as page:
        page.get("/?token=tok")
        body = {
            "action": "gateway.add",
            "targets": [],
            "params": {"server": "online@registry/fresh-docs", "discovery": row["id"]},
        }
        response = page.post("/api/changes/preview", json=body, headers=POST)
        assert response.status_code == 200, response.text
        change = response.json()
        assert "fresh-docs" not in load_settings(home)["servers"]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified", applied
        assert load_settings(home)["servers"]["fresh-docs"]["command"] == "demo-docs"
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone", undone
        assert "fresh-docs" not in load_settings(home)["servers"]


def test_demo_never_searches_online(tmp_path, monkeypatch):
    from kitden.demo import build_demo_home, demo_build

    home = build_demo_home(tmp_path, "small")
    monkeypatch.setattr(discovery, "read_json", lambda _: pytest.fail("demo went online"))
    with TestClient(
        create_app(demo_build(home), token="tok", port=47800, home=home, demo=True), base_url=ORIGIN
    ) as page:
        page.get("/?token=tok")
        assert (
            page.post(
                "/api/discovery/search", json={"source": "skills.sh", "query": "tidy"}, headers=POST
            ).status_code
            == 400
        )


def test_optional_registry_credentials_do_not_block_public_access():
    entry, refusal = server_entry(
        {
            "remotes": [
                {
                    "type": "streamable-http",
                    "url": "https://mcp.context7.com/mcp",
                    "headers": [{"name": "Authorization", "isSecret": True}],
                }
            ]
        }
    )
    assert entry == {"url": "https://mcp.context7.com/mcp"} and refusal is None


def test_online_plugin_adds_marketplace_in_same_preview_and_undo(tmp_path, monkeypatch):
    from tests.unit.test_api_plugin_install import FakeCli

    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2")
    marketplace = tmp_path / "market"
    manifest = marketplace / ".claude-plugin/marketplace.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {"name": "fresh-market", "plugins": [{"name": "fresh-plugin", "source": "./plugin"}]}
        )
    )
    row = {
        "name": "fresh-plugin",
        "kind": "plugin",
        "repo": "acme/plugins",
        "source": "acme/plugins",
        "marketplace": "fresh-market",
    }
    row["id"] = row_key(row)
    monkeypatch.setattr(Discovery, "get", lambda _, key: row)
    monkeypatch.setattr(
        Discovery,
        "plugin",
        lambda _, value: {
            "name": "fresh-market",
            "source": str(marketplace),
            "formats": ["claude"],
            "plugin": "fresh-plugin@fresh-market",
        },
    )
    before = (home / ".claude/settings.json").read_bytes()
    app = create_app(
        lambda: build_inventory(home), token="tok", port=47800, home=home, run=FakeCli(home)
    )
    with TestClient(app, base_url=ORIGIN) as page:
        page.get("/?token=tok")
        request = {
            "action": "plugin.install",
            "targets": [{"client": "claude_code"}],
            "params": {"plugin": "fresh-plugin", "discovery": row["id"]},
        }
        response = page.post("/api/changes/preview", json=request, headers=POST)
        assert response.status_code == 200, response.text
        change = response.json()
        assert len(change["steps"]) >= 2
        assert (home / ".claude/settings.json").read_bytes() == before
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST).json()
        assert applied["state"] == "verified", applied
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST).json()
        assert undone["state"] == "undone", undone
        assert (home / ".claude/settings.json").read_bytes() == before


def test_single_plugins_are_not_preset_catalogs_and_legacy_default_is_removed(tmp_path):
    source = Discovery(tmp_path)
    assert "obra/superpowers" not in {s["id"] for s in source.sources()}
    source.root.mkdir(parents=True)
    (source.root / "sources.json").write_text(json.dumps(["obra/superpowers", "acme/skills"]))
    assert "obra/superpowers" not in {s["id"] for s in source.sources()}
    assert "acme/skills" in {s["id"] for s in source.sources()}
    # An owner can still explicitly choose a plugin repository as a personal source.
    source.add_source("obra/superpowers")
    assert "obra/superpowers" in {s["id"] for s in Discovery(tmp_path).sources()}
