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
    is_allowed,
    load_settings,
    load_tools,
    rule_step,
    save_tools,
    servers_on,
    settings_unreadable,
    state_in,
    strict_step,
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

    everywhere = allowed_tools(settings, TOOLS, [])
    assert names(everywhere["github"]) == ["list_issues"]
    assert names(everywhere["linear"]) == ["search"]

    in_p = allowed_tools(settings, TOOLS, ["/p"])
    assert names(in_p["github"]) == ["delete_repo", "list_issues"]
    assert "linear" not in in_p

    # A project with no rules of its own gets the global set.
    assert allowed_tools(settings, TOOLS, ["/other"]) == everywhere


def test_in_strict_mode_a_tool_without_a_rule_is_off():
    settings = {
        "servers": {"github": {}},
        "rules": {
            "global": {"github": {"mode": "strict", "tools": {"list_issues": "on"}}},
            "projects": {},
        },
    }
    tools = {"github": [tool("list_issues"), tool("create_issue")]}
    assert names(allowed_tools(settings, tools, [])["github"]) == ["list_issues"]
    assert state_in(settings, [], "github", "create_issue") == "off"
    assert state_in(settings, [], "github", None) == "on"  # the server itself needs no rule


def test_a_project_rule_still_wins_in_strict_mode():
    settings = {
        "servers": {"github": {}},
        "rules": {
            "global": {"github": {"mode": "strict"}},
            "projects": {"/p": {"github": {"tools": {"create_issue": "on"}}}},
        },
    }
    assert state_in(settings, ["/p"], "github", "create_issue") == "on"
    assert state_in(settings, [], "github", "create_issue") == "off"


def test_settings_without_a_mode_read_as_before():
    settings = {
        "servers": SERVERS,
        "rules": {
            "global": {"github": {"tools": {"delete_repo": "off"}}},
            "projects": {
                "/p": {"github": {"tools": {"delete_repo": "on"}}, "linear": {"server": "off"}}
            },
        },
    }
    assert names(allowed_tools(settings, TOOLS, [])["github"]) == ["list_issues"]
    assert names(allowed_tools(settings, TOOLS, ["/p"])["github"]) == [
        "delete_repo",
        "list_issues",
    ]


def test_strict_step_writes_and_removes_the_mode(tmp_path):
    step = strict_step(tmp_path, "github", True)
    assert step.edit.key == ("rules", "global", "github", "mode")
    assert step.edit.after == "strict"
    assert strict_step(tmp_path, "github", False).edit.after is ABSENT


def test_a_project_can_turn_on_a_server_that_is_off_everywhere():
    settings = {
        "servers": SERVERS,
        "rules": {
            "global": {"linear": {"server": "off"}},
            "projects": {"/q": {"linear": {"server": "on"}}},
        },
    }
    assert "linear" not in allowed_tools(settings, TOOLS, [])
    assert "linear" not in allowed_tools(settings, TOOLS, ["/p"])
    assert names(allowed_tools(settings, TOOLS, ["/q"])["linear"]) == ["search"]


def test_the_deepest_project_with_its_own_state_decides_then_the_next_then_global():
    settings = {
        "servers": SERVERS,
        "rules": {
            "global": {"github": {"tools": {"list_issues": "off"}}},
            "projects": {
                "/repo": {"github": {"tools": {"delete_repo": "off"}}},
                "/repo/web": {"github": {"tools": {"list_issues": "on"}}},
                "/repo-wt": {
                    "github": {"tools": {"delete_repo": "on"}},
                    "linear": {"server": "off"},
                },
            },
        },
    }
    # A known subfolder keeps its parent's rule unless it has its own.
    assert names(allowed_tools(settings, TOOLS, ["/repo/web", "/repo"])["github"]) == [
        "list_issues"
    ]
    # A worktree's own rule wins over its main checkout's.
    in_wt = allowed_tools(settings, TOOLS, ["/repo-wt", "/repo"])
    assert names(in_wt["github"]) == ["delete_repo"]
    assert servers_on(settings, ["/repo-wt", "/repo"]) == ["github"]
    assert names(allowed_tools(settings, TOOLS, ["/repo"])["github"]) == []


def test_a_rule_for_a_missing_tool_is_ignored_and_a_new_tool_is_on():
    settings = {
        "servers": SERVERS,
        "rules": {
            "global": {"github": {"tools": {"gone_tool": "off", "delete_repo": "off"}}},
            "projects": {"/p": {"github": {"tools": {"also_gone": "on"}}}},
        },
    }
    tools = {"github": [tool("delete_repo"), tool("list_issues"), tool("brand_new")]}

    assert names(allowed_tools(settings, tools, [])["github"]) == ["list_issues", "brand_new"]
    assert names(allowed_tools(settings, tools, ["/p"])["github"]) == ["list_issues", "brand_new"]


def test_only_servers_in_the_gateway_with_a_known_tool_list_are_offered():
    settings = {"servers": SERVERS, "rules": {"global": {}, "projects": {}}}
    tools = {"github": [tool("list_issues")], "removed": [tool("old")]}  # linear: list not known

    assert list(allowed_tools(settings, tools, [])) == ["github"]


def test_servers_on_lists_every_server_that_is_on_with_or_without_a_tool_list():
    settings = {
        "servers": {**SERVERS, "notion": {"command": "notion-mcp"}},  # no tool list known
        "rules": {
            "global": {"linear": {"server": "off"}, "ghost": {"server": "on"}},
            "projects": {"/q": {"linear": {"server": "on"}, "github": {"server": "off"}}},
        },
    }

    assert servers_on(settings, []) == ["github", "notion"]
    assert servers_on(settings, ["/p"]) == ["github", "notion"]  # no rules of its own
    assert servers_on(settings, ["/q"]) == ["linear", "notion"]
    assert servers_on({"servers": {}, "rules": {}}, ["/q"]) == []


def test_a_missing_settings_file_reads_as_empty(tmp_path):
    empty = {"servers": {}, "rules": {"global": {}, "projects": {}}}
    assert load_settings(tmp_path) == empty
    assert load_tools(tmp_path) == {}
    assert allowed_tools(load_settings(tmp_path), load_tools(tmp_path), []) == {}


def test_an_unreadable_settings_file_reads_as_empty(tmp_path):
    assert settings_unreadable(tmp_path) is False  # no file is no problem
    path = write_settings(tmp_path, {})
    assert settings_unreadable(tmp_path) is False
    path.write_text("{ not json")
    assert load_settings(tmp_path) == {"servers": {}, "rules": {"global": {}, "projects": {}}}
    assert settings_unreadable(tmp_path) is True
    path.write_text("[]")
    assert settings_unreadable(tmp_path) is True
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
    assert "delete_repo" in step.edit.masked_diff
    engine.apply(change.id)
    assert str(change.state) == "verified"
    records = (data_dir(tmp_path) / "changes" / change.id / "change.json").read_text()
    records += (data_dir(tmp_path) / "changes.log").read_text()
    assert "delete_repo" in records
    assert "SENTINEL_SECRET_GATEWAY" not in records  # the servers' env is never recorded
    saved = json.loads(path.read_text())
    assert saved["rules"]["projects"] == {"/p": {"github": {"tools": {"delete_repo": "on"}}}}
    assert saved["rules"]["global"] == original["rules"]["global"]
    assert saved["servers"] == SERVERS
    assert "delete_repo" in names(allowed_tools(load_settings(tmp_path), TOOLS, ["/p"])["github"])

    # Follow the global rule again: the project's own value is removed.
    step = rule_step(tmp_path, "/p", "github", "delete_repo", None)
    assert step.edit.after is ABSENT
    change_back = engine.preview("gateway.rule", [step])
    engine.apply(change_back.id)
    assert "delete_repo" not in json.dumps(json.loads(path.read_text())["rules"]["projects"])
    assert "delete_repo" not in names(
        allowed_tools(load_settings(tmp_path), TOOLS, ["/p"])["github"]
    )

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


def test_a_saved_tool_keeps_what_the_client_is_shown_and_nothing_else(tmp_path):
    schema = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
    hints = {"readOnlyHint": True, "destructiveHint": False}
    save_tools(
        tmp_path,
        "linear",
        [
            {
                "name": "search",
                "description": None,
                "inputSchema": schema,
                "title": "Search",
                "annotations": hints,
                "_meta": {"x": 1},
            },
            {"name": "ping"},
        ],
    )
    assert load_tools(tmp_path)["linear"] == [
        {
            "name": "search",
            "description": "",
            "inputSchema": schema,
            "title": "Search",
            "annotations": hints,
        },
        {"name": "ping", "description": "", "inputSchema": {"type": "object"}},
    ]


def test_is_allowed_reads_the_file_again(tmp_path):
    write_settings(tmp_path, {"servers": {"github": {}}, "rules": {"global": {}, "projects": {}}})
    assert is_allowed(tmp_path, [], "github", "echo") is True
    off = {"github": {"tools": {"echo": "off"}}}
    write_settings(tmp_path, {"servers": {"github": {}}, "rules": {"global": off, "projects": {}}})
    assert is_allowed(tmp_path, [], "github", "echo") is False


def test_a_tool_on_under_a_server_off_is_refused(tmp_path):
    rules = {"global": {"github": {"server": "off", "tools": {"echo": "on"}}}, "projects": {}}
    write_settings(tmp_path, {"servers": {"github": {}}, "rules": rules})
    assert is_allowed(tmp_path, [], "github", "echo") is False


def test_is_allowed_follows_strict_mode(tmp_path):
    rules = {"global": {"github": {"mode": "strict", "tools": {"echo": "on"}}}, "projects": {}}
    write_settings(tmp_path, {"servers": {"github": {}}, "rules": rules})
    assert is_allowed(tmp_path, [], "github", "echo") is True
    assert is_allowed(tmp_path, [], "github", "other") is False


def test_is_allowed_uses_the_fallback_when_the_file_cannot_be_read(tmp_path):
    off = {"servers": {"github": {}}, "rules": {"global": {"github": {"tools": {"echo": "off"}}}}}
    on = {"servers": {"github": {}}, "rules": {"global": {}}}
    path = write_settings(tmp_path, on)
    path.write_text("{ not json")
    assert is_allowed(tmp_path, [], "github", "echo", fallback=off) is False
    assert is_allowed(tmp_path, [], "github", "echo", fallback=on) is True
    # Without a fallback a broken or missing file allows nothing.
    assert is_allowed(tmp_path, [], "github", "echo") is False
    path.unlink()
    assert is_allowed(tmp_path, [], "github", "echo") is False
    assert is_allowed(tmp_path, [], "github", "echo", fallback=off) is False
