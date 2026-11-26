"""The Context page's groups: each skill of a Claude Code or Codex card is in one group by where it
comes from, named with the Library's words, with its plugin's own switch on the group (spec
context-by-source, 2026-11-26)."""

import pytest

from kitden.views import words
from kitden.views.library_map import ACCOUNT, OTHER, SKILLS
from tests.unit.test_context_now import codex
from tests.unit.test_context_view import (
    claude_chat,
    codex_chat,
    codex_home,
    plugin,
    skill,
    view,
    write_json,
)


@pytest.fixture
def home(tmp_path):
    home = tmp_path / "home"
    for root in (".claude", ".codex", ".cursor"):
        (home / root).mkdir(parents=True)
    return home


def groups_of(card) -> dict[str, dict]:
    return {g["key"]: g for g in card["groups"]}


def test_the_library_and_context_name_their_groups_from_one_table():
    assert SKILLS["name"] == words.GROUP_WORDS["own"] == words.SOURCE_OWN
    assert ACCOUNT["name"] == words.GROUP_WORDS["account"] == words.ACCOUNT_GROUP
    assert OTHER["name"] == words.GROUP_WORDS["other"]


def test_each_skill_is_in_the_group_of_its_source(home):
    key = plugin(home, skills=("tool", "other"))
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    sent = {
        "alpha": "Does alpha.",
        "plug:tool": "Does tool.",
        "plug:other": None,
        "plug:start": "Starts.",
        "dataviz": "Charts.",
        "anthropic-skills:pdf": "PDF.",
        "venture:review": "Reviews.",
        "mystery": "What.",
    }
    claude_chat(home, sent)
    card = view(home)["claude_code"]
    groups = groups_of(card)
    # One group per source, in the order they first come; the page orders them by size.
    assert list(groups) == [
        "own",
        f"plugin:{key}",
        "built_in",
        "app",
        "other:venture",
        "unknown",
    ]
    by_skill = {s["name"]: s["group"] for s in card["skills"]}
    assert all(name in groups[by_skill[name]]["skills"] for name in sent)
    plug = groups[f"plugin:{key}"]
    # A plugin's group: its name and marketplace, its Library item, and its own switch, as its
    # skills' Details offer it; its command is in it too.
    assert (plug["kind"], plug["name"], plug["from"], plug["lookup"]) == (
        "plugin",
        "plug",
        "market",
        key,
    )
    assert plug["skills"] == ["plug:tool", "plug:other", "plug:start"]
    assert plug["switch"] == card["skills"][1]["plugin_switch"]
    assert plug["switch"]["label"] == "Turn off plug" and plug["why"] is None
    assert groups["own"]["name"] == "Your skills" and groups["own"]["switch"] is None
    # No switch: each says why, and where to go.
    assert groups["built_in"]["name"] == "Built into Claude Code"
    assert groups["built_in"]["why"] == words.GROUP_WHY_BUILT_IN
    assert (groups["app"]["name"], groups["app"]["why"]) == (words.SOURCE_APP, words.NOTE_APP)
    assert groups["other:venture"]["why"] == words.NOTE_OTHER_PLUGIN.format("venture")
    assert groups["unknown"]["why"] == words.NOTE_NO_ITEM
    assert all(g["lookup"] is None for k, g in groups.items() if k != f"plugin:{key}")


def test_a_project_skill_is_in_its_project_group(home):
    project = home / "work/atlas"
    skill(project / ".claude/skills", "local", "Does local.")
    write_json(home / ".claude.json", {"projects": {str(project): {}}})
    claude_chat(home, {"local": "Does local."}, folder=str(project))
    card = view(home, folder=str(project))["claude_code"]
    (group,) = card["groups"]
    assert (group["kind"], group["name"]) == ("project", "Project atlas")
    assert group["skills"] == ["local"]


def test_an_off_plugins_group_offers_to_turn_it_on_after_a_new_chat(home):
    key = plugin(home, on=False)
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(home, {"alpha": "Does alpha."})
    group = groups_of(view(home)["claude_code"])[f"plugin:{key}"]
    assert group["skills"] == ["plug:tool"]
    assert group["switch"]["label"] == "Turn on plug"


def test_codex_skills_are_grouped_too(home):
    paths = codex_home(home, window=272_000)
    names = list(paths)
    codex_chat(home, [f"- {n}: Does {n}. (file: {paths[n]})" for n in names])
    card = codex(home)
    assert [g["key"] for g in card["groups"]] == ["own"]
    assert card["groups"][0]["skills"] == [s["name"] for s in card["skills"]]


def test_a_codex_skill_turned_off_after_the_chat_stays_in_its_group(home):
    from tests.unit.test_context_now import codex_off

    paths = codex_home(home, window=272_000)
    codex_chat(home, [f"- {n}: Does {n}. (file: {paths[n]})" for n in paths])
    codex_off(home, paths["gamma"])
    card = codex(home)
    gamma = next(s for s in card["skills"] if s["name"] == "gamma")
    assert (gamma["state"], gamma["group"]) == ("off", "own")
    assert [g["key"] for g in card["groups"]] == ["own"]
