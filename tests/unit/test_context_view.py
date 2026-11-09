"""The Context read model, from sandbox homes with small fixture chat logs (spec "States")."""

import json
from pathlib import Path

import pytest

from kitden.context.rules import CodexSkill, codex_rule
from kitden.views.context_view import context_view
from kitden.views.inventory import build_inventory
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
    assert fact["result"]["room"] is None
    assert set(fact["result"]["sent"]) == {"alpha", "beta"}
    assert fact["result"]["over"] == {"gamma": 1002, "delta": 1002}
    assert {s["name"]: s["side"] for s in cc["skills"]} == {
        "alpha": 0,
        "beta": 0,
        "gamma": 1,
        "delta": 1,
    }


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
        "In your last chat on Nov 6, all 1 skills were sent with their descriptions."
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
        "of the list. The agent did not see them at all."
    )
    assert fact["result"]["short"] == "1 left out, the rest name only"
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
