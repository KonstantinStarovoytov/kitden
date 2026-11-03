"""Online metadata never writes client settings; installs keep preview, verify and Undo."""

import io
import json
import zipfile

import pytest
from starlette.testclient import TestClient

from kitden import discovery
from kitden.discovery import Discovery, checked_url, row_key, server_entry
from kitden.gateways import data_dir
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
    assert row["installs"] == 42
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


def test_custom_source_edit_remove_and_restore(tmp_path):
    source = Discovery(tmp_path)
    source.add_source("acme/skills")
    source.change_source("edit", "https://github.com/acme/plugins", "acme/skills")
    ids = {s["id"] for s in Discovery(tmp_path).sources()}
    assert "acme/plugins" in ids and "acme/skills" not in ids
    source.change_source("remove", "", "acme/plugins")
    assert "acme/plugins" not in {s["id"] for s in source.sources()}
    source.change_source("add", "acme/plugins", "")
    assert "acme/plugins" in {s["id"] for s in source.sources()}
    with pytest.raises(ValueError):
        source.change_source("remove", "", "skills.sh")


def test_popular_skills_uses_leaderboard_counts(tmp_path, monkeypatch):
    payload = "1:" + json.dumps(
        {
            "initialSkills": [
                {"name": "low", "source": "acme/skills", "installs": 2},
                {"name": "high", "source": "acme/skills", "installs": 100},
            ]
        }
    )
    page = "<script>self.__next_f.push(" + json.dumps([1, payload]) + ")</script>"
    monkeypatch.setattr(discovery, "download", lambda url: page.encode())
    rows = Discovery(tmp_path).search("skills.sh", "", "skill")
    assert [r["name"] for r in rows] == ["high", "low"]
    assert [r["installs"] for r in rows] == [100, 2]


@pytest.mark.parametrize("name", ["tidy", "old-name"])
def test_ambiguous_or_renamed_skill_offers_pinned_choices(tmp_path, monkeypatch, name):
    skill_source(monkeypatch)
    source = Discovery(tmp_path)
    row = source.search("skills.sh", "tidy", "skill")[0]
    source.results[row["id"]]["name"] = name
    source.trees["acme/skills"] = (SHA, ["one/tidy/SKILL.md", "two/tidy/SKILL.md"])
    choices = source.details(row["id"])["choices"]
    assert [c["path"] for c in choices] == ["one/tidy", "two/tidy"]
    assert all(c["commit"] == SHA for c in choices)
    reopened = Discovery(tmp_path)
    assert reopened.get(choices[1]["id"])["path"] == "two/tidy"
    with pytest.raises(ValueError, match="choose a folder"):
        source.skill(source.get(row["id"]), {"codex"})
    assert not (tmp_path / ".agents").exists()


def test_missing_skill_does_not_claim_multiple_matches(tmp_path, monkeypatch):
    skill_source(monkeypatch)
    source = Discovery(tmp_path)
    row = source.search("skills.sh", "tidy", "skill")[0]
    source.trees["acme/skills"] = (SHA, ["README.md"])
    with pytest.raises(ValueError, match="no longer contains"):
        source.details(row["id"])


def test_details_pin_exact_folder_and_can_read_after_restart(tmp_path, monkeypatch):
    skill_source(monkeypatch)
    source = Discovery(tmp_path)
    row = source.search("skills.sh", "tidy", "skill")[0]
    detail = source.details(row["id"])
    assert detail["path"] == "skills/tidy"
    assert detail["commit"] == SHA
    assert detail["description"] == "Tidy files."
    reopened = Discovery(tmp_path)
    monkeypatch.setattr(reopened, "tree", lambda _: pytest.fail("must use pinned choice"))
    assert reopened.details(detail["id"])["content"] == detail["content"]


def test_root_skill_opens_and_previews_without_folder_choice(tmp_path, monkeypatch):
    skill_source(monkeypatch)
    source = Discovery(tmp_path)
    row = source.search("skills.sh", "tidy", "skill")[0]
    source.trees["acme/skills"] = (SHA, ["SKILL.md", "reference.md"])
    downloads = []
    content = archive(
        {
            "repo/SKILL.md": "---\nname: tidy\ndescription: Tidy files.\n---\nRead before editing.",
            "repo/reference.md": "Reference",
        }
    )

    def fetch(url):
        downloads.append(url)
        if "raw.githubusercontent" in url:
            return b"---\nname: tidy\ndescription: Tidy files.\n---\nRead before editing."
        return content

    monkeypatch.setattr(discovery, "download", fetch)
    detail = source.details(row["id"])
    assert "choices" not in detail
    assert detail["path"] == "."
    # A direct drag of the original search result resolves the same single folder.
    skill = source.skill(source.get(row["id"]), {"codex"})
    assert skill["name"] == "tidy"
    assert downloads == [
        f"https://raw.githubusercontent.com/acme/skills/{SHA}/SKILL.md",
        f"https://codeload.github.com/acme/skills/zip/{SHA}",
    ]
    assert (source.checkout("acme/skills", SHA, ".") / "reference.md").read_text() == "Reference"


def test_setup_fields_accept_declared_tokens_and_hide_them():
    from kitden.changes.batch import kept_request
    from kitden.discovery import configured_entry, server_setup

    entry, refusal, fields = server_setup(
        {
            "remotes": [
                {
                    "type": "streamable-http",
                    "url": "https://example.test/mcp",
                    "headers": [
                        {"name": "Authorization", "isRequired": True, "value": "Bearer {token}"}
                    ],
                }
            ]
        }
    )
    row = {"entry": entry, "setup": fields}
    assert refusal is None and fields[0]["prefix"] == "Bearer "
    from kitden.changes.actions import NeedsAccess

    with pytest.raises(NeedsAccess):
        configured_entry(row, {})
    params = {"headers": {"Authorization": "Bearer example-test-token"}}
    assert configured_entry(row, params)["headers"] == params["headers"]
    assert "headers" not in entry  # The cached public source never holds credentials.
    kept = kept_request([{"kind": "gateway.add", "targets": [], "params": params, "picked": None}])
    assert "example-test-token" not in json.dumps(kept)
    with pytest.raises(ValueError):
        configured_entry(row, {"headers": {"Host": "other.test"}})
    with pytest.raises(ValueError):
        configured_entry(row, {"headers": {"Authorization": "bad\r\nheader"}})


def test_registry_search_treats_spaces_as_hyphens(tmp_path, monkeypatch):
    queries = []

    def read(url):
        from urllib.parse import parse_qs, urlsplit

        term = parse_qs(urlsplit(url).query)["search"][0]
        queries.append(term)
        return {"servers": []}

    monkeypatch.setattr(discovery, "read_json", read)
    Discovery(tmp_path).search("mcp-registry", "agent docs", "mcp")
    assert queries == ["agent-docs", "agent docs"]
    assert discovery.words_match("agent docs", "io.github.example/agent-docs")
    assert discovery.words_match("Agent_Docs", "agent docs")


def test_token_preview_apply_and_undo_use_keychain(tmp_path, monkeypatch, fake_keychain):
    from kitden.changes import actions

    home = make_home(tmp_path, "codex/0.159.2")
    checked = []
    monkeypatch.setattr(
        actions, "access_needed", lambda url, headers: checked.append(headers) or "open"
    )
    monkeypatch.setattr(
        discovery,
        "read_json",
        lambda _: {
            "servers": [
                {
                    "_meta": {"io.modelcontextprotocol.registry/official": {"status": "active"}},
                    "server": {
                        "name": "test/token-server",
                        "remotes": [
                            {
                                "type": "streamable-http",
                                "url": "https://example.test/mcp",
                                "headers": [
                                    {
                                        "name": "Authorization",
                                        "isRequired": True,
                                        "value": "Bearer {token}",
                                    }
                                ],
                            }
                        ],
                    },
                }
            ]
        },
    )
    app = create_app(lambda: build_inventory(home), token="tok", port=47800, home=home)
    with TestClient(app, base_url=ORIGIN) as page:
        page.get("/?token=tok")
        row = page.post(
            "/api/discovery/search",
            json={
                "source": "mcp-registry",
                "query": "token",
                "kind": "mcp",
            },
            headers=POST,
        ).json()["results"][0]
        assert row["remote"] is True and "entry" not in row
        request = {
            "action": "gateway.add",
            "targets": [],
            "params": {
                "server": "online@registry/token-server",
                "discovery": row["id"],
                "headers": {"Authorization": "Bearer SENTINEL_TEST_TOKEN"},
            },
        }
        preview = page.post("/api/changes/preview", json=request, headers=POST)
        assert preview.status_code == 200, preview.text
        assert "SENTINEL_TEST_TOKEN" not in preview.text
        change = preview.json()
        assert checked == [{"Authorization": "Bearer SENTINEL_TEST_TOKEN"}]
        applied = page.post(f"/api/changes/{change['id']}/apply", headers=POST)
        assert applied.json()["state"] == "verified", applied.text
        assert "SENTINEL_TEST_TOKEN" not in applied.text
        assert "SENTINEL_TEST_TOKEN" in fake_keychain.read_text()
        for record in (data_dir(home) / "changes").rglob("*.json"):
            assert "SENTINEL_TEST_TOKEN" not in record.read_text()
        undone = page.post(f"/api/changes/{change['id']}/undo", headers=POST)
        assert undone.json()["state"] == "undone", undone.text
        assert "SENTINEL_TEST_TOKEN" not in fake_keychain.read_text()
        # A token the server turns down says so, and is not echoed back.
        monkeypatch.setattr(actions, "access_needed", lambda url, headers: "token")
        refused = page.post("/api/changes/preview", json=request, headers=POST)
        assert refused.status_code >= 400
        assert "token-server did not accept this token." in refused.text
        assert "SENTINEL_TEST_TOKEN" not in refused.text


def test_a_missing_required_value_waits_for_a_token():
    from kitden.changes.actions import NeedsAccess
    from kitden.discovery import configured_entry

    setup = [
        {"field": "headers", "name": "Authorization", "label": "Neon API key", "prefix": "Bearer "}
    ]
    row = {"name": "io.github.x/neon", "entry": {"url": "https://x.test/mcp"}, "setup": setup}
    with pytest.raises(NeedsAccess) as error:
        configured_entry(row, {})
    assert (error.value.server, error.value.kind, error.value.fields) == ("neon", "token", setup)
    assert str(error.value) == "neon needs a token."


def test_a_bare_authorization_header_takes_a_bearer_token():
    from kitden.discovery import server_setup

    remote = {
        "type": "streamable-http",
        "url": "https://example.test/mcp",
        "headers": [{"name": "Authorization", "isRequired": True, "description": "API key"}],
    }
    entry, refusal, fields = server_setup({"remotes": [remote]})
    assert refusal is None and entry["url"] == "https://example.test/mcp"
    assert fields == [
        {"field": "headers", "name": "Authorization", "label": "API key", "prefix": "Bearer "}
    ]


def test_a_generic_registry_name_takes_the_publishers_name():
    from kitden.discovery import short_name

    assert short_name("com.neon/mcp") == "neon"
    assert short_name("io.github.acme/mcp-server") == "acme"
    assert short_name("ac.tandem/docs-mcp") == "docs-mcp"


def test_a_local_value_is_checked_when_the_gateway_starts_it():
    from kitden.discovery import server_setup

    package = {
        "registryType": "npm",
        "identifier": "neon-mcp",
        "version": "1.0.0",
        "transport": {"type": "stdio"},
        "environmentVariables": [
            {"name": "NEON_API_KEY", "isRequired": True, "description": "Neon API key"}
        ],
    }
    entry, refusal, fields = server_setup({"packages": [package]})
    assert refusal is None and entry["command"] == "npx"
    assert fields == [
        {
            "field": "env",
            "name": "NEON_API_KEY",
            "label": "Neon API key",
            "prefix": "",
            "later": True,
        }
    ]


def test_details_say_up_front_when_kitden_cannot_sign_in(tmp_path):
    """A remote that offers sign-in Kitden cannot do (no client registration) asks for a token
    in its details, with the reason, before anything is pressed."""
    from kitden.discovery import Discovery
    from tests.unit.fake_oauth import FakeOAuth

    fake = FakeOAuth(no_registration=True)
    try:
        found = Discovery(tmp_path)
        row = {"id": "a" * 24, "kind": "mcp", "name": "io.x/zoom", "entry": {"url": fake.url}}
        found.results[row["id"]] = row
        out = found.details(row["id"])
    finally:
        fake.stop()
    assert out["access_kind"] == "sign-in-later" and out["access_required"] is True
    assert out["access_note"] == (
        "zoom does not let Kitden sign in yet. It may take an API key; see its docs."
    )


def test_a_python_package_runs_with_uvx_at_its_exact_version():
    # Official MCP Registry packages with registryType "pypi" (checked 2026-11-03).
    package = {
        "registryType": "pypi",
        "identifier": "mcparmory-atlassian-jira",
        "version": "1.0.3",
        "transport": {"type": "stdio"},
    }
    entry, refusal = server_entry({"packages": [package]})
    assert refusal is None
    assert entry == {"command": "uvx", "args": ["mcparmory-atlassian-jira==1.0.3"]}
    # Without uv (Kitden from Homebrew) it says what to install.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(discovery.shutil, "which", lambda name: None)
        assert server_entry({"packages": [package]}) == (
            None,
            "This Python server runs with uv. Install uv, then search again.",
        )
    # A name or version that is not a plain package spec is never run.
    for bad in ({"identifier": "x; rm -rf /"}, {"version": "1.0 || true"}):
        assert server_entry({"packages": [{**package, **bad}]})[0] is None


def test_a_python_package_that_needs_a_value_asks_for_it():
    from kitden.discovery import server_setup

    package = {
        "registryType": "pypi",
        "identifier": "jira-mcp",
        "version": "2.0.0",
        "transport": {"type": "stdio"},
        "environmentVariables": [{"name": "JIRA_TOKEN", "isRequired": True}],
    }
    entry, refusal, fields = server_setup({"packages": [package]})
    assert refusal is None and entry == {"command": "uvx", "args": ["jira-mcp==2.0.0"]}
    assert [f["name"] for f in fields] == ["JIRA_TOKEN"]


def test_a_server_kitden_cannot_add_says_why():
    docker = {"registryType": "oci", "identifier": "ghcr.io/x/y:1", "transport": {"type": "stdio"}}
    bundle = {
        "registryType": "mcpb",
        "identifier": "https://github.com/x/y/releases/download/v1/y.mcpb",
        "version": "1.0.0",
        "transport": {"type": "stdio"},
    }
    sse = {"type": "sse", "url": "https://example.com/sse"}
    assert server_entry({"packages": [docker]})[1] == (
        "Only a Docker image. Kitden cannot run Docker servers yet."
    )
    assert server_entry({"packages": [bundle]})[1] == (
        "Only an .mcpb bundle. Install it in your client, then move it into the gateway."
    )
    assert server_entry({"remotes": [sse]})[1] == (
        "Only an SSE address. The gateway does not support SSE yet."
    )
    # Anything else keeps the general words.
    assert server_entry({})[1] == (
        "This server needs sign-in, configuration or a transport Kitden cannot add yet."
    )


def test_only_an_exact_version_is_run():
    # npm reads "owner/repo" as a GitHub repository and "./dir" as a local folder; a tag or a
    # range picks whatever is newest. Only an exact version runs what the registry listed.
    npm = {"registryType": "npm", "identifier": "@acme/mcp", "transport": {"type": "stdio"}}
    pypi = {"registryType": "pypi", "identifier": "acme-mcp", "transport": {"type": "stdio"}}
    for good in ("1.2.3", "0.1.0-beta.2", "1.2.3+build.5"):
        assert server_entry({"packages": [{**npm, "version": good}]})[0] is not None, good
    for good in ("1.0", "1.0.3", "2024.10.1", "1.0rc1", "1.0.post2", "1.0.dev3"):
        assert server_entry({"packages": [{**pypi, "version": good}]})[0] is not None, good
    for bad in ("owner/repo", "./dir", "../up", "latest", "^1.2.0", "~1.2", "1.x", "file:x"):
        assert server_entry({"packages": [{**npm, "version": bad}]})[0] is None, bad
        assert server_entry({"packages": [{**pypi, "version": bad}]})[0] is None, bad


def test_a_version_that_is_not_text_is_skipped_not_an_error():
    # A hand-written server.json may give null or a number; the search must go on.
    npm = {"registryType": "npm", "identifier": "@acme/mcp", "transport": {"type": "stdio"}}
    for odd in (None, 1, 1.2, ["1.2.3"]):
        assert server_entry({"packages": [{**npm, "version": odd}]})[0] is None
