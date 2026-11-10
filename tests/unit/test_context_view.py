"""The Context read model, from sandbox homes with small fixture chat logs (spec "States")."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kitden.context.rules import CodexSkill, codex_rule
from kitden.views.context_view import _codex_estimate, context_view
from kitden.views.inventory import build_inventory
from kitden.views.overview import overview
from tests.unit.test_context_claude_log import assistant, list_entry, write_chat
from tests.unit.test_context_codex_log import meta, turn, write_log
from tests.unit.test_context_codex_log import skills as codex_list_entry

NO_CHECK = "Kitden cannot check its estimate against your last chat, so it shows none."
LONG = "Use it when the task needs a careful plan. " * 30  # 1,290 characters


@pytest.fixture
def home(tmp_path):
    home = tmp_path / "home"
    for root in (".claude", ".codex", ".cursor"):
        (home / root).mkdir(parents=True)
    return home


def skill(folder: Path, name: str, description: str, extra: str = "") -> Path:
    path = folder / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: {description}\n{extra}---\nBody.\n")
    return path


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def usage(home: Path, counts: dict[str, int], at_ms: int = 1_762_400_000_000) -> None:
    usage = {n: {"usageCount": c, "lastUsedAt": at_ms} for n, c in counts.items()}
    write_json(home / ".claude.json", {"skillUsage": usage})


def view(home: Path, folder: str | None = None, draft: dict | None = None) -> dict:
    inventory = build_inventory(home)
    answer = context_view(inventory, home, home / ".codex", folder, draft or {})
    return {c["client"]: c for c in answer["clients"]}


def claude_chat(home, skills, *, model="claude-opus-5-5", at="2026-11-06T12:00:00Z", **kw):
    """A chat whose list sends `skills` (name -> sent text, None = name only)."""
    names = list(skills)
    content = "\n".join(f"- {n}: {t}" if t is not None else f"- {n}" for n, t in skills.items())
    entry = list_entry(names, content, at=at, **kw)
    write_chat(home, "p", "chat", [entry, assistant(model)], 100)


# Claude Code


def test_claude_everything_fits_is_a_fact_and_the_room_is_an_estimate(home):
    own = home / ".claude/skills"
    for name in ("alpha", "beta", "gamma"):
        skill(own, name, f"Does {name}.")
    claude_chat(home, {"alpha": "Does alpha.", "beta": "Does beta.", "gamma": "Does gamma."})
    cc = view(home)["claude_code"]
    assert cc["lede"] == (
        "Every chat starts with a list of your skills. The agent reads it to choose the right "
        "skill. Claude Code lets this list use 1% of the context window."
    )
    assert (cc["lamp"], cc["checked"], cc["message"], cc["unit"]) == (
        "ok",
        True,
        None,
        "characters",
    )
    assert cc["fact"] == {
        "date": "Nov 6",
        "surface": "in the Claude app",
        "folder": "/work/a",
        "version": "2.1.311",
    }
    fact, other = cc["windows"]
    assert (fact["title"], fact["models"], fact["tag"], fact["budget"]) == (
        "1M window",
        "Opus 5.5 · in the Claude app",
        "Last chat · Nov 6",
        30_000,
    )
    assert fact["result"]["say"] == (
        "In your last chat on Nov 6, all 3 skills were sent with their descriptions."
    )
    assert fact["result"]["short"] == "All 3 sent"
    used = fact["result"]["used"]
    assert (
        fact["result"]["room"]
        == f"Estimate: about {30_000 - used:,} characters left before the limit."
    )
    assert (other["title"], other["models"], other["tag"], other["budget"]) == (
        "200K window",
        "Older models",
        "Estimate",
        8_000,
    )
    assert (
        other["result"]["say"]
        == "Estimate: On a 200K window, every skill would keep its description."
    )
    assert cc["sides"] == ["Description sent", "Name only"]
    assert [s["side"] for s in cc["skills"]] == [0, 0, 0]
    assert cc["after"] is None
    assert cc["how"][0] == (
        "Last chat: the list Claude Code 2.1.311 sent on Nov 6 in the Claude app, "
        "read from its chat log."
    )


def test_claude_too_many_names_the_count(home):
    own = home / ".claude/skills"
    for name in ("alpha", "beta", "gamma", "delta"):
        skill(own, name, LONG[:1000])
    write_json(home / ".claude/settings.json", {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "2100"}})
    usage(home, {"alpha": 9, "beta": 5, "gamma": 2, "delta": 1})
    claude_chat(
        home,
        {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None},
        model="claude-sonnet-4-6",
        at="2026-11-07T12:00:00Z",
    )
    cc = view(home)["claude_code"]
    assert (cc["lamp"], cc["checked"], cc["message"]) == ("warn", True, None)
    [fact] = cc["windows"]
    assert (fact["title"], fact["models"], fact["budget"]) == (
        "2,100 characters",
        "Set in Claude Code settings",
        2100,
    )
    assert fact["result"]["say"] == (
        "In your last chat on Nov 7, 2 of 4 skills showed only a name. "
        "The agent may not have used them."
    )
    assert fact["result"]["short"] == "2 of 4 showed only a name"
    assert fact["result"]["misfit"] == {"kind": "name", "n": 2}
    assert fact["result"]["room"] is None
    assert set(fact["result"]["sent"]) == {"alpha", "beta"}
    assert fact["result"]["over"] == {"gamma": 1002, "delta": 1002}
    assert {s["name"]: s["side"] for s in cc["skills"]} == {
        "alpha": 0,
        "beta": 0,
        "gamma": 1,
        "delta": 1,
    }


def test_skills_set_to_name_only_after_the_chat_keep_the_last_chat_result(home):
    own = home / ".claude/skills"
    for name in ("alpha", "beta", "gamma", "delta"):
        skill(own, name, LONG[:1000])
    settings = {
        "env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "2100"},
        "skillOverrides": {"gamma": "name-only", "delta": "name-only"},
    }
    write_json(home / ".claude/settings.json", settings)
    usage(home, {"alpha": 9, "beta": 5, "gamma": 2, "delta": 1})
    claude_chat(home, {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None})
    cc = view(home)["claude_code"]
    # The fact, the lamp, the hatched part and the room all come from the last chat.
    result = cc["windows"][0]["result"]
    assert result["say"].startswith("In your last chat on Nov 6, 2 of 4 skills showed only a name.")
    assert cc["lamp"] == "warn"
    assert result["over"] == {"gamma": 1002, "delta": 1002}
    assert result["room"] is None


def before_the_chat(path: Path) -> None:
    """The settings file last changed on Nov 1, before the chats of these tests (Nov 6)."""
    when = datetime(2026, 11, 1, tzinfo=UTC).timestamp()
    os.utime(path, (when, when))


def chosen_home(home, overrides):
    """Four long skills, a limit of 2,100 characters, and these skills set to Name only."""
    own = home / ".claude/skills"
    for name in ("alpha", "beta", "gamma", "delta"):
        skill(own, name, LONG[:1000])
    settings = {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "2100"}, "skillOverrides": overrides}
    write_json(home / ".claude/settings.json", settings)
    usage(home, {"alpha": 9, "beta": 5, "gamma": 2, "delta": 1})


def test_skills_set_to_name_only_before_the_chat_are_a_choice_not_a_misfit(home):
    chosen_home(home, {"gamma": "name-only", "delta": "name-only"})
    before_the_chat(home / ".claude/settings.json")
    claude_chat(home, {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None})
    cc = view(home)["claude_code"]
    result = cc["windows"][0]["result"]
    assert result["say"] == (
        "In your last chat on Nov 6, all 4 skills were sent; 2 showed only a name, as you chose."
    )
    assert (cc["lamp"], result["misfit"], result["over"]) == ("ok", None, {})
    assert result["short"] == "All 4 sent"
    assert result["room"] is not None
    # The Overview has no card for a choice.
    clients = context_view(build_inventory(home), home, home / ".codex", None, {})["clients"]
    cards = overview(build_inventory(home), [], None, context_cards=clients)["cards"]
    assert not [c for c in cards if c["icon"] == "gauge"]


def test_a_choice_and_a_misfit_are_told_apart(home):
    chosen_home(home, {"delta": "name-only"})
    before_the_chat(home / ".claude/settings.json")
    claude_chat(home, {"alpha": LONG[:1000], "beta": LONG[:1000], "gamma": None, "delta": None})
    cc = view(home)["claude_code"]
    result = cc["windows"][0]["result"]
    assert result["say"] == (
        "In your last chat on Nov 6, 1 of 4 skills showed only a name. The agent may not have "
        "used it. 1 more showed only a name, as you chose."
    )
    assert (cc["lamp"], result["misfit"], result["over"]) == (
        "warn",
        {"kind": "name", "n": 1},
        {"gamma": 1002},
    )


def test_name_only_the_rule_needs_to_rebuild_the_list_is_a_choice(home):
    # The settings changed after the chat, but with gamma on, the rule would have sent its
    # description: only its Name only setting explains the list.
    own = home / ".claude/skills"
    for name in ("alpha", "beta", "gamma"):
        skill(own, name, f"Does {name}.")
    write_json(home / ".claude/settings.json", {"skillOverrides": {"gamma": "name-only"}})
    claude_chat(home, {"alpha": "Does alpha.", "beta": "Does beta.", "gamma": None})
    cc = view(home)["claude_code"]
    assert cc["checked"] is True
    assert cc["windows"][0]["result"]["say"] == (
        "In your last chat on Nov 6, all 3 skills were sent; 1 showed only a name, as you chose."
    )
    assert cc["lamp"] == "ok"


def test_without_a_check_name_only_is_told_as_set_now(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    skill(home / ".claude/skills", "beta", "Does beta.")
    write_json(home / ".claude/settings.json", {"skillOverrides": {"beta": "name-only"}})
    claude_chat(home, {"alpha": "Does alpha.", "beta": None}, model="claude-new-9")
    cc = view(home)["claude_code"]
    assert cc["checked"] is False
    result = cc["windows"][0]["result"]
    assert result["say"] == (
        "In your last chat on Nov 6, all 2 skills were sent; 1 showed only a name and is set to "
        "Name only now."
    )
    # Kitden cannot judge that chat: grey, not green, and no Overview card.
    assert (cc["lamp"], result["misfit"]) == ("none", None)
    clients = context_view(build_inventory(home), home, home / ".codex", None, {})["clients"]
    cards = overview(build_inventory(home), [], None, context_cards=clients)["cards"]
    assert not [c for c in cards if c["icon"] == "gauge"]


def test_without_a_check_every_skill_sent_with_its_description_stays_green(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(home, {"alpha": "Does alpha."}, model="claude-new-9")
    cc = view(home)["claude_code"]
    assert (cc["checked"], cc["lamp"], cc["windows"][0]["result"]["misfit"]) == (False, "ok", None)


def test_the_check_that_never_ran_is_not_called_a_mismatch(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(home, {"alpha": "Does alpha."}, model="claude-new-9")
    how = view(home)["claude_code"]["how"]
    assert how[2].endswith("This time Kitden could not run the check.")


def test_a_check_that_ran_and_differs_says_so(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    skill(home / ".claude/skills", "beta", "Does beta.")
    claude_chat(home, {"alpha": "Does alpha.", "beta": None})
    how = view(home)["claude_code"]["how"]
    assert how[2].endswith("This time it does not.")


def test_one_skill_and_a_bad_timestamp_read_plainly(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(home, {"alpha": "Does alpha."}, at="not a time")
    cc = view(home)["claude_code"]
    [fact, *_] = cc["windows"]
    assert fact["result"]["say"] == (
        "In your last chat, your one skill was sent with its description."
    )
    assert fact["tag"] == "Last chat"
    assert cc["how"][0] == (
        "Last chat: the list Claude Code 2.1.311 sent in the Claude app, read from its chat log."
    )


def test_one_skill_with_only_a_name(home):
    claude_chat(home, {"alpha": None})
    say = view(home)["claude_code"]["windows"][0]["result"]["say"]
    assert say == (
        "In your last chat on Nov 6, 1 of 1 skill showed only a name. The agent may not have "
        "used it."
    )


def test_an_unreadable_log_with_no_version_names_no_version(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    entry = list_entry(["alpha"], "- alpha: A.", version=None, isInitial=False)
    write_chat(home, "p", "chat", [entry], 100)
    assert view(home)["claude_code"]["message"] == (
        "Kitden cannot read chat logs of this version of Claude Code yet, so it shows no result "
        "and no estimate."
    )


def test_a_second_window_that_drops_skills(home):
    own = home / ".claude/skills"
    names = [f"s{i}" for i in range(1, 9)]
    for name in names:
        skill(own, name, LONG[:1000])
    claude_chat(home, dict.fromkeys(names, LONG[:1000]))
    cc = view(home)["claude_code"]
    assert cc["checked"] is True
    other = cc["windows"][1]["result"]
    assert other["say"] == (
        "Estimate: On a 200K window, 1 of 8 skills would show only a name. "
        "The agent may not use it."
    )
    assert other["short"] == "1 of 8 would show only a name"
    assert other["misfit"] == {"kind": "name", "n": 1}
    assert cc["windows"][0]["result"]["misfit"] is None


def test_a_rule_that_does_not_rebuild_the_list_shows_no_estimate(home):
    own = home / ".claude/skills"
    skill(own, "alpha", "Does alpha.")
    skill(own, "beta", "Does beta.")
    # Everything fits in 30,000 characters, yet the log shows beta as a name only.
    claude_chat(home, {"alpha": "Does alpha.", "beta": None})
    cc = view(home)["claude_code"]
    assert cc["checked"] is False
    assert cc["message"] == NO_CHECK
    assert [w["tag"] for w in cc["windows"]] == ["Last chat · Nov 6"]
    assert cc["windows"][0]["result"]["say"].startswith("In your last chat on Nov 6, 1 of 2")
    assert cc["after"] is None


def test_a_name_only_skill_with_no_file_means_no_check(home):
    claude_chat(home, {"alpha": None})  # no file on disk: its size is not known
    cc = view(home)["claude_code"]
    assert (cc["checked"], cc["message"]) == (False, NO_CHECK)
    assert cc["windows"][0]["result"]["over"] == {}


def test_no_chat_yet(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    cc = view(home)["claude_code"]
    assert cc["message"] == (
        "No Claude Code chat yet. Open one chat, and Kitden will show what Claude Code sent."
    )
    assert (cc["lamp"], cc["fact"], cc["windows"], cc["checked"]) == ("none", None, [], False)
    assert cc["sides"] == ["Skills found", "Name only"]
    assert [(s["name"], s["side"]) for s in cc["skills"]] == [("alpha", 0)]


def test_unreadable_log(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    entry = list_entry(["alpha"], "- alpha: A.", version="2.2.0", isInitial=False)
    write_chat(home, "p", "chat", [entry], 100)
    cc = view(home)["claude_code"]
    assert cc["message"] == (
        "Kitden cannot read chat logs of Claude Code 2.2.0 yet, so it shows no result and no "
        "estimate."
    )
    assert (cc["lamp"], cc["fact"], cc["windows"]) == ("none", None, [])
    assert [s["name"] for s in cc["skills"]] == ["alpha"]


def test_no_skills(home):
    views = view(home)
    for client in ("claude_code", "codex", "cursor"):
        assert views[client]["message"] == "There is nothing to fit."
        assert views[client]["skills"] == []
        assert views[client]["lamp"] == "none"


def test_a_picked_project_without_its_own_chat_says_no_chat_yet(home, tmp_path):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(home, {"alpha": "Does alpha."}, folder="/work/a")
    other = tmp_path / "work/b"
    other.mkdir(parents=True)
    cc = view(home, folder=str(other))["claude_code"]
    assert cc["message"].startswith("No Claude Code chat yet.")
    assert (cc["fact"], cc["windows"]) == (None, [])


def test_a_budget_setting_that_is_not_a_number_is_ignored(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    write_json(home / ".claude/settings.json", {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "lots"}})
    claude_chat(home, {"alpha": "Does alpha."}, model="claude-sonnet-4-6")
    cc = view(home)["claude_code"]
    assert [(w["title"], w["budget"]) for w in cc["windows"]] == [
        ("200K window", 8_000),
        ("1M window", 30_000),
    ]


def test_the_project_settings_of_the_chat_set_the_limit(home, tmp_path):
    project = tmp_path / "work/a"
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    write_json(home / ".claude/settings.json", {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": 9000}})
    write_json(project / ".claude/settings.json", {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": 7000}})
    claude_chat(home, {"alpha": "Does alpha."}, folder=str(project))
    assert view(home)["claude_code"]["windows"][0]["budget"] == 7000


def test_a_model_not_in_the_table_gets_the_fact_and_no_estimate(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(home, {"alpha": "Does alpha."}, model="claude-new-9")
    cc = view(home)["claude_code"]
    assert (cc["checked"], cc["message"]) == (False, NO_CHECK)
    [fact] = cc["windows"]
    assert fact["budget"] is None
    assert fact["result"]["say"] == (
        "In your last chat on Nov 6, your one skill was sent with its description."
    )
    assert fact["result"]["room"] is None


def draft_home(home):
    """x is set to Name only and used most; the room fits one long description."""
    own = home / ".claude/skills"
    skill(own, "x", LONG[:1000])
    skill(own, "a", LONG[:1000])
    skill(own, "b", LONG[:400])
    skill(own, "c", LONG[:400])
    write_json(
        home / ".claude/settings.json",
        {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "1050"}, "skillOverrides": {"x": "name-only"}},
    )
    usage(home, {"x": 100, "a": 10, "b": 5, "c": 1})
    claude_chat(home, {"x": None, "a": LONG[:1000], "b": None, "c": None})


def test_a_draft_name_only_shows_after_apply_with_both_sides(home):
    draft_home(home)
    cc = view(home)["claude_code"]
    assert cc["checked"] is True
    assert {s["name"]: s["state"] for s in cc["skills"]}["x"] == "name-only"
    assert cc["after"] is None

    freed = view(home, draft={"claude_code": {"a": "name-only"}})["claude_code"]["after"]
    # The limit is the setting, not the window: the sentence does not name a window.
    assert freed["say"] == (
        "After Apply, estimate: With this limit, everything would fit. 2 skills show only a "
        "name, as you chose. b and c get descriptions."
    )
    assert (freed["gets"], freed["loses"]) == (["b", "c"], [])
    assert freed["say"].endswith("b and c get descriptions.")

    taken = view(home, draft={"claude_code": {"x": "on"}})["claude_code"]["after"]
    assert (taken["gets"], taken["loses"]) == ([], ["a"])
    assert taken["say"].endswith("a loses its description.")
    assert set(taken["result"]["sent"]) == {"x"}


def test_a_draft_that_changes_nothing_shows_no_after(home):
    draft_home(home)
    cc = view(home, draft={"claude_code": {"x": "name-only"}})["claude_code"]
    assert cc["after"] is None


def test_no_after_apply_when_the_check_fails(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    skill(home / ".claude/skills", "beta", "Does beta.")
    claude_chat(home, {"alpha": "Does alpha.", "beta": None})
    cc = view(home, draft={"claude_code": {"alpha": "off"}})["claude_code"]
    assert (cc["checked"], cc["after"]) == (False, None)


def test_plugin_skills_have_no_switch_in_claude_code(home):
    install = home / ".claude/plugins/cache/market/plug/1.0.0"
    skill(install / "skills", "tool", "Does tool.")
    write_json(
        home / ".claude/plugins/installed_plugins.json",
        {"plugins": {"plug@market": [{"installPath": str(install)}]}},
    )
    skill(home / ".claude/skills", "own", "Does own.")
    claude_chat(home, {"plug:tool": "Does tool.", "own": "Does own.", "dataviz": "Charts."})
    rows = {s["name"]: s for s in view(home)["claude_code"]["skills"]}
    assert rows["plug:tool"]["shown"] == "tool"
    assert rows["plug:tool"]["item"] is not None
    assert rows["plug:tool"]["switch"] == []
    assert "plugin" in rows["plug:tool"]["note"]
    assert rows["own"]["switch"] == ["on", "name-only", "off"]
    assert rows["dataviz"]["item"] is None
    assert rows["dataviz"]["switch"] == []
    assert rows["dataviz"]["note"] == "Claude Code always sends built-in skills in full."


def test_a_skill_not_in_the_last_list_is_shown_apart(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    skill(home / ".claude/skills", "later", "Added after the chat.")
    claude_chat(home, {"alpha": "Does alpha."})
    rows = {s["name"]: s for s in view(home)["claude_code"]["skills"]}
    assert rows["later"]["side"] is None
    assert rows["later"]["note"] == "It was not in the list of your last chat."


# Codex

CODEX_A = "Turns rough notes into a tidy plan with steps, owners and dates for the week ahead."
CODEX_B = "Checks a pull request for bugs, missing tests and unclear names, then writes a review."
CODEX_C = "Says hello."


def codex_home(home, *, window=None, limit=None):
    """Three skills in ~/.agents/skills; the model cache gives gpt-6-astra `window`."""
    folder = home / ".agents/skills"
    paths = {
        "alpha": str(skill(folder, "alpha", CODEX_A).resolve()),
        "beta": str(skill(folder, "beta", CODEX_B).resolve()),
        "gamma": str(skill(folder, "gamma", CODEX_C).resolve()),
    }
    models = [{"slug": "gpt-6-astra", "display_name": "gpt-6-astra", "context_window": window}]
    if window:
        models.append(
            {"slug": "gpt-6.1-sol", "display_name": "gpt-6.1-sol", "context_window": 500_000}
        )
    write_json(home / ".codex/models_cache.json", {"models": models})
    if limit is not None:
        (home / ".codex/config.toml").write_text(f"[skills]\nmax_context_tokens = {limit}\n")
    return paths


def codex_chat(home, lines, at="2026-10-30T12:00:00Z"):
    text = "<skills_instructions>\n" + "\n".join(lines) + "\n</skills_instructions>"
    write_log(home / ".codex", "a", [meta(), turn(), codex_list_entry(text, at=at)], 100)


def rule_skills(paths):
    return [
        CodexSkill("alpha", CODEX_A, paths["alpha"]),
        CodexSkill("beta", CODEX_B, paths["beta"]),
        CodexSkill("gamma", CODEX_C, paths["gamma"]),
    ]


def a_budget(paths, wanted):
    """The smallest budget whose rule result passes `wanted`."""
    return next(b for b in range(100, 2000) if wanted(codex_rule(rule_skills(paths), b)))


def window_for(budget):
    """A window whose 2% is `budget`."""
    return next(w for w in range(budget * 50, budget * 50 + 50) if int(w * 0.02) == budget)


def test_codex_cut_short(home):
    paths = codex_home(home, window=1)
    budget = a_budget(paths, lambda fit: fit.cap is not None and fit.cap >= 30)
    cap = codex_rule(rule_skills(paths), budget).cap
    codex_home(home, window=window_for(budget))
    # Codex cut alpha to the shared length; beta one shorter, as a cut can end on a space.
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A[:cap]} (file: {paths['alpha']})",
            f"- beta: {CODEX_B[: cap - 1]} (file: {paths['beta']})",
            f"- gamma: {CODEX_C} (file: {paths['gamma']})",
        ],
    )
    cx = view(home)["codex"]
    assert cx["lede"].endswith("Codex lets this list use 2% of the context window.")
    assert (cx["lamp"], cx["unit"], cx["checked"], cx["message"]) == ("warn", "tokens", True, None)
    fact = cx["windows"][0]
    assert fact["tag"] == "Last chat · Oct 30"
    assert fact["result"]["say"] == (
        f"In your last chat on Oct 30, 2 of 3 descriptions were cut to {cap - 1}–{cap} "
        "characters. The agent saw only their start."
    )
    assert fact["result"]["short"] == "2 of 3 cut short"
    assert fact["result"]["misfit"] == {"kind": "cut", "n": 2}
    assert set(fact["result"]["over"]) == {"alpha", "beta"}
    other = cx["windows"][1]
    assert (other["title"], other["tag"], other["budget"]) == ("500K window", "Estimate", 10_000)
    assert other["result"]["say"] == (
        "Estimate: On a 500K window, every skill would keep its full description."
    )
    assert cx["sides"] == ["Full description", "Cut short"]
    rows = {s["name"]: s for s in cx["skills"]}
    assert {n: r["side"] for n, r in rows.items()} == {"alpha": 1, "beta": 1, "gamma": 0}
    assert rows["alpha"]["switch"] == ["on", "off"]
    assert rows["alpha"]["size"] == len(CODEX_A)
    assert cx["how"][2] == (
        "Before it shows an estimate, Kitden checks that the rule cuts the same skills as your "
        "last chat. It does: the same 2."
    )


def test_codex_left_out(home):
    paths = codex_home(home, window=1)
    budget = a_budget(paths, lambda fit: fit.sent == {"alpha": 0, "beta": 0, "gamma": None})
    codex_home(home, window=window_for(budget))
    before_the_chat(Path(paths["gamma"]))
    codex_chat(
        home,
        [f"- alpha: (file: {paths['alpha']})", f"- beta: (file: {paths['beta']})"],
        at="2026-11-07T12:00:00Z",
    )
    cx = view(home)["codex"]
    assert cx["checked"] is True
    fact = cx["windows"][0]
    assert fact["result"]["say"] == (
        "In your last chat on Nov 7, Codex removed every description and left 1 of 3 skills out "
        "of the list. The agent did not see it at all."
    )
    assert fact["result"]["short"] == "1 left out, the rest name only"
    assert fact["result"]["misfit"] == {"kind": "out", "n": 1}
    assert "gamma" not in fact["result"]["sent"]
    assert {s["name"]: s["side"] for s in cx["skills"]}["gamma"] == 1


def test_codex_everything_fits_and_a_new_skill_is_not_left_out(home):
    paths = codex_home(home, window=272_000)
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A} (file: {paths['alpha']})",
            f"- beta: {CODEX_B} (file: {paths['beta']})",
        ],
    )
    cx = view(home)["codex"]
    fact = cx["windows"][0]
    # gamma came after the chat: it was not left out, it was not there.
    assert fact["result"]["say"] == (
        "In your last chat on Oct 30, all 2 skills were sent with full descriptions."
    )
    assert fact["result"]["room"].startswith("Estimate: about ")
    assert fact["result"]["room"].endswith(" tokens left before the limit.")
    assert {s["name"]: s["side"] for s in cx["skills"]}["gamma"] is None


def test_codex_one_skill_and_a_bad_timestamp_read_plainly(home):
    paths = codex_home(home, window=272_000)
    codex_chat(home, [f"- alpha: {CODEX_A} (file: {paths['alpha']})"], at="not a time")
    cx = view(home)["codex"]
    fact = cx["windows"][0]
    assert fact["result"]["say"] == (
        "In your last chat, your one skill was sent with its full description."
    )
    assert fact["tag"] == "Last chat"
    assert cx["how"][0] == (
        "Last chat: the list Codex 0.163.0-alpha.11 sent, read from its chat log."
    )
    assert cx["how"][-2] == (
        "Full sizes come from your skill files today. They may have changed since the chat."
    )


def test_codex_check_that_never_ran_is_not_called_a_mismatch(home):
    paths = codex_home(home)  # the model cache gives no window: no limit to run the rule with
    codex_chat(home, [f"- alpha: {CODEX_A} (file: {paths['alpha']})"])
    cx = view(home)["codex"]
    assert cx["checked"] is False
    assert cx["how"][2].endswith("This time Kitden could not run the check.")


def test_codex_with_no_files_found_gives_no_full_or_cut_verdict(home):
    codex_home(home, window=272_000)
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A[:30]} (file: /gone/alpha/SKILL.md)",
            f"- beta: {CODEX_B} (file: /gone/beta/SKILL.md)",
        ],
        at="2026-10-29T12:00:00Z",
    )
    cx = view(home)["codex"]
    assert (cx["lamp"], cx["checked"], cx["message"]) == ("none", False, NO_CHECK)
    fact = cx["windows"][0]["result"]
    assert fact["say"] == (
        "In your last chat on Oct 29, Codex sent 2 skills. Kitden cannot find all their files, "
        "so it cannot tell if any were cut."
    )
    assert fact["room"] is None
    assert fact["over"] == {}
    # No pill on the full or the cut side either.
    rows = {s["name"]: s for s in cx["skills"] if s["name"] in ("alpha", "beta")}
    assert {n: r["side"] for n, r in rows.items()} == {"alpha": None, "beta": None}
    assert rows["alpha"]["note"] == "Kitden cannot find its file, so it cannot tell if it was cut."


def test_codex_sends_at_most_1024_characters_and_that_is_not_a_cut(home):
    paths = codex_home(home, window=272_000)
    long = "Plans" * 300  # 1,500 characters
    paths["delta"] = str(skill(home / ".agents/skills", "delta", long).resolve())
    lines = [f"- {s.name}: {s.description} (file: {s.path})" for s in rule_skills(paths)]
    codex_chat(home, [*lines, f"- delta: {long[:1024]} (file: {paths['delta']})"])
    cx = view(home)["codex"]
    assert (cx["lamp"], cx["checked"]) == ("ok", True)
    fact = cx["windows"][0]["result"]
    assert fact["say"] == (
        "In your last chat on Oct 30, all 4 skills were sent with full descriptions."
    )
    assert fact["misfit"] is None
    delta = {s["name"]: s for s in cx["skills"]}["delta"]
    assert delta["side"] == 0
    assert delta["note"] == (
        "Codex sends only the first 1,024 characters of a description. "
        "Off frees room, so long descriptions get cut less."
    )


def test_codex_a_known_cut_is_told_when_another_file_is_gone(home):
    paths = codex_home(home, window=272_000)
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A[:29]} (file: {paths['alpha']})",
            f"- beta: {CODEX_B} (file: /gone/beta/SKILL.md)",
        ],
        at="2026-10-29T12:00:00Z",
    )
    cx = view(home)["codex"]
    assert cx["lamp"] == "warn"
    fact = cx["windows"][0]["result"]
    assert fact["say"] == (
        "In your last chat on Oct 29, 1 of 2 descriptions was cut to 29 characters. "
        "The agent saw only its start. "
        "Kitden cannot find the file of 1 more, so it cannot tell if it was cut."
    )
    assert fact["misfit"] == {"kind": "cut", "n": 1}
    assert {s["name"]: s["side"] for s in cx["skills"]}["alpha"] == 1


def test_codex_a_skill_written_after_a_names_only_chat_was_not_left_out(home):
    paths = codex_home(home, window=272_000)
    after = datetime(2026, 11, 8, tzinfo=UTC).timestamp()
    os.utime(paths["gamma"], (after, after))
    codex_chat(
        home,
        [f"- alpha: (file: {paths['alpha']})", f"- beta: (file: {paths['beta']})"],
        at="2026-11-07T12:00:00Z",
    )
    cx = view(home)["codex"]
    fact = cx["windows"][0]["result"]
    assert fact["say"] == (
        "In your last chat on Nov 7, Codex removed every description. The agent saw only the names."
    )
    assert fact["misfit"] == {"kind": "cut", "n": 2}
    gamma = {s["name"]: s for s in cx["skills"]}["gamma"]
    assert (gamma["side"], gamma["note"]) == (None, "It was not in the list of your last chat.")


def a_small_window(home, paths, wanted):
    """A 272K last chat that sent everything in full, and a small second window whose rule
    result passes `wanted`."""
    budget = a_budget(paths, wanted)
    small = window_for(budget)
    models = [
        {"slug": "gpt-6-astra", "display_name": "gpt-6-astra", "context_window": 272_000},
        {"slug": "gpt-tiny", "display_name": "gpt-tiny", "context_window": small},
    ]
    write_json(home / ".codex/models_cache.json", {"models": models})
    codex_chat(home, [f"- {s.name}: {s.description} (file: {s.path})" for s in rule_skills(paths)])
    cx = view(home)["codex"]
    assert cx["checked"] is True
    return codex_rule(rule_skills(paths), budget), _size_of(small), cx["windows"][1]["result"]


def _size_of(window):
    return f"{round(window / 1000)}K"


def test_codex_estimate_cut(home):
    paths = codex_home(home)
    fit, size, other = a_small_window(home, paths, lambda f: f.cap is not None and f.cap >= 30)
    about = round(fit.cap / 10) * 10
    assert other["say"] == (
        f"Estimate: On a {size} window, 2 of 3 descriptions would be cut to about {about} "
        "characters."
    )
    assert other["short"] == "2 of 3 would be cut short"
    assert other["misfit"] == {"kind": "cut", "n": 2}


def test_codex_estimate_left_out(home):
    paths = codex_home(home)
    wanted = {"alpha": 0, "beta": 0, "gamma": None}
    _, size, other = a_small_window(home, paths, lambda f: f.sent == wanted)
    assert other["say"] == (
        f"Estimate: On a {size} window, 1 of 3 skills would be left out and no description sent."
    )
    assert other["misfit"] == {"kind": "out", "n": 1}


def test_codex_names_only_with_nothing_left_out(home):
    paths = codex_home(home, window=272_000)
    codex_chat(home, [f"- {n}: (file: {paths[n]})" for n in ("alpha", "beta", "gamma")])
    fact = view(home)["codex"]["windows"][0]["result"]
    assert fact["say"] == (
        "In your last chat on Oct 30, Codex removed every description. The agent saw only the "
        "names."
    )


def test_codex_unreadable_log(home):
    codex_home(home, window=272_000)
    write_log(home / ".codex", "a", [meta(version="0.200.0"), turn()], 100)
    cx = view(home)["codex"]
    assert cx["message"] == (
        "Kitden cannot read chat logs of Codex 0.200.0 yet, so it shows no result and no estimate."
    )
    assert (cx["lamp"], cx["fact"], cx["windows"]) == ("none", None, [])


def test_a_codex_plugin_skill_from_the_log_has_no_item_to_switch(home):
    # Codex's scan has no plugin skill items, and skill.rule refuses a plugin-scope Codex skill,
    # so a plugin skill of the list has no switch; its own skills have On and Off.
    paths = codex_home(home, window=272_000)
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A} (file: {paths['alpha']})",
            "- plug:tool: Does tool. (file: /p/tool/SKILL.md)",
        ],
    )
    rows = {s["name"]: s for s in view(home)["codex"]["skills"]}
    assert (rows["plug:tool"]["item"], rows["plug:tool"]["switch"]) == (None, [])
    assert rows["alpha"]["switch"] == ["on", "off"]


def test_codex_limit_from_config_toml(home):
    paths = codex_home(home, window=272_000, limit=900)
    codex_chat(
        home,
        [
            f"- {n}: {d} (file: {paths[n]})"
            for n, d in (("alpha", CODEX_A), ("beta", CODEX_B), ("gamma", CODEX_C))
        ],
    )
    cx = view(home)["codex"]
    fact, default = cx["windows"]
    assert (fact["title"], fact["models"], fact["tag"], fact["budget"]) == (
        "900 tokens",
        "Set in config.toml",
        "Last chat · Oct 30",
        900,
    )
    assert (default["title"], default["models"], default["tag"], default["budget"]) == (
        "272K window",
        "Default limit",
        "Estimate",
        5_440,
    )
    assert cx["lede"].endswith("Your config.toml limits this list to 900 tokens.")


def test_codex_draft_off_shows_after_apply(home):
    paths = codex_home(home, window=1)
    budget = a_budget(paths, lambda fit: fit.cap is not None and fit.cap >= 30)
    cap = codex_rule(rule_skills(paths), budget).cap
    codex_home(home, window=window_for(budget))
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A[:cap]} (file: {paths['alpha']})",
            f"- beta: {CODEX_B[:cap]} (file: {paths['beta']})",
            f"- gamma: {CODEX_C} (file: {paths['gamma']})",
        ],
    )
    after = view(home, draft={"codex": {"beta": "off"}})["codex"]["after"]
    assert after["say"].startswith("After Apply, estimate:")
    assert after["gets"] == ["alpha"]
    assert after["say"].endswith("alpha gets its full description.")


# Cursor


def test_cursor_has_no_verdict(home):
    folder = home / ".cursor/skills"
    skill(folder, "free", "Picks itself.")
    skill(folder, "asked", "Only on request.", "disable-model-invocation: true\n")
    cu = view(home)["cursor"]
    assert cu["message"] == (
        "Kitden cannot see what Cursor sends, so it cannot tell if your skills fit."
    )
    assert cu["lede"].endswith("Cursor does not publish a limit for this list.")
    assert (cu["lamp"], cu["fact"], cu["windows"], cu["checked"], cu["after"]) == (
        "none",
        None,
        [],
        False,
        None,
    )
    assert cu["sides"] == ["The agent can pick it", "Only when you ask"]
    assert {s["name"]: s["side"] for s in cu["skills"]} == {"asked": 1, "free": 0}


def test_cursor_skills_have_no_switch(home):
    skill(home / ".cursor/skills", "free", "Picks itself.")
    [row] = view(home)["cursor"]["skills"]
    assert row["switch"] == []
    assert row["item"] is not None


def test_a_skill_says_its_source_and_a_project_skill_names_its_project(home, tmp_path):
    # A rule for a project's own skill must name that project (changes/actions.py), so the page
    # gets its id; a user skill has none.
    from kitden.model import Project

    project = tmp_path / "work/a"
    write_json(home / ".claude.json", {"projects": {str(project): {}}})
    skill(project / ".claude/skills", "local", "Does local.")
    skill(home / ".claude/skills", "own", "Does own.")
    install = home / ".claude/plugins/cache/market/plug/1.0.0"
    skill(install / "skills", "tool", "Does tool.")
    write_json(
        home / ".claude/plugins/installed_plugins.json",
        {"plugins": {"plug@market": [{"installPath": str(install)}]}},
    )
    sent = {"local": "Does local.", "own": "Does own.", "plug:tool": "Does tool.", "dataviz": "x"}
    claude_chat(home, sent, folder=str(project))
    rows = {s["name"]: (s["project"], s["source"]) for s in view(home)["claude_code"]["skills"]}
    assert rows["local"] == (Project(str(project), True).id, "Project a")
    assert rows["own"] == (None, "Your skills")
    assert rows["plug:tool"] == (None, "Plugin plug")
    assert rows["dataviz"] == (None, "Built into Claude Code")


def test_a_codex_skill_that_is_off_has_no_on_to_offer(home):
    # Codex only writes `enabled = false`; turning it back on stays an Undo in Changes. A skill
    # that is off is not loaded, so it has no item here, and so no switch (no On to press).
    paths = codex_home(home, window=272_000)
    with (home / ".codex/config.toml").open("a") as config:
        config.write(f'\n[[skills.config]]\npath = "{paths["beta"]}"\nenabled = false\n')
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A} (file: {paths['alpha']})",
            f"- beta: {CODEX_B} (file: {paths['beta']})",
        ],
    )
    rows = {s["name"]: s for s in view(home)["codex"]["skills"]}
    assert (rows["beta"]["item"], rows["beta"]["switch"]) == (None, [])
    assert rows["alpha"]["switch"] == ["on", "off"]


# The window worked out from the list


def eight_skills(home, *, model, sent=7):
    """Eight skills of 1,000 characters; the log sent the first `sent` with a description.
    A limit of 8,000 characters (a 200K window at 4 per token) keeps 7, 6,000 keeps 5, and a
    1M window keeps all 8."""
    names = [f"s{i}" for i in range(1, 9)]
    for name in names:
        skill(home / ".claude/skills", name, LONG[:1000])
    claude_chat(
        home, {n: LONG[:1000] if i < sent else None for i, n in enumerate(names)}, model=model
    )


def test_a_model_not_in_the_table_gets_the_one_window_that_gives_its_list(home):
    eight_skills(home, model="claude-new-9")
    cc = view(home)["claude_code"]
    assert (cc["checked"], cc["message"]) == (True, None)
    fact, other = cc["windows"]
    assert (fact["title"], fact["budget"]) == ("200K window", 8000)
    assert fact["models"] == "New 9 · in the Claude app · worked out from the list"
    assert other["title"] == "1M window"
    assert (
        "The chat log does not say the window. Only a 200K window gives this list, "
        "so Kitden shows it."
    ) in cc["how"]


def test_a_model_that_ran_with_the_other_window_than_the_table_says(home):
    eight_skills(home, model="claude-opus-5-5")
    cc = view(home)["claude_code"]
    assert cc["checked"] is True
    assert cc["windows"][0]["title"] == "200K window"
    assert cc["windows"][0]["models"].endswith("worked out from the list")


def test_a_window_with_two_limits_that_give_the_list_shows_no_estimate(home):
    skill(home / ".claude/skills", "alpha", LONG[:1000])
    built_in = ("dataviz", "simplify", "loop", "schedule", "run", "code-review")
    sent = dict.fromkeys(built_in, "x" * 1536) | {"alpha": None}
    # The built-in skills alone pass 8,000 characters: alpha shows a name at 6,000 and at 8,000.
    claude_chat(home, sent, model="claude-new-9")
    cc = view(home)["claude_code"]
    assert cc["checked"] is False
    assert cc["message"] == (
        "Two limits give the list of your last chat, so Kitden shows no estimate."
    )
    [fact] = cc["windows"]
    assert (fact["title"], fact["budget"]) == ("200K window", None)
    assert cc["after"] is None


def test_a_list_every_window_gives_keeps_the_window_unknown(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    claude_chat(home, {"alpha": "Does alpha."}, model="claude-new-9")
    cc = view(home)["claude_code"]
    assert cc["windows"][0]["title"] == "Unknown window"
    assert cc["windows"][0]["models"] == "New 9 · in the Claude app"


def test_a_skill_of_unknown_size_does_not_hide_the_window_when_no_size_changes_the_list(home):
    built_in = ("dataviz", "simplify", "loop", "schedule", "run", "code-review")
    # ghost has no file. The built-in skills alone pass 8,000 characters, so it shows only a
    # name on a 200K window whatever its size, and gets a description on a 1M window.
    claude_chat(home, dict.fromkeys(built_in, "x" * 1536) | {"ghost": None}, model="claude-new-9")
    cc = view(home)["claude_code"]
    assert cc["windows"][0]["title"] == "200K window"
    assert cc["checked"] is False


# Review of 2026-11-10


def test_a_window_worked_out_from_the_list_names_no_models_on_the_other_card(home):
    # The table says Opus 5.5 has a 1M window, yet this chat's list is the one of a 200K window.
    eight_skills(home, model="claude-opus-5-5")
    other = view(home)["claude_code"]["windows"][1]
    assert (other["title"], other["models"], other["budget"]) == ("1M window", "", 40_000)


def test_a_missing_description_the_limit_does_not_explain_is_not_blamed_on_room(home):
    own = home / ".claude/skills"
    skill(own, "alpha", "Does alpha.")
    skill(own, "beta", "Does beta.")
    claude_chat(home, {"alpha": "Does alpha.", "beta": None})
    cc = view(home)["claude_code"]
    assert cc["checked"] is False
    notes = {s["name"]: s["note"] for s in cc["skills"]}
    assert notes["beta"] == (
        "Its description was not sent in your last chat. Kitden cannot tell why."
    )


def test_no_room_gives_advice_only_when_a_skill_can_be_switched(home):
    skill(home / ".claude/skills", "alpha", LONG[:1000])
    built_in = ("dataviz", "simplify", "loop", "schedule", "run", "code-review")
    # Only built-in skills have a description here, and they have no switch.
    sent = dict.fromkeys(built_in, "x" * 1536) | {"alpha": None}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    cc = view(home)["claude_code"]
    assert cc["checked"] is True
    notes = {s["name"]: s["note"] for s in cc["skills"]}
    assert notes["alpha"] == "No room for its description."


def test_no_room_with_a_skill_to_switch_keeps_the_advice(home):
    eight_skills(home, model="claude-sonnet-4-6")
    notes = {s["name"]: s["note"] for s in view(home)["claude_code"]["skills"]}
    assert notes["s8"] == (
        "No room for its description. Set a skill with a description to Name only or Off to "
        "free room."
    )


def test_a_claude_limit_from_settings_is_named_in_the_lede(home):
    skill(home / ".claude/skills", "alpha", "Does alpha.")
    write_json(home / ".claude/settings.json", {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": 9000}})
    claude_chat(home, {"alpha": "Does alpha."})
    assert view(home)["claude_code"]["lede"] == (
        "Every chat starts with a list of your skills. The agent reads it to choose the right "
        "skill. Your Claude Code settings limit this list to 9,000 characters."
    )


def test_a_codex_limit_above_the_most_codex_allows_says_so(home):
    paths = codex_home(home, window=272_000, limit=50_000)
    codex_chat(
        home,
        [
            f"- {n}: {d} (file: {paths[n]})"
            for n, d in (("alpha", CODEX_A), ("beta", CODEX_B), ("gamma", CODEX_C))
        ],
    )
    fact = view(home)["codex"]["windows"][0]
    assert (fact["title"], fact["models"], fact["budget"]) == (
        "10,000 tokens",
        "config.toml says 50,000; Codex allows 10,000 at most",
        10_000,
    )
    assert view(home)["codex"]["lede"].endswith("Codex lets this list use 10,000 tokens at most.")


def test_codex_estimate_says_one_description_for_one_skill():
    one = [CodexSkill("alpha", CODEX_A, "/work/skills/alpha/SKILL.md")]
    budget = next(b for b in range(100, 400) if (codex_rule(one, b).cap or 0) >= 30)
    fit = codex_rule(one, budget)
    assert fit.cap < len(CODEX_A)
    say = _codex_estimate(one, fit, "On a 9K window", "Estimate: {}")["say"]
    about = round(fit.cap / 10) * 10
    assert say == (
        f"Estimate: On a 9K window, 1 of 1 description would be cut to about {about} characters."
    )


def test_codex_estimate_with_a_cut_of_a_few_characters_does_not_round_it_to_zero(home):
    paths = codex_home(home)
    _, size, other = a_small_window(home, paths, lambda f: f.cap == 1)
    assert other["say"] == (
        f"Estimate: On a {size} window, 3 of 3 descriptions would be cut to about 1 character."
    )


def test_codex_estimate_that_removes_every_description_says_so(home):
    paths = codex_home(home)
    _, size, other = a_small_window(home, paths, lambda f: f.cap == 0)
    assert other["say"] == (
        f"Estimate: On a {size} window, Codex would remove every description. "
        "The agent would see only the names."
    )
