"""The local gateway's settings, rules and tool cache."""

import json
import stat

import pytest

from kitden.changes.backup import ChangeStore
from kitden.changes.engine import ChangeRefusedError, Engine
from kitden.changes.json_splice import ABSENT
from kitden.gateways import data_dir
from kitden.local_gateway.settings import (
    SETTINGS_FILE,
    TOOLS_FILE,
    allowed_tools,
    load_settings,
    load_tools,
    rule_step,
    save_tools,
)
from kitden.model import Scope


def tool(name):
    return {"name": name, "description": f"The {name} tool", "inputSchema": {"type": "object"}}


def names(tools):
    return [t["name"] for t in tools]


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def write_settings(home, settings):
    path = data_dir(home) / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2))
    return path


def engine_for(home):
    return Engine(ChangeStore(data_dir(home)), run=None)


SERVERS = {
    "github": {"command": "gh-mcp", "env": {"GITHUB_TOKEN": "SENTINEL_SECRET_GATEWAY"}},
    "linear": {"url": "https://mcp.linear.app/mcp"},
}
TOOLS = {
    "github": [tool("delete_repo"), tool("list_issues")],
    "linear": [tool("search")],
}


def test_tools_follow_global_then_project_rules():
    settings = {
        "servers": SERVERS,
        "rules": {
            "global": {"github": {"tools": {"delete_repo": "off"}}},
            "projects": {
                "/p": {"github": {"tools": {"delete_repo": "on"}}, "linear": {"server": "off"}}
            },
        },
    }

    everywhere = allowed_tools(settings, TOOLS, None)
    assert names(everywhere["github"]) == ["list_issues"]
    assert names(everywhere["linear"]) == ["search"]

    in_p = allowed_tools(settings, TOOLS, "/p")
    assert names(in_p["github"]) == ["delete_repo", "list_issues"]
    assert "linear" not in in_p

    # A project with no rules of its own gets the global set.
    assert allowed_tools(settings, TOOLS, "/other") == everywhere


def test_a_project_can_turn_on_a_server_that_is_off_everywhere():
    settings = {
        "servers": SERVERS,
        "rules": {
            "global": {"linear": {"server": "off"}},
            "projects": {"/q": {"linear": {"server": "on"}}},
        },
    }
    assert "linear" not in allowed_tools(settings, TOOLS, None)
    assert "linear" not in allowed_tools(settings, TOOLS, "/p")
    assert names(allowed_tools(settings, TOOLS, "/q")["linear"]) == ["search"]


def test_a_rule_for_a_missing_tool_is_ignored_and_a_new_tool_is_on():
    settings = {
        "servers": SERVERS,
        "rules": {
            "global": {"github": {"tools": {"gone_tool": "off", "delete_repo": "off"}}},
            "projects": {"/p": {"github": {"tools": {"also_gone": "on"}}}},
        },
    }
    tools = {"github": [tool("delete_repo"), tool("list_issues"), tool("brand_new")]}

    assert names(allowed_tools(settings, tools, None)["github"]) == ["list_issues", "brand_new"]
    assert names(allowed_tools(settings, tools, "/p")["github"]) == ["list_issues", "brand_new"]


def test_only_servers_in_the_gateway_with_a_known_tool_list_are_offered():
    settings = {"servers": SERVERS, "rules": {"global": {}, "projects": {}}}
    tools = {"github": [tool("list_issues")], "removed": [tool("old")]}  # linear: list not known

    assert list(allowed_tools(settings, tools, None)) == ["github"]


def test_a_missing_settings_file_reads_as_empty(tmp_path):
    empty = {"servers": {}, "rules": {"global": {}, "projects": {}}}
    assert load_settings(tmp_path) == empty
    assert load_tools(tmp_path) == {}
    assert allowed_tools(load_settings(tmp_path), load_tools(tmp_path), None) == {}


def test_an_unreadable_settings_file_reads_as_empty(tmp_path):
    path = write_settings(tmp_path, {})
    path.write_text("{ not json")
    assert load_settings(tmp_path) == {"servers": {}, "rules": {"global": {}, "projects": {}}}
    (data_dir(tmp_path) / TOOLS_FILE).write_text("[1, 2]")
    assert load_tools(tmp_path) == {}
    (data_dir(tmp_path) / TOOLS_FILE).write_text(
        json.dumps({"github": [tool("list_issues"), "junk", {"description": "no name"}], "x": 1})
    )
    assert load_tools(tmp_path) == {"github": [tool("list_issues")]}


def test_settings_that_are_saved_read_back_whole(tmp_path):
    settings = {
        "servers": SERVERS,
        "rules": {"global": {"linear": {"server": "off"}}, "projects": {"/p": {}}},
    }
    write_settings(tmp_path, settings)
    assert load_settings(tmp_path) == settings


def test_rule_step_edits_one_entry_and_can_go_back_to_global(tmp_path):
    original = {
        "servers": SERVERS,
        "rules": {
            "global": {"github": {"tools": {"delete_repo": "off"}}, "linear": {"server": "off"}},
            "projects": {},
        },
    }
    path = write_settings(tmp_path, original)
    path.chmod(0o600)
    before = path.read_text()
    engine = engine_for(tmp_path)

    # Turn one tool on for one project, against the global rule.
    step = rule_step(tmp_path, "/p", "github", "delete_repo", "on")
    assert (step.client, step.scope) == ("kitden", Scope.USER)
    assert (step.edit.fmt, step.edit.check) == ("json", "entry")
    assert step.edit.path == str(path)
    assert step.edit.key == ("rules", "projects", "/p", "github", "tools", "delete_repo")
    change = engine.preview("gateway.rule", [step])
    assert "SENTINEL_SECRET_GATEWAY" not in step.edit.masked_diff
    engine.apply(change.id)
    assert str(change.state) == "verified"
    saved = json.loads(path.read_text())
    assert saved["rules"]["projects"] == {"/p": {"github": {"tools": {"delete_repo": "on"}}}}
    assert saved["rules"]["global"] == original["rules"]["global"]
    assert saved["servers"] == SERVERS
    assert "delete_repo" in names(allowed_tools(load_settings(tmp_path), TOOLS, "/p")["github"])

    # Follow the global rule again: the project's own value is removed.
    step = rule_step(tmp_path, "/p", "github", "delete_repo", None)
    assert step.edit.after is ABSENT
    change_back = engine.preview("gateway.rule", [step])
    engine.apply(change_back.id)
    assert "delete_repo" not in json.dumps(json.loads(path.read_text())["rules"]["projects"])
    assert "delete_repo" not in names(allowed_tools(load_settings(tmp_path), TOOLS, "/p")["github"])

    # Undo puts the first file back exactly.
    engine.undo(change_back.id)
    engine.undo(change.id)
    assert path.read_text() == before
    assert mode(path) == 0o600


def test_rule_step_keys_for_global_project_server_and_tool_rules(tmp_path):
    keys = {
        (None, "github", None, "off"): ("rules", "global", "github", "server"),
        (None, "github", "delete_repo", "off"): (
            ("rules", "global", "github", "tools", "delete_repo")
        ),
        ("/p", "linear", None, "on"): ("rules", "projects", "/p", "linear", "server"),
    }
    for (project, server, tool_name, state), key in keys.items():
        assert rule_step(tmp_path, project, server, tool_name, state).edit.key == key


def test_a_global_rule_is_written_into_a_file_that_is_not_there_yet(tmp_path):
    engine = engine_for(tmp_path)
    step = rule_step(tmp_path, None, "github", "delete_repo", "off")
    change = engine.preview("gateway.rule", [step])
    engine.apply(change.id)

    path = data_dir(tmp_path) / SETTINGS_FILE
    assert json.loads(path.read_text()) == {
        "rules": {"global": {"github": {"tools": {"delete_repo": "off"}}}}
    }
    assert mode(path) == 0o600
    settings = load_settings(tmp_path)
    assert settings["servers"] == {}
    assert settings["rules"]["global"]["github"]["tools"] == {"delete_repo": "off"}

    engine.undo(change.id)
    assert not path.exists()


def test_a_rule_that_is_already_set_has_nothing_to_change(tmp_path):
    write_settings(tmp_path, {"rules": {"global": {"github": {"server": "off"}}}})
    step = rule_step(tmp_path, None, "github", None, "off")
    with pytest.raises(ChangeRefusedError):
        engine_for(tmp_path).preview("gateway.rule", [step])


def test_rule_step_refuses_a_state_that_is_not_on_or_off(tmp_path):
    with pytest.raises(ValueError, match="on or off"):
        rule_step(tmp_path, None, "github", None, "maybe")


def test_the_tool_cache_is_private(tmp_path):
    save_tools(tmp_path, "github", [tool("list_issues")])
    save_tools(tmp_path, "linear", [tool("search")])

    path = data_dir(tmp_path) / TOOLS_FILE
    assert mode(path) == 0o600
    assert mode(data_dir(tmp_path)) == 0o700
    assert [p.name for p in data_dir(tmp_path).iterdir()] == [TOOLS_FILE]  # no temp file left
    assert load_tools(tmp_path) == {"github": [tool("list_issues")], "linear": [tool("search")]}


def test_saving_tools_replaces_that_servers_list_and_keeps_the_rest(tmp_path):
    save_tools(tmp_path, "github", [tool("list_issues"), tool("delete_repo")])
    save_tools(tmp_path, "linear", [tool("search")])
    save_tools(tmp_path, "github", [tool("list_issues")])

    assert names(load_tools(tmp_path)["github"]) == ["list_issues"]
    assert names(load_tools(tmp_path)["linear"]) == ["search"]


def test_a_saved_tool_keeps_name_description_and_input_schema_only(tmp_path):
    schema = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
    save_tools(
        tmp_path,
        "linear",
        [
            {"name": "search", "description": None, "inputSchema": schema, "title": "Search"},
            {"name": "ping"},
        ],
    )
    assert load_tools(tmp_path)["linear"] == [
        {"name": "search", "description": "", "inputSchema": schema},
        {"name": "ping", "description": "", "inputSchema": {"type": "object"}},
    ]
