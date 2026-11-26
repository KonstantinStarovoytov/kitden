"""The Context page's groups: each skill of a Claude Code or Codex card is in one group by where it
comes from, named with the Library's words, with its plugin's own switch on the group (spec
context-by-source, 2026-11-26)."""

import pytest

from kitden.views import words
from kitden.views.library_map import ACCOUNT, OTHER, SKILLS
from tests.unit.test_context_codex_log import meta, turn, write_log
from tests.unit.test_context_codex_log import skills as codex_list_entry
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


def codex_plugin(home, enabled: bool = True):
    """The Codex plugin plug@market with one skill, and its entry in config.toml."""
    inside = home / ".codex/plugins/cache/market/plug/1.0/skills"
    tool = skill(inside, "tool", "Does one thing.").resolve()
    (home / ".codex/plugins/cache/market/plug/1.0/.codex-plugin").mkdir(exist_ok=True)
    state = "true" if enabled else "false"
    (home / ".codex/config.toml").write_text(f'[plugins."plug@market"]\nenabled = {state}\n')
    return tool


def test_a_codex_plugin_group_has_its_switch_and_its_skills_take_it(home):
    paths = codex_home(home, window=20_000)
    tool = codex_plugin(home)
    codex_chat(
        home,
        [
            f"- alpha: Does alpha. (file: {paths['alpha']})",
            f"- plug:tool: Does one thing. (file: {tool})",
        ],
    )
    card = codex(home)
    group = next(g for g in card["groups"] if g["key"] == "plugin:plug@market")
    assert group["switch"]["label"] == "Turn off plug" and group["skills"] == ["plug:tool"]
    row = next(s for s in card["skills"] if s["name"] == "plug:tool")
    assert row["plugin_switch"] == group["switch"]


def test_an_off_codex_plugin_keeps_its_group_after_a_chat_without_it(home):
    paths = codex_home(home, window=20_000)
    codex_plugin(home, enabled=False)
    codex_chat(home, [f"- alpha: Does alpha. (file: {paths['alpha']})"])
    card = codex(home)
    group = next(g for g in card["groups"] if g["key"] == "plugin:plug@market")
    assert group["switch"]["label"] == "Turn on plug"
    (row,) = [s for s in card["skills"] if s["group"] == "plugin:plug@market"]
    assert (row["state"], row["side"], row["note"]) == ("off", None, words.NOTE_OFF)


def test_a_codex_plugin_turned_off_after_the_chat_lists_its_skill_once(home):
    paths = codex_home(home, window=20_000)
    tool = codex_plugin(home)
    lines = [f"- alpha: Does alpha. (file: {paths['alpha']})"]
    codex_chat(home, [*lines, f"- plug:tool: Does one thing. (file: {tool})"])
    codex_plugin(home, enabled=False)
    card = codex(home)
    assert [s["name"] for s in card["skills"]].count("plug:tool") == 1
    group = next(g for g in card["groups"] if g["key"] == "plugin:plug@market")
    assert group["switch"]["label"] == "Turn on plug"


def test_an_off_codex_plugin_with_no_version_folder_keeps_its_skills(home):
    # Codex may keep a plugin's files in its own folder, with no version folder under it.
    paths = codex_home(home, window=20_000)
    folder = home / ".codex/plugins/cache/market/plug"
    skill(folder / "skills", "tool", "Does one thing.")
    (folder / ".codex-plugin").mkdir(parents=True)
    (home / ".codex/config.toml").write_text('[plugins."plug@market"]\nenabled = false\n')
    codex_chat(home, [f"- alpha: Does alpha. (file: {paths['alpha']})"])
    card = codex(home)
    group = next(g for g in card["groups"] if g["key"] == "plugin:plug@market")
    assert group["skills"] == ["plug:tool"]


def test_a_codex_plugin_a_project_sets_has_no_switch_for_all_projects(home):
    # The user's entry has it on, the project's has it off: a switch for all projects would leave
    # this project off, so the group offers none and says why.
    paths = codex_home(home, window=20_000)
    tool = codex_plugin(home)
    project = home / "work/a"
    (project / ".codex").mkdir(parents=True)
    (project / ".codex/config.toml").write_text('[plugins."plug@market"]\nenabled = false\n')
    config = home / ".codex/config.toml"
    trusted = f'\n[projects."{project}"]\ntrust_level = "trusted"\n'
    config.write_text(config.read_text() + trusted)
    lines = [
        f"- alpha: Does alpha. (file: {paths['alpha']})",
        f"- plug:tool: Does one. (file: {tool})",
    ]
    text = "<skills_instructions>\n" + "\n".join(lines) + "\n</skills_instructions>"
    log = [meta(folder=str(project)), turn(), codex_list_entry(text, at="2026-10-30T12:00:00Z")]
    write_log(home / ".codex", "a", log, 100)
    card = view(home, folder=str(project))["codex"]
    group = next(g for g in card["groups"] if g["key"] == "plugin:plug@market")
    assert group["switch"] is None and group["why"] == words.GROUP_WHY_PROJECT


def test_an_off_codex_plugin_keeps_its_nested_skills(home):
    # Codex finds a skill in a sub-folder of skills/, so Kitden does too.
    paths = codex_home(home, window=20_000)
    folder = home / ".codex/plugins/cache/market/plug"
    skill(folder / "skills/tools", "tool", "Does one thing.")
    (folder / ".codex-plugin").mkdir(parents=True)
    (home / ".codex/config.toml").write_text('[plugins."plug@market"]\nenabled = false\n')
    codex_chat(home, [f"- alpha: Does alpha. (file: {paths['alpha']})"])
    card = codex(home)
    group = next(g for g in card["groups"] if g["key"] == "plugin:plug@market")
    assert group["skills"] == ["plug:tool"] and group["switch"]["label"] == "Turn on plug"


def test_a_codex_plugin_a_project_turns_off_shows_its_skills_and_why_no_switch(home):
    # The user's entry has it on, the project's off, and the last chat did not list it.
    paths = codex_home(home, window=20_000)
    codex_plugin(home)
    project = home / "work/a"
    (project / ".codex").mkdir(parents=True)
    (project / ".codex/config.toml").write_text('[plugins."plug@market"]\nenabled = false\n')
    config = home / ".codex/config.toml"
    config.write_text(config.read_text() + f'\n[projects."{project}"]\ntrust_level = "trusted"\n')
    lines = [f"- alpha: Does alpha. (file: {paths['alpha']})"]
    text = "<skills_instructions>\n" + "\n".join(lines) + "\n</skills_instructions>"
    log = [meta(folder=str(project)), turn(), codex_list_entry(text, at="2026-10-30T12:00:00Z")]
    write_log(home / ".codex", "a", log, 100)
    card = view(home, folder=str(project))["codex"]
    group = next(g for g in card["groups"] if g["key"] == "plugin:plug@market")
    assert group["skills"] == ["plug:tool"]
    assert group["switch"] is None and group["why"] == words.GROUP_WHY_PROJECT
