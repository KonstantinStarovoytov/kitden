"""The skill list for the setup as it is now, when the setup is not the one the last chat was sent
under: the sentence under the last chat's verdict, the estimate the picture follows, and the limit
line's places with the preview's changes in them. The chats are those of test_skill_limit."""

import os

import pytest

from kitden.views import words
from tests.unit.test_codex_limit import cut_chat as codex_cut_chat
from tests.unit.test_context_claude_log import assistant, list_entry, write_chat
from tests.unit.test_context_view import before_the_chat, claude_chat, skill, view, write_json
from tests.unit.test_skill_limit import NAMES, TEXT, counted_chat, cut_chat, near_chat

CHANGED = "Your skills changed after this list was sent. Your next chat will show the real list."
KEEPS = "Estimate: On a 200K window, every skill would keep its description."
NOT_ALL = "Estimate: On a 200K window, not all descriptions would fit."


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
    assert cc["changed"] == [CHANGED, NOT_ALL] and cc["now"] is None
    assert places(cc)[0.01] == "1% now · not all fit"


def test_by_a_count_everything_can_fit_now(home):
    counted_chat(home)
    overrides(home, a="off", b="off", c="off", d="off")
    cc = claude(home)
    assert not cc["checked"] and cc["changed"] == [CHANGED, KEEPS]
    assert set(cc["now"]["sent"]) == set("efghij")


def test_by_a_count_that_already_fits_a_chat_that_did_not_get_everything_nothing_is_said(home):
    for name in "ab":
        skill(home / ".claude/skills", name, f"Does {name}.")
    # Both fit easily, yet the log shows b as a name only: the count does not explain that chat.
    claude_chat(home, {"a": "Does a.", "b": None})
    skill(home / ".claude/skills", "later", "Does later.")
    cc = claude(home)
    assert cc["changed"] == [] and cc["now"] is None
    assert claude(home, {"later": "off"})["after"] is None


def test_by_a_count_the_place_of_today_does_not_count_a_list_that_changed(home):
    counted_chat(home)
    assert places(claude(home))[0.01] == "1% now · 4 of 10 show only a name"
    # A skill that was not sent leaves no room of its size: the chat's number less that skill.
    overrides(home, i="off")
    assert places(claude(home))[0.01] == "1% now · 3 of 9 show only a name"
    # One that was sent leaves room for another: how many show only a name is not known.
    overrides(home, b="off")
    assert places(claude(home))[0.01] == "1% now · not all fit"


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
    # Nine take 9 x 1,205 + 8 = 10,853 characters.
    assert places(cc)[0.01] == "1% now · not all fit"
    assert places(cc)[0.013] == "1.3% · not all fit"
    assert places(cc)[0.014].startswith("1.4% · all 9 fit")
    assert cc["limit"]["offer"]["say"] == "1.4%: all 9 skills get their description"
    assert cc["after"]["say"] == (
        "After Apply, estimate: On a 200K window, not all descriptions would fit."
    )
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
