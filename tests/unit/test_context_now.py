"""The skill list for the setup as it is now, when the setup is not the one the last chat was sent
under: the sentence under the last chat's verdict, the estimate the picture follows, and the limit
line's places with the preview's changes in them. The chats are those of test_skill_limit."""

import os
from pathlib import Path

import pytest

from kitden.context.rules import CodexSkill, codex_rule
from kitden.views import words
from kitden.views.context_view import _size
from tests.unit.test_codex_limit import cut_chat as codex_cut_chat
from tests.unit.test_context_claude_log import assistant, list_entry, write_chat
from tests.unit.test_context_view import (
    CODEX_A,
    CODEX_B,
    CODEX_C,
    a_budget,
    before_the_chat,
    claude_chat,
    codex_chat,
    codex_home,
    rule_skills,
    skill,
    view,
    window_for,
    write_json,
)
from tests.unit.test_skill_limit import NAMES, TEXT, counted_chat, cut_chat, near_chat

CHANGED = "Your skills changed after this list was sent. Your next chat will show the real list."
KEEPS = "Estimate: On a 200K window, every skill would keep its description."
NO_RULE = words.NOW_NO_RULE.format(client="{}")


def about(bad: int, n: int) -> str:
    """The estimate by a count where not all fit: about how many, not which."""
    return (
        f"Estimate: On a 200K window, about {bad} of {n} skills would show only a name. "
        "Kitden counted them and cannot tell which."
    )


@pytest.fixture
def home(tmp_path):
    home = tmp_path / "home"
    for root in (".claude", ".codex", ".cursor"):
        (home / root).mkdir(parents=True)
    return home


def overrides(home, **states):
    write_json(home / ".claude/settings.json", {"skillOverrides": states})


def claude(home, draft=None, limit=None):
    asked = {"claude_code": draft or {}}
    if limit is not None:
        asked["limits"] = {"claude_code": limit}
    return view(home, draft=asked)["claude_code"]


def places(card):
    """Each place of the limit line, by its value, in the words of its readout."""
    return {step["value"]: step["say"] for step in card["limit"]["steps"]}


# The sentence under the last chat's verdict


def test_skills_added_after_the_chat_are_said_at_rest(home):
    cut_chat(home)
    before = claude(home)
    assert before["changed"] == [] and before["now"] is None
    for n in "123":
        skill(home / ".claude/skills", f"later{n}", TEXT)
    cc = claude(home)
    assert cc["changed"] == [
        CHANGED,
        "Estimate: On a 200K window, 4 of 10 skills would show only a name. The agent may not "
        "use them.",
    ]
    # The picture follows the same estimate: six sent, four over the limit.
    assert set(cc["now"]["sent"]) == set(NAMES[:-1])
    assert set(cc["now"]["over"]) == {"g", "later1", "later2", "later3"}
    assert cc["now"]["misfit"]["n"] == 4 and cc["now"]["room"] is None
    assert cc["now"]["budget"] == 8_000
    # The limit line counts the same, and the last chat's fact stays.
    assert places(cc)[0.01] == "1% now · 4 of 10 show only a name"
    assert cc["windows"][0] == before["windows"][0]
    assert cc["lamp"] == "warn"


def test_a_skill_turned_off_after_the_chat_can_make_everything_fit(home):
    cut_chat(home)
    overrides(home, a="off")
    cc = claude(home)
    assert cc["changed"] == [CHANGED, KEEPS]
    assert set(cc["now"]["sent"]) == set("bcdefg") and cc["now"]["over"] == {}
    # 6 x (1 + 4 + 1,200) + 5 = 7,235 characters of 8,000.
    assert cc["now"]["room"] == "Estimate: about 765 characters left before the limit."
    assert cc["windows"][0]["result"]["short"] == "1 of 7 showed only a name"
    assert cc["limit"]["why"] == words.LIMIT_NOT_NEEDED


def test_a_cut_skill_set_to_name_only_after_the_chat_is_said(home):
    cut_chat(home)
    overrides(home, g="name-only")
    cc = claude(home)
    # Kitden cannot see that it was on in the chat, so there it stays a misfit.
    assert cc["windows"][0]["result"]["misfit"]["n"] == 1
    # And so it does not say that a skill changed: only what it expects now.
    assert cc["changed"] == [
        "Estimate: On a 200K window, everything would fit. 1 skill shows only a name, as you "
        "chose.",
    ]
    # Set before the chat, the fact already says it, and nothing changed.
    before_the_chat(home / ".claude/settings.json")
    cc = claude(home)
    assert cc["windows"][0]["result"]["misfit"] is None
    assert cc["changed"] == [] and cc["now"] is None


def test_a_sent_skill_set_to_name_only_after_the_chat_is_said(home):
    cut_chat(home)
    overrides(home, a="name-only")
    cc = claude(home)
    assert cc["changed"][0] == CHANGED
    assert "1 skill shows only a name, as you chose." in cc["changed"][1]
    assert "a" not in cc["now"]["sent"] and "a" not in cc["now"]["over"]


def test_skills_added_during_the_chat_are_said(home):
    # The list it started with fits; the one added later was sent whole, outside the limit.
    for name in [*NAMES[:-1], "late"]:
        skill(home / ".claude/skills", name, TEXT)
    first = list_entry(list(NAMES[:-1]), "\n".join(f"- {n}: {TEXT}" for n in NAMES[:-1]))
    late = list_entry(["late"], f"- late: {TEXT}", isInitial=False)
    write_chat(home, "p", "chat", [first, late, assistant("claude-sonnet-4-6")], 100)
    cc = claude(home)
    assert cc["checked"] and cc["windows"][0]["result"]["misfit"] is None
    assert cc["changed"][0] == CHANGED
    assert cc["changed"][1].startswith("Estimate: On a 200K window, 1 of 7 skills would show only")


def test_nothing_is_said_when_the_skills_are_the_same(home):
    cut_chat(home)
    # Another setting, and a skill that is off or only asked for, change no list.
    asked = "disable-model-invocation: true\n"
    skill(home / ".claude/skills", "later", TEXT, extra=asked)
    skill(home / ".claude/skills", "away", TEXT)
    write_json(
        home / ".claude/settings.json",
        {"skillOverrides": {"away": "off"}, "model": "sonnet"},
    )
    cc = claude(home)
    assert cc["checked"] and cc["changed"] == [] and cc["now"] is None


def test_the_limit_and_the_skills_changed(home):
    cut_chat(home)
    skill(home / ".claude/skills", "later", TEXT)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.012})
    cc = claude(home)
    # 8,446 + 1,211 = 9,657 characters, over 9,600 (1.2%).
    assert cc["changed"] == [
        "The limit and your skills changed after this list was sent: the limit is 1.2% now. Your "
        "next chat will show the real list.",
        "Estimate: On a 200K window, 1 of 8 skills would show only a name. The agent may not use "
        "it.",
    ]
    assert cc["windows"][0]["budget"] == 8_000


def test_the_limit_changed_alone_gives_the_picture_its_estimate_too(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.015})
    cc = claude(home)
    assert cc["changed"][0].startswith("The limit was changed after this chat: it is 1.5% now.")
    assert set(cc["now"]["sent"]) == set(NAMES) and cc["now"]["over"] == {}


def test_a_fixed_limit_is_said_with_its_own_words(home):
    for name in "abc":
        skill(home / ".claude/skills", name, TEXT[:900])
    write_json(home / ".claude/settings.json", {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "2800"}})
    claude_chat(home, dict.fromkeys("abc", TEXT[:900]), model="claude-sonnet-4-6")
    assert claude(home)["changed"] == []
    skill(home / ".claude/skills", "later", TEXT[:900])
    cc = claude(home)
    assert cc["changed"][0] == CHANGED
    assert cc["changed"][1].startswith("Estimate: With this limit, 1 of 4 skills would show only")


def test_details_notes_go_by_the_estimate_for_now(home):
    cut_chat(home)
    # later is used less than a..g, so g still has no room, and later has none.
    skill(home / ".claude/skills", "later", TEXT)
    overrides(home, a="off")
    notes = {s["name"]: s["note"] for s in claude(home)["skills"]}
    assert notes["g"].startswith("Name only frees 1,202 characters.")
    assert notes["later"] == words.NOTE_NOT_LISTED
    overrides(home)
    notes = {s["name"]: s["note"] for s in claude(home)["skills"]}
    assert notes["g"].startswith(words.NOTE_NO_ROOM)


# By a count, when the rule does not rebuild the chat


def test_by_a_count_skills_added_after_the_chat_are_said(home):
    near_chat(home)
    skill(home / ".claude/skills", "later", "y" * 2_000)
    cc = claude(home)
    assert not cc["checked"]
    # Which skills the limit keeps is not known: no numbers, and no estimate for the picture.
    assert cc["changed"] == [CHANGED, about(5, 11)] and cc["now"] is None
    assert places(cc)[0.01] == "1% now · about 5 of 11 show only a name"


def test_by_a_count_everything_can_fit_now(home):
    counted_chat(home)
    overrides(home, a="off", b="off", c="off", d="off")
    cc = claude(home)
    assert not cc["checked"] and cc["changed"] == [CHANGED, KEEPS]
    assert set(cc["now"]["sent"]) == set("efghij")


def test_by_a_count_that_already_fits_a_chat_that_did_not_get_everything_says_it_cannot(home):
    for name in "ab":
        skill(home / ".claude/skills", name, f"Does {name}.")
    # Both fit easily, yet the log shows b as a name only: the count does not explain that chat.
    claude_chat(home, {"a": "Does a.", "b": None})
    skill(home / ".claude/skills", "later", "Does later.")
    cc = claude(home)
    assert cc["changed"] == [CHANGED, NO_RULE.format("Claude Code")] and cc["now"] is None
    assert claude(home, {"later": "off"})["after"] is None


def test_by_a_count_the_place_of_today_does_not_count_a_list_that_changed(home):
    counted_chat(home)
    assert places(claude(home))[0.01] == "1% now · 4 of 10 show only a name"
    # A skill that was not sent leaves no room of its size: the chat's number less that skill.
    overrides(home, i="off")
    assert places(claude(home))[0.01] == "1% now · 3 of 9 show only a name"
    # One that was sent leaves room for another: how many show only a name is not known.
    overrides(home, b="off")
    assert places(claude(home))[0.01] == "1% now · about 3 of 9 show only a name"


# The limit line's places, with the preview's changes


def test_the_places_count_the_skills_turned_off_in_the_preview(home):
    cut_chat(home)
    for n in "123":
        skill(home / ".claude/skills", f"later{n}", TEXT)
    today = claude(home)
    assert places(today)[0.01] == "1% now · 4 of 10 show only a name"
    assert places(today)[0.015].startswith("1.5% · 1 of 10 show only a name")
    cc = claude(home, {"a": "off"})
    # The readout, the places and the verdict count the same nine.
    assert places(cc)[0.01] == "1% now · 3 of 9 show only a name"
    assert "3 of 9 skills would show only a name" in cc["after"]["say"]
    # A skill the last list did not hold gains and loses as any other.
    assert cc["after"]["gets"] == ["g"] and cc["after"]["loses"] == []
    more = claude(home, {"a": "off", "b": "off"})["after"]
    assert more["gets"] == ["g", "later1"] and "g and later1 get descriptions." in more["say"]
    assert places(cc)[0.015].startswith("1.5% · all 9 fit")
    assert cc["limit"]["offer"]["fraction"] == 0.014  # 10,868 characters; 1.3% is 10,400
    assert cc["limit"]["offer"]["say"] == "1.4%: all 9 skills get their description"
    # Each place is what the preview says of it.
    for value, said in places(cc).items():
        if value == 0.01:
            continue
        after = claude(home, {"a": "off"}, value)["after"]
        n = after["result"]["misfit"]["n"] if after["result"]["misfit"] else 0
        assert (f"{n} of 9" in said) if n else ("all 9 fit" in said), said


def test_the_places_count_a_skill_set_to_name_only_in_the_preview(home):
    cut_chat(home)
    skill(home / ".claude/skills", "later", TEXT)
    cc = claude(home, {"a": "name-only"})
    assert places(cc)[0.01] == "1% now · 1 of 8 show only a name"
    assert places(cc)[0.011].startswith("1.1% · all 8 fit")
    assert "1 of 8 skills would show only a name" in cc["after"]["say"]
    assert cc["limit"]["note"].startswith(words.LIMIT_KEEPS_CHOSEN)


def test_the_places_count_a_skill_turned_back_on_in_the_preview(home):
    cut_chat(home)
    skill(home / ".claude/skills", "away", TEXT)
    overrides(home, away="off")
    assert places(claude(home))[0.01] == "1% now · 1 of 7 show only a name"
    cc = claude(home, {"away": "on"})
    assert places(cc)[0.01] == "1% now · 2 of 8 show only a name"
    assert "2 of 8 skills would show only a name" in cc["after"]["say"]
    assert cc["limit"]["offer"]["fraction"] == 0.013  # 9,658 characters; 1.2% is 9,600
    assert "1 skill was not in this chat's list; it is counted too." in cc["limit"]["counted"]


def test_the_line_keeps_its_places_when_the_preview_makes_everything_fit(home):
    cut_chat(home)
    cc = claude(home, {"a": "off"})
    assert cc["after"]["say"].startswith("After Apply, estimate: On a 200K window, every skill")
    # Nothing to raise any more; the line can still be moved until Apply.
    assert cc["limit"]["offer"] is None and cc["limit"]["why"] == words.LIMIT_NOT_NEEDED
    assert places(cc)[0.01] == "1% now · all 6 fit"
    assert places(cc)[0.011] == "1.1% · all 6 fit"
    assert "default" not in places(cc)
    # With a limit waiting too, its place is still there to take it back from.
    assert 0.011 in places(claude(home, {"a": "off"}, 0.011))
    # A setup that has no line gets none from a change that raises nothing.
    overrides(home, a="off")
    assert places(claude(home)) == {} and places(claude(home, {"b": "off"})) == {}


def test_a_change_in_the_preview_can_give_the_line_its_places(home):
    cut_chat(home)
    overrides(home, a="off")
    assert places(claude(home)) == {}
    cc = claude(home, {"a": "on"})
    assert cc["limit"]["offer"]["fraction"] == 0.011
    assert places(cc)[0.01] == "1% now · 1 of 7 show only a name"


def test_back_to_the_default_counts_the_preview_too(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.015})
    assert places(claude(home))["default"].startswith("1%, the default · 1 of 7 show only a name")
    cc = claude(home, {"a": "off"})
    assert places(cc)["default"] == "1%, the default · all 6 fit"
    assert places(cc)[0.015] == "1.5% now · all 6 fit"


def test_the_preview_changes_the_places_and_not_the_sentence_at_rest(home):
    cut_chat(home)
    for n in "123":
        skill(home / ".claude/skills", f"later{n}", TEXT)
    today = claude(home)
    cc = claude(home, {"a": "off"})
    assert cc["changed"] == today["changed"] and cc["now"] == today["now"]


def test_by_a_count_the_places_count_the_preview(home):
    counted_chat(home)
    cc = claude(home, {"j": "off"})
    # Nine take 9 x 1,205 + 8 = 10,853 characters: not all fit, about three do not.
    assert places(cc)[0.01] == "1% now · about 3 of 9 show only a name"
    assert places(cc)[0.013] == "1.3% · about 1 of 9 show only a name"
    assert places(cc)[0.014].startswith("1.4% · all 9 fit")
    assert cc["limit"]["offer"]["say"] == "1.4%: all 9 skills get their description"
    assert cc["after"]["say"] == about(3, 9).replace("Estimate:", "After Apply, estimate:")
    off = dict.fromkeys("abcd", "off")
    cc = claude(home, off)
    assert places(cc)[0.01] == "1% now · all 6 fit"
    assert cc["after"]["say"].startswith(
        "After Apply, estimate: On a 200K window, every skill would keep its description."
    )
    assert cc["after"]["gets"] == ["h", "i", "j"]


def test_by_a_count_a_skill_turned_back_on_counts(home):
    near_chat(home)
    skill(home / ".claude/skills", "away", "y" * 2_000)
    overrides(home, away="off")
    assert claude(home)["limit"]["offer"]["fraction"] == 0.015
    cc = claude(home, {"away": "on"})
    assert cc["limit"]["offer"]["fraction"] == 0.017
    assert cc["limit"]["offer"]["say"] == "1.7%: all 11 skills get their description"


def test_a_built_in_skill_of_unknown_size_turned_on_counts_at_the_longest(home):
    cut_chat(home)
    overrides(home, init="off")
    cc = claude(home, {"init": "on"})
    # No file and no earlier chat: 8,446 + 4 + 4 + 1,536 + 1 = 9,991 characters.
    assert cc["limit"]["offer"]["fraction"] == 0.013
    assert cc["limit"]["offer"]["say"] == "1.3%: all 8 skills get their description"
    assert cc["limit"]["counted"] == [
        "1 skill has no description Kitden can find; it is counted at the longest, 1,536 "
        "characters.",
        "1 skill was not in this chat's list; it is counted too.",
    ]
    assert cc["after"] is None  # its size is not known to the rule


# Codex


def test_codex_places_count_the_skills_turned_off_in_the_preview(home):
    budget = codex_cut_chat(home)
    today = view(home)["codex"]
    assert (
        today["limit"]["steps"][0]["say"] == f"{budget} tokens now · 2 of 3 cut short or left out"
    )
    cx = view(home, draft={"codex": {"gamma": "off"}})["codex"]
    # Without gamma the other two fit, and the line keeps its places.
    assert cx["limit"]["steps"][0]["say"] == f"{budget} tokens now · all 2 fit"
    assert "every skill would keep its full description" in cx["after"]["say"]
    assert cx["limit"]["steps"][1]["say"].startswith("500 tokens · all 2 fit")


def test_codex_keeps_its_places_when_the_preview_makes_everything_fit(home):
    codex_cut_chat(home)
    cx = view(home, draft={"codex": {"alpha": "off", "beta": "off"}})["codex"]
    assert cx["limit"]["offer"] is None and cx["limit"]["why"] == words.LIMIT_NOT_NEEDED
    assert cx["limit"]["steps"][0]["say"].endswith("tokens now · all 1 fit")
    assert [s["value"] for s in cx["limit"]["steps"]][1] == 500


def test_the_settings_file_alone_being_newer_says_nothing(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"theme": "dark"})
    os.utime(home / ".claude/settings.json")
    assert claude(home)["changed"] == []


def test_codex_gives_the_picture_its_estimate_when_the_limit_changed(home):
    codex_cut_chat(home)
    assert view(home)["codex"]["now"] is None
    (home / ".codex/config.toml").write_text("[skills]\nmax_context_tokens = 500\n")
    cx = view(home)["codex"]
    assert set(cx["now"]["sent"]) == {"alpha", "beta", "gamma"} and cx["now"]["over"] == {}
    assert cx["now"]["budget"] == 500
    assert cx["now"]["room"].startswith("Estimate: about ")
    assert cx["now"]["room"].endswith(" tokens left before the limit.")


def test_the_setup_now_is_read_from_the_folder_claude_code_uses(home, tmp_path, monkeypatch):
    cut_chat(home)
    to = tmp_path / "claude-work"
    (home / ".claude").rename(to)
    (home / ".claude.json").rename(to / ".claude.json")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(to))
    # What the old folder holds now is no skill and no setting of Claude Code's.
    skill(home / ".claude/skills", "decoy", TEXT)
    overrides(home, a="off")
    assert claude(home)["changed"] == []
    # A skill added and one turned off in the folder it uses: both count, and so does the preview.
    skill(to / "skills", "later", TEXT)
    cc = claude(home)
    assert cc["checked"] and cc["changed"][0] == CHANGED
    assert "2 of 8 skills would show only a name" in cc["changed"][1]
    cc = claude(home, {"a": "off"})
    assert places(cc)[0.01] == "1% now · 1 of 7 show only a name"
    assert "1 of 7 skills would show only a name" in cc["after"]["say"]
    write_json(to / "settings.json", {"skillOverrides": {"a": "off", "b": "off"}})
    assert claude(home)["changed"] == [CHANGED, KEEPS]


# Codex: skills turned off and added after the last chat

CODEX_LONG = "Looks through a long report, marks what matters and writes down what to do about it."


def codex(home, draft=None, limit=None):
    asked = {"codex": draft or {}}
    if limit is not None:
        asked["limits"] = {"codex": limit}
    return view(home, draft=asked)["codex"]


def codex_off(home, *paths):
    tables = [f'[[skills.config]]\npath = "{p}"\nenabled = false\n' for p in paths]
    (home / ".codex/config.toml").write_text("\n".join(tables))


def own(home, name="", folder=".agents/skills"):
    return home / folder / name / "SKILL.md" if name else home / folder


def later_skills(home):
    """Two skills to add after a chat, as the rule sees them in a list with no roots table."""
    return [
        CodexSkill(f"later{n}", CODEX_LONG, str(own(home).resolve() / f"later{n}/SKILL.md"))
        for n in "12"
    ]


def add_later(home):
    for n in "12":
        skill(own(home), f"later{n}", CODEX_LONG)


def roomy_chat(home, at="2026-10-30T12:00:00Z"):
    """The three skills of test_context_view sent whole. Returns the limit: with the two of
    `later_skills` added, 4 of the 5 descriptions would be cut."""
    paths = codex_home(home, window=1)
    five = [*rule_skills(paths), *later_skills(home)]

    def cut(fit):
        return fit.cap is not None and fit.cap >= 30

    budget = next(b for b in range(1, 3000) if cut(codex_rule(five, b)))
    assert codex_rule(rule_skills(paths), budget).sent["alpha"] == len(CODEX_A)
    codex_home(home, window=window_for(budget))
    texts = {"alpha": CODEX_A, "beta": CODEX_B, "gamma": CODEX_C}
    codex_chat(home, [f"- {n}: {t} (file: {paths[n]})" for n, t in texts.items()], at=at)
    return budget


def rooted_chat(home, window=15_000):
    """The three sent whole in a list with a roots table: r0 is ~/.agents/skills."""
    root = f"- `r0` = `{own(home).resolve()}`"
    shown = {n: f"r0/{n}/SKILL.md" for n in ("alpha", "beta", "gamma")}
    codex_home(home, window=window)
    texts = {"alpha": CODEX_A, "beta": CODEX_B, "gamma": CODEX_C}
    codex_chat(home, [root, *(f"- {n}: {t} (file: {shown[n]})" for n, t in texts.items())])
    return [CodexSkill(n, t, shown[n]) for n, t in texts.items()], (root,)


def test_a_codex_skill_turned_off_after_the_chat_is_said_and_leaves_the_estimate(home):
    budget = codex_cut_chat(home)
    before = codex(home)
    assert before["changed"] == [] and before["now"] is None
    codex_off(home, own(home, "gamma"))
    cx = codex(home)
    assert cx["checked"] is True
    size = _size(budget * 50)
    assert cx["changed"] == [
        CHANGED,
        f"Estimate: On a {size} window, every skill would keep its full description.",
    ]
    assert set(cx["now"]["sent"]) == {"alpha", "beta"} and cx["now"]["over"] == {}
    assert cx["now"]["budget"] == budget
    assert cx["now"]["room"].endswith(" tokens left before the limit.")
    # The last chat's fact stays, and the limit line counts the two.
    assert cx["windows"][0] == before["windows"][0] and cx["lamp"] == "warn"
    assert cx["limit"]["why"] == words.LIMIT_NOT_NEEDED
    rows = {s["name"]: s for s in cx["skills"]}
    assert (rows["gamma"]["state"], rows["gamma"]["side"]) == ("off", 0)
    # Off, it keeps its switch: On turns it on again.
    assert rows["gamma"]["switch"] == ["on", "off"] and rows["alpha"]["state"] == "on"
    assert rows["gamma"]["note"] == words.NOTE_OFF


def test_a_codex_skill_kitden_has_no_item_for_can_be_off_too(home):
    # Codex also lists a SKILL.md in a folder inside a skill's folder, which Kitden does not scan.
    paths = codex_home(home, window=20_000)
    deep = str(skill(own(home, "alpha").parent, "deep", "Goes deep.").resolve())
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A} (file: {paths['alpha']})",
            f"- beta: {CODEX_B} (file: {paths['beta']})",
            f"- deep: Goes deep. (file: {deep})",
            f"- gamma: {CODEX_C} (file: {paths['gamma']})",
        ],
    )
    assert codex(home)["changed"] == []
    codex_off(home, deep)
    cx = codex(home)
    assert cx["changed"][0] == CHANGED and set(cx["now"]["sent"]) == {"alpha", "beta", "gamma"}


def test_a_codex_skill_with_another_copy_on_is_not_off(home):
    # The list is read by name, so two skills of one name share a state: on while one of them is.
    paths = codex_home(home, window=20_000)
    other = str(skill(own(home, folder=".codex/skills"), "alpha", CODEX_A).resolve())
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A} (file: {paths['alpha']})",
            f"- alpha: {CODEX_A} (file: {other})",
            f"- beta: {CODEX_B} (file: {paths['beta']})",
            f"- gamma: {CODEX_C} (file: {paths['gamma']})",
        ],
    )
    codex_off(home, other)
    cx = codex(home)
    assert [s["state"] for s in cx["skills"] if s["name"] == "alpha"] == ["on", "on"]
    assert cx["changed"] == []
    assert "alpha" in codex(home, {"beta": "off"})["after"]["result"]["sent"]
    # With both off, it is off.
    codex_off(home, paths["alpha"], other)
    cx = codex(home)
    assert {s["state"] for s in cx["skills"] if s["name"] == "alpha"} == {"off"}
    assert cx["changed"][0] == CHANGED and set(cx["now"]["sent"]) == {"beta", "gamma"}


def test_the_preview_counts_without_a_codex_skill_that_is_off(home):
    codex_cut_chat(home)
    codex_off(home, own(home, "gamma"))
    cx = codex(home, {"alpha": "off"})
    assert set(cx["after"]["result"]["sent"]) == {"beta"}
    assert cx["after"]["gets"] == [] and cx["after"]["loses"] == []
    assert codex(home, limit=500)["after"]["result"]["size"] == cx["now"]["size"]


def test_codex_skills_added_after_the_chat_are_said_at_rest(home):
    budget = roomy_chat(home)
    before = codex(home)
    assert before["changed"] == [] and before["windows"][0]["result"]["room"]
    add_later(home)
    cx = codex(home)
    # What Codex's own rule gives for the five, the new ones by their files' paths.
    five = [*rule_skills(codex_home(home, window=window_for(budget))), *later_skills(home)]
    fit = codex_rule(five, budget)
    assert cx["now"]["used"] == fit.used and cx["now"]["size"] == fit.size
    assert cx["now"]["kept"] == {n: kept for n, kept in fit.sent.items() if n != "gamma"}
    assert cx["changed"][0] == CHANGED and len(cx["changed"]) == 2
    assert cx["changed"][1].startswith(f"Estimate: On a {_size(budget * 50)} window, ")
    assert "4 of 5 descriptions" in cx["changed"][1]
    assert cx["now"]["misfit"] == {"kind": "cut", "n": 4} and cx["now"]["room"] is None
    assert cx["windows"][0] == before["windows"][0] and cx["lamp"] == "ok"
    assert places(cx)[budget] == f"{budget} tokens now · 4 of 5 cut short or left out"
    # The other window's estimate holds them too.
    assert len(cx["windows"][1]["result"]["sent"]) == 5
    rows = {s["name"]: s for s in cx["skills"]}
    assert rows["later1"]["side"] is None and rows["later1"]["switch"] == ["on", "off"]


def test_the_preview_counts_codex_skills_added_after_the_chat(home):
    budget = roomy_chat(home)
    add_later(home)
    cx = codex(home, {"later1": "off", "later2": "off"})
    assert set(cx["after"]["result"]["sent"]) == {"alpha", "beta", "gamma"}
    assert cx["after"]["gets"] == ["alpha", "beta"]
    assert places(cx)[budget] == f"{budget} tokens now · all 3 fit"
    # One that stays can get its description back, and one the list held can.
    cx = codex(home, {"alpha": "off", "later2": "off"})
    assert cx["after"]["gets"] == ["beta", "later1"]


def test_an_added_codex_skill_has_the_path_its_root_gives_it(home):
    skills, roots = rooted_chat(home)
    assert codex(home)["checked"] is True
    add_later(home)
    added = [CodexSkill(f"later{n}", CODEX_LONG, f"r0/later{n}/SKILL.md") for n in "12"]
    fit = codex_rule([*skills, *added], 300, roots)
    cx = codex(home)
    assert cx["now"]["size"] == fit.size and cx["now"]["used"] == fit.used
    assert cx["changed"][0] == CHANGED and len(cx["changed"]) == 2


@pytest.mark.parametrize("folder", ["parts", "alpha/parts"])  # inside a skill's folder too
def test_an_added_codex_skill_in_a_sub_folder_counts(home, folder):
    skills, roots = rooted_chat(home)
    for n in "12":
        skill(own(home) / folder, f"later{n}", CODEX_LONG)
    added = [CodexSkill(f"later{n}", CODEX_LONG, f"r0/{folder}/later{n}/SKILL.md") for n in "12"]
    fit = codex_rule([*skills, *added], 300, roots)
    cx = codex(home)
    assert cx["now"]["size"] == fit.size and cx["now"]["used"] == fit.used
    assert cx["changed"][0] == CHANGED and len(cx["changed"]) == 2


def test_a_listed_codex_skill_in_a_sub_folder_has_a_switch(home):
    codex_home(home, window=15_000)
    inner = skill(own(home) / "alpha/parts", "inner", CODEX_LONG)
    codex_chat(home, [f"- inner: {CODEX_LONG} (file: {inner.resolve()})"])
    rows = {s["name"]: s for s in codex(home)["skills"]}
    assert rows["inner"]["switch"] == ["on", "off"]
    codex_off(home, inner)
    cx = codex(home)
    assert cx["changed"][0] == CHANGED
    assert "inner" not in cx["now"]["sent"]


@pytest.mark.parametrize("where", ["a root of its own", "a link"])
def test_an_added_codex_skill_whose_line_is_not_known_is_said_and_not_counted(home, where):
    rooted_chat(home)
    if where == "a link":
        skill(home / "shared", "later", CODEX_LONG)
        (home / ".agents/skills/later").symlink_to(home / "shared/later")
    else:
        skill(home / ".codex/skills", "later", CODEX_LONG)
    left = "Kitden cannot tell how Codex will list later, so its estimates leave this skill out."
    cx = codex(home)
    assert cx["changed"] == [CHANGED, left] and cx["now"] is None
    assert left in cx["how"]
    assert "later" not in cx["windows"][1]["result"]["sent"]
    # With a change Kitden can count, the estimate comes too.
    codex_off(home, own(home, "gamma"))
    cx = codex(home)
    assert cx["changed"][0] == CHANGED and cx["changed"][1].startswith("Estimate: ")
    assert cx["changed"][2] == left and set(cx["now"]["sent"]) == {"alpha", "beta"}
    # Two are named together.
    skill(home / ".codex/skills", "more", CODEX_LONG)
    assert codex(home)["changed"][2] == (
        "Kitden cannot tell how Codex will list later and more, so its estimates leave these "
        "skills out."
    )


def test_a_codex_skill_that_is_never_on_the_list_is_no_change(home):
    roomy_chat(home)
    skill(own(home), "asked", CODEX_LONG)
    policy = own(home, "asked").parent / "agents/openai.yaml"
    policy.parent.mkdir()
    policy.write_text(
        "interface:\n  display_name: Asked\npolicy:\n  allow_implicit_invocation: false\n"
    )
    skill(own(home), "bare", "")
    cx = codex(home)
    assert cx["changed"] == [] and cx["now"] is None
    assert not any("bare" in line or "asked" in line for line in cx["how"])
    policy.write_text("policy:\n  allow_implicit_invocation: true\n")
    assert codex(home)["changed"][0] == CHANGED


def only_asked(home, name):
    policy = own(home, name).parent / "agents/openai.yaml"
    policy.parent.mkdir(exist_ok=True)
    policy.write_text("policy:\n  allow_implicit_invocation: false\n")
    return policy


def test_a_listed_codex_skill_kept_for_when_it_is_asked_for_leaves_the_estimate(home):
    budget = codex_cut_chat(home)
    before = codex(home)
    only_asked(home, "gamma")
    cx = codex(home)
    assert cx["checked"] is True and cx["changed"][0] == CHANGED
    assert "every skill would keep its full description" in cx["changed"][1]
    assert set(cx["now"]["sent"]) == {"alpha", "beta"} and cx["now"]["budget"] == budget
    assert cx["windows"][0] == before["windows"][0]
    assert set(cx["windows"][1]["result"]["sent"]) == {"alpha", "beta"}
    assert set(codex(home, {"alpha": "off"})["after"]["result"]["sent"]) == {"beta"}
    # It is not off: its switch says On, and its note says why it is on no side.
    gamma = {s["name"]: s for s in cx["skills"]}["gamma"]
    assert (gamma["state"], gamma["switch"]) == ("on", ["on", "off"])
    assert gamma["note"] == words.NOTE_ONLY_ASKED


def names_only_chat(home, policy=None):
    """Names only, with room for two: a chat whose list holds alpha and beta. Gamma's own file, and
    its policy file when there is one, are from before the chat."""
    paths = codex_home(home, window=1)
    budget = a_budget(paths, lambda fit: fit.sent == {"alpha": 0, "beta": 0, "gamma": None})
    codex_home(home, window=window_for(budget))
    before_the_chat(Path(paths["gamma"]))
    if policy:
        before_the_chat(policy(home, "gamma"))
    codex_chat(
        home,
        [f"- alpha: (file: {paths['alpha']})", f"- beta: (file: {paths['beta']})"],
        at="2026-11-07T12:00:00Z",
    )


def test_a_skill_kept_for_when_it_is_asked_for_was_not_left_out_of_a_names_only_list(home):
    names_only_chat(home, only_asked)
    cx = codex(home)
    assert cx["changed"] == [] and "gamma" not in cx["windows"][0]["result"]["over"]


def test_a_skill_that_codex_may_pick_again_counts_as_new_after_a_names_only_list(home):
    names_only_chat(home, only_asked)
    policy = own(home, "gamma").parent / "agents/openai.yaml"
    policy.write_text("policy:\n  allow_implicit_invocation: true\n")
    cx = codex(home)
    # It was not on the list, and the next one holds it: an estimate, not a failed replay.
    assert cx["checked"] is True and cx["changed"][0] == CHANGED
    assert cx["changed"][1].startswith("Estimate: ")
    assert "gamma" not in cx["windows"][0]["result"]["over"]
    assert "gamma" in cx["now"]["over"]


def test_a_policy_set_after_a_names_only_list_says_nothing_of_that_list(home):
    # Left out, or kept off by an earlier policy: Kitden cannot tell.
    names_only_chat(home)
    assert "gamma" in codex(home)["windows"][0]["result"]["over"]
    only_asked(home, "gamma")
    cx = codex(home)
    assert cx["changed"] == [] and "gamma" not in cx["windows"][0]["result"]["over"]


@pytest.mark.parametrize("how", ["kept for when it is asked for", "off"])
def test_a_plugin_skill_is_taken_out_by_its_newer_version(home, how):
    # An update removed the version the chat used: what counts now is what its file says there.
    paths = codex_home(home, window=20_000)
    plugin = home / ".codex/plugins/cache/market/plug"
    gone = plugin.resolve() / "1.0.0/skills/tool/SKILL.md"
    newer = skill(plugin / "1.1.0/skills", "tool", "Does one thing.")
    texts = {"alpha": CODEX_A, "beta": CODEX_B, "gamma": CODEX_C}
    lines = [f"- {n}: {t} (file: {paths[n]})" for n, t in texts.items()]
    codex_chat(home, [*lines, f"- plug:tool: Does one thing. (file: {gone})"])
    cx = codex(home)
    assert cx["checked"] is True and cx["changed"] == []
    if how == "off":
        # The path of the version that is gone turns nothing off.
        codex_off(home, gone)
        assert codex(home)["changed"] == []
        codex_off(home, newer.resolve())
    else:
        policy = newer.parent / "agents/openai.yaml"
        policy.parent.mkdir()
        policy.write_text("policy:\n  allow_implicit_invocation: false\n")
    cx = codex(home)
    assert cx["changed"][0] == CHANGED
    assert set(cx["now"]["sent"]) == {"alpha", "beta", "gamma"}


def test_codex_skills_and_the_limit_changed(home):
    budget = codex_cut_chat(home)
    (home / ".codex/config.toml").write_text(
        f'[skills]\nmax_context_tokens = 500\n\n[[skills.config]]\npath = "{own(home, "gamma")}"\n'
        "enabled = false\n"
    )
    cx = codex(home)
    assert cx["changed"] == [
        "The limit and your skills changed after this list was sent: the limit is 500 tokens now. "
        "Your next chat will show the real list.",
        f"Estimate: On a {_size(budget * 50)} window, every skill would keep its full description.",
    ]
    assert set(cx["now"]["sent"]) == {"alpha", "beta"} and cx["now"]["budget"] == 500


def test_a_codex_limit_set_before_the_chat_is_said_with_its_own_words(home):
    paths = codex_home(home, limit=2_000)
    texts = {"alpha": CODEX_A, "beta": CODEX_B, "gamma": CODEX_C}
    codex_chat(home, [f"- {n}: {t} (file: {paths[n]})" for n, t in texts.items()])
    skill(own(home), "later", CODEX_LONG)
    assert codex(home)["changed"] == [
        CHANGED,
        "Estimate: With this limit, every skill would keep its full description.",
    ]


def test_a_codex_plugin_turned_off_after_the_chat_takes_its_skills_out(home):
    paths = codex_home(home, window=20_000)
    inside = home / ".codex/plugins/cache/market/plug/1.0/skills"
    tool = skill(inside, "tool", "Does one thing.").resolve()
    (home / ".codex/plugins/cache/market/plug/1.0/.codex-plugin").mkdir()
    config = home / ".codex/config.toml"
    config.write_text('[plugins."plug@market"]\nenabled = true\n')
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A} (file: {paths['alpha']})",
            f"- beta: {CODEX_B} (file: {paths['beta']})",
            f"- gamma: {CODEX_C} (file: {paths['gamma']})",
            f"- plug:tool: Does one thing. (file: {tool})",
        ],
    )
    cx = codex(home)
    assert cx["checked"] is True and cx["changed"] == []
    config.write_text('[plugins."plug@market"]\nenabled = false\n')
    cx = codex(home)
    assert cx["changed"][0] == CHANGED and "plug:tool" not in cx["now"]["sent"]
    assert {s["name"]: s["state"] for s in cx["skills"]}["plug:tool"] == "off"


def test_a_names_only_codex_chat_counts_a_skill_added_after_it(home):
    paths = codex_home(home, window=1)
    budget = a_budget(paths, lambda fit: fit.sent == {"alpha": 0, "beta": 0, "gamma": None})
    codex_home(home, window=window_for(budget))
    before_the_chat(Path(paths["gamma"]))
    codex_chat(
        home,
        [f"- alpha: (file: {paths['alpha']})", f"- beta: (file: {paths['beta']})"],
        at="2026-11-07T12:00:00Z",
    )
    assert codex(home)["changed"] == []
    skill(own(home), "later", CODEX_LONG)
    cx = codex(home)
    assert cx["changed"][0] == CHANGED
    assert "2 of 4 skills" in cx["changed"][1]
    assert set(cx["now"]["over"]) == {"alpha", "beta", "gamma", "later"}


def test_an_added_codex_skill_takes_its_place_in_the_order_of_the_list(home):
    # Names only, and room for two: Codex keeps the first two by name, so the new one comes first.
    paths = codex_home(home, window=1)
    budget = a_budget(paths, lambda fit: fit.sent == {"alpha": 0, "beta": 0, "gamma": None})
    codex_home(home, window=window_for(budget))
    before_the_chat(Path(paths["gamma"]))
    codex_chat(
        home,
        [f"- alpha: (file: {paths['alpha']})", f"- beta: (file: {paths['beta']})"],
        at="2026-11-07T12:00:00Z",
    )
    skill(own(home), "abc", CODEX_LONG)
    assert set(codex(home)["now"]["sent"]) == {"abc", "alpha"}


def test_a_codex_chat_the_rule_does_not_rebuild_gets_kitdens_count_said_as_a_count(home):
    paths = codex_home(home, window=272_000)
    codex_chat(home, [f"- alpha: {CODEX_A[:20]} (file: {paths['alpha']})"])
    cx = codex(home)
    assert cx["checked"] is False
    keeps = "Estimate: On a 272K window, every skill would keep its full description."
    assert cx["changed"] == [CHANGED, words.CODEX_COUNTED, keeps]
    assert cx["now"]["say"] == keeps
    assert cx["limit"]["counted"] == [words.CODEX_LIMIT_COUNTED]
    assert words.HOW_CODEX_COUNTED in " ".join(cx["how"])
