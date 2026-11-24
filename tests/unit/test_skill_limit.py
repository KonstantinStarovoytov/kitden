"""The `skill.limit` change: Claude Code's skill list limit raised from the Context page (spec
skill-list-limit). The suggestion and its words come from the context view; the change goes
through the preview tray's endpoint, Apply and Undo, on a sandbox home, as the page does.
"""

import json
import os

import pytest

from kitden.context.rules import on_share_grid
from kitden.views import words
from tests.unit.test_context_claude_log import assistant, list_entry, write_chat
from tests.unit.test_context_view import LONG, claude_chat, skill, usage, view, write_json
from tests.unit.test_skill_rule import _page, _preview, _round_trip

NAMES = "abcdefg"
TEXT = LONG[:1200]


@pytest.fixture
def home(tmp_path):
    home = tmp_path / "home"
    for root in (".claude", ".codex", ".cursor"):
        (home / root).mkdir(parents=True)
    return home


def cut_chat(home, **kw):
    """Seven skills of 1,200 characters on a 200K window (8,000 characters at 1%): six get their
    description, the least used (g) shows only a name. All of them take 8,446 characters."""
    for name in NAMES:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 10 - i for i, name in enumerate(NAMES)})
    sent = dict.fromkeys(NAMES[:-1], TEXT) | {"g": None}
    claude_chat(home, sent, model="claude-sonnet-4-6", **kw)


def test_the_page_offers_the_smallest_half_percent_that_fits_every_description(home):
    cut_chat(home)
    cc = view(home)["claude_code"]
    assert cc["checked"] and cc["windows"][0]["result"]["misfit"]["n"] == 1
    steps = cc["limit"].pop("steps")
    assert cc["limit"].pop("param") == "fraction"
    assert cc["limit"] == {
        "now": "1% of the context window: 8,000 characters",
        "offer": {
            "fraction": 0.015,
            "label": "Set to 1.5%",
            "say": "1.5%: all 7 skills get their description",
            # 8,446 - 7,239 characters, at 4 characters per token
            "cost": "About 1,200 more characters in every chat (about 300 tokens)",
        },
        "back": None,
        "note": (
            "Kitden writes it in your Claude Code user settings, for all projects. Your next "
            "chat will show the real list."
        ),
        "why": None,
    }
    assert not any(line.startswith("Kitden does not offer") for line in cc["how"])
    # The limit line's places: today's, then each 0.5% up to 5%, with what each gives.
    assert [s["value"] for s in steps] == [0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05]
    assert steps[0] == {
        "value": 0.01,
        "limit": 8_000,
        "short": 1,
        "say": "1% now · 1 of 7 show only a name",
        "now": True,
    }
    assert steps[1] == {
        "value": 0.015,
        "limit": 12_000,
        "short": 0,
        "say": "1.5% · all 7 fit · about 1,200 more characters per chat",
    }
    assert steps[-1]["limit"] == 40_000 and steps[-1]["short"] == 0


def test_a_share_above_the_default_offers_the_next_step_and_back(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.0105})
    cc = view(home)["claude_code"]
    # 0.0105 of 800,000 is 8,400: the same list as the chat, so the check holds.
    assert cc["checked"]
    limit = cc["limit"]
    assert limit["now"] == "1.05% of the context window: 8,400 characters"
    assert limit["offer"]["fraction"] == 0.015
    assert limit["back"] == {"fraction": "default", "label": "Back to 1%"}


def test_name_only_skills_keep_their_state_in_the_suggestion(home):
    for name in NAMES:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 10 - i for i, name in enumerate(NAMES)})
    # h is Name only by choice; it was so at the chat, before which no settings file changed.
    skill(home / ".claude/skills", "h", TEXT)
    write_json(home / ".claude/settings.json", {"skillOverrides": {"h": "name-only"}})
    settings = home / ".claude/settings.json"
    os.utime(settings, (1_000, 1_000))
    sent = dict.fromkeys(NAMES[:-1], TEXT) | {"g": None, "h": None}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    cc = view(home)["claude_code"]
    offer = cc["limit"]["offer"]
    assert offer["say"] == "1.5%: all 7 skills get their description"
    assert cc["limit"]["note"].startswith("Skills set to Name only stay as they are. ")


def test_the_draft_carries_the_limit_and_the_estimate_uses_it(home):
    cut_chat(home)
    after = view(home, draft={"limits": {"claude_code": 0.015}})["claude_code"]["after"]
    assert after["budget"] == 12_000
    assert after["gets"] == ["g"]
    assert after["say"].startswith("After Apply, estimate: On a 200K window, every skill would")
    # With a skill switch in the tray too, both count.
    draft = {"claude_code": {"a": "off"}, "limits": {"claude_code": 0.015}}
    after = view(home, draft=draft)["claude_code"]["after"]
    assert "a" not in after["result"]["sent"] and after["budget"] == 12_000
    # An old draft (skills only) still works, and the same share as now changes nothing.
    assert view(home, draft={"claude_code": {}})["claude_code"]["after"] is None
    assert view(home, draft={"limits": {"claude_code": 0.01}})["claude_code"]["after"] is None
    assert view(home, draft={"limits": {"claude_code": "default"}})["claude_code"]["after"] is None


def test_not_offered_when_everything_fits(home):
    for name in "abc":
        skill(home / ".claude/skills", name, f"Does {name}.")
    claude_chat(home, {name: f"Does {name}." for name in "abc"})
    cc = view(home)["claude_code"]
    assert cc["limit"]["offer"] is None
    assert cc["limit"]["why"] == words.LIMIT_NOT_NEEDED
    assert cc["how"][-1] == "Kitden does not offer a new skill list limit: every description fits."


def test_not_offered_with_the_fixed_budget(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "8000"}})
    cc = view(home)["claude_code"]
    assert cc["limit"]["offer"] is None and cc["limit"]["now"] is None
    assert cc["how"][-1] == (
        "Kitden does not offer a new skill list limit: SLASH_COMMAND_TOOL_CHAR_BUDGET is set, and "
        "it wins. Kitden does not change env."
    )
    # A share in the draft is not used then.
    assert view(home, draft={"limits": {"claude_code": 0.015}})["claude_code"]["after"] is None


def test_not_offered_when_a_project_file_sets_the_share(home):
    project = home / "work/site"
    write_json(project / ".claude/settings.local.json", {"skillListingBudgetFraction": 0.01})
    cut_chat(home, folder=str(project))
    cc = view(home)["claude_code"]
    assert cc["limit"]["offer"] is None and cc["limit"]["back"] is None
    assert cc["limit"]["why"] == (
        "Kitden does not offer a new skill list limit: ~/work/site/.claude/settings.local.json "
        "sets it for this project, and that file wins."
    )


def test_not_offered_when_the_window_is_not_known(home):
    for name in NAMES:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 10 - i for i, name in enumerate(NAMES)})
    # A model Kitden has no window for, and a list no window gives: the most used show a name.
    sent = dict.fromkeys(NAMES[2:], TEXT) | {"a": None, "b": None}
    claude_chat(home, sent, model="claude-new-9")
    cc = view(home)["claude_code"]
    assert not cc["checked"]
    assert cc["limit"]["offer"] is None and cc["limit"]["now"] is None
    assert cc["how"][-1] == (
        "Kitden does not offer a new skill list limit: there is no estimate for this chat, so it "
        "cannot tell what would fit."
    )


def test_not_offered_past_five_percent(home):
    names = [f"s{i:02}" for i in range(40)]
    for name in names:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 100 - i for i, name in enumerate(names)})
    # 8,000 characters fit 6 descriptions; all 40 take about 48,000, past 5% (40,000).
    sent = {name: TEXT if i < 6 else None for i, name in enumerate(names)}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    cc = view(home)["claude_code"]
    assert cc["checked"]
    assert cc["limit"]["why"] == (
        "Kitden does not offer a new skill list limit: even 5% of the window would not fit every "
        "description. Set some skills to Name only or Off."
    )


def test_the_share_grid():
    assert on_share_grid(0.015) and on_share_grid(0.05) and on_share_grid(1)
    for bad in (True, False, 0, -0.005, 0.0123, 1.005, "0.015", None, float("nan")):
        assert not on_share_grid(bad), bad


# The change itself


def _limit(fraction, client="claude_code"):
    return {
        "id": "r1",
        "kind": "skill.limit",
        "title": "Set the skill list limit",
        "targets": [{"client": client}],
        "params": {"fraction": fraction},
    }


def test_set_the_limit_writes_the_user_file_and_undo(home):
    settings = home / ".claude/settings.json"
    before = '{\n    "theme": "dark"\n}\n'
    settings.write_text(before)
    with _page(home) as page:
        change, _, undo = _round_trip(page, _limit(0.015))
        (row,) = change["rows"]
        assert row["after"] == [{"client": "claude_code", "state": "on", "word": "Limit 1.5%"}]
        assert change["target"]["scope"] == "all"
        (step,) = change["steps"]
        assert step["restart_note"].startswith("Start a new Claude Code session")
        data = json.loads(settings.read_text())
        assert data == {"theme": "dark", "skillListingBudgetFraction": 0.015}
        assert undo()["state"] == "undone"
    assert settings.read_text() == before


def test_back_to_the_default_takes_the_key_out(home):
    settings = home / ".claude/settings.json"
    write_json(settings, {"theme": "dark", "skillListingBudgetFraction": 0.03})
    with _page(home) as page:
        change, _, undo = _round_trip(page, _limit("default"))
        word = change["rows"][0]["after"][0]["word"]
        assert word == "Limit 1%, the default"
        assert json.loads(settings.read_text()) == {"theme": "dark"}
        undo()
    assert json.loads(settings.read_text())["skillListingBudgetFraction"] == 0.03


def test_the_server_refuses_a_share_it_would_not_offer(home):
    write_json(home / ".claude/settings.json", {})
    with _page(home) as page:
        for bad in (True, 1.5, 0, 0.0123, "0.015", None):
            answer = _preview(page, _limit(bad))
            assert answer.status_code == 422
            assert answer.json() == {"detail": words.LIMIT_BAD_SHARE, "row": "r1"}, bad
        answer = _preview(page, _limit(0.015, client="cursor"))
        assert answer.json() == {"detail": words.LIMIT_CLAUDE_ONLY, "row": "r1"}
        # Taking out a key that is not there changes nothing.
        assert _preview(page, _limit("default")).status_code == 422


def test_a_bad_limit_in_the_draft_is_refused(home):
    with _page(home) as page:
        for bad in ({"claude_code": True}, {"claude_code": "1%"}, [0.015]):
            answer = page.get("/api/context", params={"draft": json.dumps({"limits": bad})})
            assert answer.status_code == 422
        ok = {"claude_code": {"x": "off"}, "limits": {"claude_code": 0.015}}
        assert page.get("/api/context", params={"draft": json.dumps(ok)}).status_code == 200


def test_the_limit_joins_a_skill_switch_in_one_change(home):
    skill(home / ".claude/skills", "deploy", "Deploys.")
    write_json(home / ".claude/settings.json", {})
    with _page(home) as page:
        found = page.get("/api/items", params={"client": "claude_code", "kind": "skill"}).json()
        item = next(i["id"] for i in found if i["name"] == "deploy")
        rule = {
            "id": "r2",
            "kind": "skill.rule",
            "title": "Turn it off",
            "targets": [{"client": "claude_code", "item": item}],
            "params": {"scope": "all", "state": "off"},
        }
        _, _, undo = _round_trip(page, _limit(0.02), rule)
        data = json.loads((home / ".claude/settings.json").read_text())
        assert data == {"skillListingBudgetFraction": 0.02, "skillOverrides": {"deploy": "off"}}
        assert undo()["state"] == "undone"


def test_after_a_raise_the_chat_keeps_its_own_limit_and_the_page_says_it_changed(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.015})
    cc = view(home)["claude_code"]
    assert cc["lede"].endswith(
        "Your Claude Code settings let this list use 1.5% of the context window."
    )
    # The chat was sent under 1%: its card keeps that limit and its own verdict.
    fact = cc["windows"][0]
    assert fact["budget"] == 8_000
    assert fact["result"]["misfit"]["n"] == 1
    assert cc["checked"] and len(cc["windows"]) == 2
    assert cc["changed"] == [
        "The limit was changed after this chat: it is 1.5% now. Your next chat will show the "
        "real list.",
        "Estimate: On a 200K window, every skill would keep its description.",
    ]
    # Nothing to raise; Back to 1% stays reachable.
    limit = cc["limit"]
    assert limit["offer"] is None and limit["why"] == words.LIMIT_NOT_NEEDED
    assert limit["now"] == "1.5% of the context window: 12,000 characters"
    assert limit["back"] == {"fraction": "default", "label": "Back to 1%"}


def test_with_the_chat_at_todays_share_nothing_is_said_to_have_changed(home):
    cut_chat(home)
    cc = view(home)["claude_code"]
    assert cc["changed"] == [] and cc["windows"][0]["budget"] == 8_000
    assert cc["lede"].endswith("Claude Code lets this list use 1% of the context window.")


def test_a_chat_that_ends_at_no_limit_kitden_knows_draws_no_limit(home):
    cut_chat(home)
    # g is the most used now: no share gives the chat's list any more. And the chat's list ends at
    # no share's limit: g would have fitted at 1% (8,000) and at 1.5% (12,000), and not at 0.5%.
    usage(home, {name: i + 1 for i, name in enumerate(NAMES)})
    sent = dict.fromkeys("abcde", TEXT) | {"f": None, "g": None}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.015})
    cc = view(home)["claude_code"]
    assert not cc["checked"] and cc["changed"] == []
    assert cc["windows"][0]["budget"] is None


def test_the_fixed_budget_lede_is_unchanged(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"env": {"SLASH_COMMAND_TOOL_CHAR_BUDGET": "8000"}})
    lede = view(home)["claude_code"]["lede"]
    assert lede.endswith("Your Claude Code settings limit this list to 8,000 characters.")


def test_a_hand_written_true_is_replaced_and_undo_puts_it_back(home):
    settings = home / ".claude/settings.json"
    before = '{\n  "skillListingBudgetFraction": true\n}\n'
    settings.write_text(before)
    with _page(home) as page:
        # In Python True == 1: the change must still write 1, not say there is nothing to change.
        _, _, undo = _round_trip(page, _limit(1))
        assert json.loads(settings.read_text()) == {"skillListingBudgetFraction": 1}
        assert undo()["state"] == "undone"
    assert settings.read_text() == before


def test_the_line_drags_back_to_the_default_when_the_user_file_has_a_higher_share(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.015})
    steps = view(home)["claude_code"]["limit"]["steps"]
    # Nothing to raise: 1%, the default, and today's 1.5%; nothing further right.
    assert steps == [
        {
            "value": "default",
            "limit": 8_000,
            "short": 1,
            "say": (
                "1%, the default · 1 of 7 show only a name · about 1,200 fewer characters per chat"
            ),
        },
        {"value": 0.015, "limit": 12_000, "short": 0, "say": "1.5% now · all 7 fit", "now": True},
    ]


def test_no_places_when_nothing_is_offered(home):
    for name in "abc":
        skill(home / ".claude/skills", name, f"Does {name}.")
    claude_chat(home, {name: f"Does {name}." for name in "abc"})
    assert view(home)["claude_code"]["limit"]["steps"] == []


# A chat the rule cannot rebuild: the limit goes by what all descriptions need

TEN = "abcdefghij"
REPLAY = (
    "Kitden could not replay this chat's list exactly, so it counts what all descriptions need."
)


def counted_chat(home, extra=None, **kw):
    """Ten skills of 1,200 characters on a 200K window (8,000 characters at 1%). The chat sent six
    descriptions, but not a's, the most used, so the rule gives another list. All ten take
    10 x (1 + 4 + 1,200) + 9 = 12,059 characters; the chat's list used 7,251."""
    for name in TEN:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 20 - i for i, name in enumerate(TEN)})
    sent = {name: TEXT if name in "bcdefg" else None for name in TEN}
    claude_chat(home, sent | (extra or {}), model="claude-sonnet-4-6", **kw)


def test_a_chat_the_rule_does_not_rebuild_gets_the_first_share_that_fits_the_count(home):
    counted_chat(home)
    cc = view(home)["claude_code"]
    assert not cc["checked"] and cc["windows"][0]["budget"] == 8_000
    limit = cc["limit"]
    assert limit["now"] == "1% of the context window: 8,000 characters"
    assert limit["why"] is None
    assert limit["offer"] == {
        "fraction": 0.02,  # 16,000; 1.5% is 12,000, under 12,059
        "label": "Set to 2%",
        "say": "2%: all 10 skills get their description",
        # 12,059 - 7,251 characters, at 4 characters per token
        "cost": "About 4,800 more characters in every chat (about 1,200 tokens)",
    }
    # A count cannot say which skills a lower limit keeps.
    assert limit["steps"][:3] == [
        {
            "value": 0.01,
            "limit": 8_000,
            "short": None,
            "say": "1% now · not all fit",
            "now": True,
        },
        {"value": 0.015, "limit": 12_000, "short": None, "say": "1.5% · not all fit"},
        {
            "value": 0.02,
            "limit": 16_000,
            "short": 0,
            "say": "2% · all 10 fit · about 4,800 more characters per chat",
        },
    ]
    assert [s["short"] for s in limit["steps"][2:]] == [0] * 7
    assert limit["counted"] == [REPLAY] and REPLAY in cc["how"]
    assert not any(line.startswith("Kitden does not offer") for line in cc["how"])


def test_a_count_that_is_exactly_the_limit_fits_and_one_character_more_does_not(home):
    counted_chat(home)
    # 59 characters less in j: 12,000 in all.
    skill(home / ".claude/skills", "j", TEXT[: 1200 - 59])
    assert view(home)["claude_code"]["limit"]["offer"]["fraction"] == 0.015
    skill(home / ".claude/skills", "j", TEXT[: 1200 - 58])
    assert view(home)["claude_code"]["limit"]["offer"]["fraction"] == 0.02


def test_a_chat_the_rule_rebuilds_says_nothing_of_a_count(home):
    cut_chat(home)
    cc = view(home)["claude_code"]
    assert "counted" not in cc["limit"] and REPLAY not in cc["how"]


def test_name_only_skills_with_no_file_are_counted_at_the_cap(home):
    # As cut_chat, which the rule rebuilds, but two listed skills have no file.
    counted_chat(home, {"ghost": None, "spook": None})
    limit = view(home)["claude_code"]["limit"]
    # 12,059 + 2 x (5 + 4 + 1,536 + 1) = 15,151 characters; the chat's list used 7,267.
    assert limit["offer"]["fraction"] == 0.02
    assert limit["offer"]["say"] == "2%: all 12 skills get their description"
    assert limit["offer"]["cost"].startswith("About 7,900 more characters in every chat")
    assert limit["counted"] == [
        REPLAY,
        "2 skills have no description Kitden can find; they are counted at the longest, 1,536 "
        "characters.",
    ]


def test_a_chat_with_one_skill_of_unknown_size_gets_an_offer(home):
    """The rule alone would do: only the missing size keeps the check from running."""
    for name in NAMES:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 10 - i for i, name in enumerate(NAMES)})
    sent = dict.fromkeys(NAMES[:-1], TEXT) | {"g": None, "ghost": None}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    limit = view(home)["claude_code"]["limit"]
    assert limit["offer"]["fraction"] == 0.015  # 8,446 + 1,546 = 9,992
    assert limit["counted"][1] == (
        "1 skill has no description Kitden can find; it is counted at the longest, 1,536 "
        "characters."
    )


def test_the_count_leaves_out_skills_set_to_name_only_or_off(home):
    counted_chat(home)
    overrides = {"skillOverrides": {"h": "name-only", "i": "off"}}
    write_json(home / ".claude/settings.json", overrides)
    limit = view(home)["claude_code"]["limit"]
    # 8 x 1,205 + 3 + 8 = 9,651 characters.
    assert limit["offer"]["fraction"] == 0.015
    assert limit["offer"]["say"] == "1.5%: all 8 skills get their description"
    assert limit["note"].startswith("Skills set to Name only stay as they are. ")


def test_the_count_never_passes_five_percent(home):
    names = [f"s{i:02}" for i in range(40)]
    for name in names:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 100 - i for i, name in enumerate(names)})
    sent = {name: TEXT if 0 < i < 7 else None for i, name in enumerate(names)}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    cc = view(home)["claude_code"]
    assert not cc["checked"] and cc["limit"]["offer"] is None and cc["limit"]["steps"] == []
    assert cc["limit"]["why"] == words.LIMIT_NOT_ENOUGH.format(share="5%")


def test_a_count_that_fits_already_does_not_promise_that_a_higher_limit_helps(home):
    for name in "ab":
        skill(home / ".claude/skills", name, f"Does {name}.")
    # Both fit easily, yet the log shows b as a name only.
    claude_chat(home, {"a": "Does a.", "b": None})
    limit = view(home)["claude_code"]["limit"]
    assert limit["offer"] is None and limit["why"] == (
        "Kitden does not offer a new skill list limit: by its count every description fits, so a "
        "higher limit may not help."
    )


def test_a_chat_that_sent_everything_needs_no_higher_limit_whatever_the_count_says(home):
    names = [f"s{i:02}" for i in range(40)]
    for name in names:
        skill(home / ".claude/skills", name, TEXT)
    # About 48,000 characters, over the limit of every window, but the chat sent them all (a
    # limit set in the shell is out of Kitden's sight).
    claude_chat(home, dict.fromkeys(names, TEXT), model="claude-sonnet-4-6")
    cc = view(home)["claude_code"]
    limit = cc["limit"]
    assert not cc["checked"] and cc["windows"][0]["result"]["misfit"] is None
    assert limit["offer"] is None and limit["why"] == words.LIMIT_NOT_NEEDED


def test_skills_added_during_the_chat_do_not_show_that_everything_fits(home):
    names = [f"s{i:02}" for i in range(40)]
    for name in [*names, "late"]:
        skill(home / ".claude/skills", name, TEXT)
    first = list_entry(names, "\n".join(f"- {n}: {TEXT}" for n in names))
    late = list_entry(["late"], f"- late: {TEXT}", isInitial=False)
    # Sent whole, outside the limit: the next chat's list has to hold it too.
    write_chat(home, "p", "chat", [first, late, assistant("claude-sonnet-4-6")], 100)
    limit = view(home)["claude_code"]["limit"]
    assert limit["why"] == words.LIMIT_NOT_ENOUGH.format(share="5%")


def test_a_dropped_skill_of_unknown_size_does_not_place_the_chats_limit(home):
    # Only ghost was dropped, and its size is not known: the list says nothing of its limit.
    sent = dict.fromkeys(NAMES, TEXT) | {"ghost": None}
    for name in NAMES:
        skill(home / ".claude/skills", name, TEXT)
    claude_chat(home, sent, model="claude-sonnet-4-6")
    # Every size up to this cap would be "no room" at any limit.
    settings = {"skillListingBudgetFraction": 0.02, "skillListingMaxDescChars": 100_000}
    write_json(home / ".claude/settings.json", settings)
    cc = view(home)["claude_code"]
    assert not cc["checked"] and cc["windows"][0]["budget"] is None and cc["changed"] == []


def test_a_dropped_description_longer_than_a_step_does_not_place_the_chats_limit(home):
    # q, dropped, is used most: the rule gives another list. Its 7,000 characters have no room at
    # 8,000 and none at today's 12,000 either, but the list of 7,000 ends at 8,000.
    for name in "pq":
        skill(home / ".claude/skills", name, "y" * 7_000)
    usage(home, {"p": 1, "q": 9})
    claude_chat(home, {"p": "y" * 7_000, "q": None}, model="claude-sonnet-4-6")
    settings = {"skillListingBudgetFraction": 0.015, "skillListingMaxDescChars": 100_000}
    write_json(home / ".claude/settings.json", settings)
    cc = view(home)["claude_code"]
    assert not cc["checked"] and cc["windows"][0]["budget"] == 8_000


def test_a_huge_cap_does_not_make_a_huge_count(home):
    counted_chat(home, {"ghost": None})
    write_json(home / ".claude/settings.json", {"skillListingMaxDescChars": 10**12})
    limit = view(home)["claude_code"]["limit"]
    assert limit["why"] == words.LIMIT_NOT_ENOUGH.format(share="5%")


def test_after_apply_of_a_share_that_fits_the_count(home):
    counted_chat(home)
    after = view(home, draft={"limits": {"claude_code": 0.02}})["claude_code"]["after"]
    assert after["budget"] == 16_000
    assert after["say"] == (
        "After Apply, estimate: On a 200K window, every skill would keep its description. 4 "
        "skills get descriptions."
    )
    assert (after["gets"], after["loses"]) == (["a", "h", "i", "j"], [])
    assert set(after["result"]["sent"]) == set(TEN) and after["result"]["over"] == {}
    assert after["result"]["used"] == 12_059


def test_after_apply_of_a_share_that_does_not_fit_names_no_skill(home):
    counted_chat(home)
    after = view(home, draft={"limits": {"claude_code": 0.015}})["claude_code"]["after"]
    assert after == {
        "say": "After Apply, estimate: On a 200K window, not all descriptions would fit.",
        "gets": [],
        "loses": [],
        "result": None,
        "budget": 12_000,
    }
    # With j set to Name only in the tray too, it does fit.
    draft = {"claude_code": {"j": "name-only"}, "limits": {"claude_code": 0.015}}
    after = view(home, draft=draft)["claude_code"]["after"]
    assert after["gets"] == ["a", "h", "i"] and "j" not in after["result"]["sent"]
    # A switch alone gets no estimate: that needs the rule.
    assert view(home, draft={"claude_code": {"j": "off"}})["claude_code"]["after"] is None
    assert view(home, draft={"limits": {"claude_code": 0.01}})["claude_code"]["after"] is None


def test_after_the_limit_was_set_the_counted_chat_keeps_its_own_limit(home):
    counted_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.02})
    cc = view(home)["claude_code"]
    # The chat's list ends at 8,000 (the next description had no room), not at 16,000.
    assert not cc["checked"] and cc["windows"][0]["budget"] == 8_000
    assert cc["changed"] == [
        "The limit was changed after this chat: it is 2% now. Your next chat will show the real "
        "list.",
        "Estimate: On a 200K window, every skill would keep its description.",
    ]
    limit = cc["limit"]
    assert limit["offer"] is None and limit["why"] == words.LIMIT_NOT_NEEDED
    assert limit["now"] == "2% of the context window: 16,000 characters"
    assert limit["back"] == {"fraction": "default", "label": "Back to 1%"}
    assert limit["steps"] == [
        {"value": "default", "limit": 8_000, "short": None, "say": "1%, the default · not all fit"},
        {"value": 0.02, "limit": 16_000, "short": 0, "say": "2% now · all 10 fit", "now": True},
    ]
    assert limit["counted"] == [REPLAY]


def test_after_a_share_that_fits_not_all_the_counted_chat_offers_the_next(home):
    counted_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.015})
    cc = view(home)["claude_code"]
    assert cc["windows"][0]["budget"] == 8_000
    assert cc["changed"][1] == "Estimate: On a 200K window, not all descriptions would fit."
    limit = cc["limit"]
    assert limit["offer"]["fraction"] == 0.02
    assert [s["say"] for s in limit["steps"][:2]] == [
        "1%, the default · not all fit",
        "1.5% now · not all fit",
    ]


def test_after_apply_a_chat_with_a_skill_of_unknown_size_keeps_its_own_limit(home):
    for name in NAMES:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 10 - i for i, name in enumerate(NAMES)})
    # 6 x 1,205 + 3 + 7 + 7 = 7,247: g's 1,202 do not fit in 8,000, and ghost is never used.
    sent = dict.fromkeys(NAMES[:-1], TEXT) | {"g": None, "ghost": None}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.015})
    cc = view(home)["claude_code"]
    assert cc["windows"][0]["budget"] == 8_000
    assert cc["changed"][1] == (
        "Estimate: On a 200K window, every skill would keep its description."
    )


def test_a_share_set_after_a_higher_one_finds_the_chats_share(home):
    counted_chat(home)
    # Sent at 1.5% (12,000): nine descriptions, but not a's, the most used.
    sent = {name: None if name == "a" else TEXT for name in TEN}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.02})
    cc = view(home)["claude_code"]
    assert cc["windows"][0]["budget"] == 12_000
    assert cc["changed"][0].startswith("The limit was changed after this chat: it is 2% now.")


def test_another_settings_change_keeps_the_counted_chats_limit(home):
    counted_chat(home)
    write_json(home / ".claude/settings.json", {"theme": "dark"})
    cc = view(home)["claude_code"]
    # The chat's list still ends at today's limit, so that is its line; nothing is said to change.
    assert cc["windows"][0]["budget"] == 8_000 and cc["changed"] == []
    assert cc["limit"]["offer"]["fraction"] == 0.02


def test_set_back_and_undo_from_a_counted_chat(home):
    counted_chat(home)
    settings = home / ".claude/settings.json"
    before = '{\n  "theme": "dark"\n}\n'
    settings.write_text(before)
    with _page(home) as page:
        offer = page.get("/api/context").json()["clients"][0]["limit"]["offer"]
        draft = json.dumps({"limits": {"claude_code": offer["fraction"]}})
        waits = page.get("/api/context", params={"draft": draft}).json()["clients"][0]
        assert waits["after"]["say"].startswith("After Apply, estimate: On a 200K window, every")
        _, _, undo = _round_trip(page, _limit(offer["fraction"]))
        assert json.loads(settings.read_text()) == {
            "theme": "dark",
            "skillListingBudgetFraction": 0.02,
        }
        cc = page.get("/api/context").json()["clients"][0]
        assert cc["changed"][0].startswith("The limit was changed after this chat: it is 2% now.")
        assert cc["windows"][0]["budget"] == 8_000
        assert undo()["state"] == "undone"
        cc = page.get("/api/context").json()["clients"][0]
        assert cc["changed"] == [] and cc["limit"]["offer"]["fraction"] == 0.02
    assert settings.read_text() == before
