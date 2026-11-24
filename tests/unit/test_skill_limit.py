"""The `skill.limit` change: Claude Code's skill list limit raised from the Context page (spec
skill-list-limit). The suggestion and its words come from the context view; the change goes
through the preview tray's endpoint, Apply and Undo, on a sandbox home, as the page does.
"""

import json
import os

import pytest

from kitden.context.rules import listed_share, same_share, shares_above, shares_below
from kitden.context.tables import CLAUDE_SHARE, CLAUDE_SHARES
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


def test_the_page_offers_the_first_share_on_the_list_that_fits_every_description(home):
    cut_chat(home)
    cc = view(home)["claude_code"]
    assert cc["checked"] and cc["windows"][0]["result"]["misfit"]["n"] == 1
    steps = cc["limit"].pop("steps")
    assert cc["limit"].pop("param") == "fraction"
    assert cc["limit"] == {
        "now": "1% of the context window: 8,000 characters",
        "offer": {
            "fraction": 0.011,
            "label": "Set to 1.1%",
            "say": "1.1%: all 7 skills get their description",
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
    # The limit line's places: today's, then each share on the list up to 4%, with what each gives.
    assert [s["value"] for s in steps] == list(CLAUDE_SHARES)
    assert steps[0] == {
        "value": 0.01,
        "limit": 8_000,
        "short": 1,
        "say": "1% now · 1 of 7 show only a name",
        "now": True,
    }
    assert steps[1] == {
        "value": 0.011,
        "limit": 8_800,
        "short": 0,
        "say": "1.1% · all 7 fit · about 1,200 more characters per chat",
    }
    assert steps[-1]["limit"] == 32_000 and steps[-1]["short"] == 0


def test_a_share_above_the_default_offers_the_next_step_and_back(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.0105})
    cc = view(home)["claude_code"]
    # 0.0105 of 800,000 is 8,400: the same list as the chat, so the check holds. It is off the
    # list, and 1.1% (8,800) is the first share above it.
    assert cc["checked"]
    limit = cc["limit"]
    assert limit["now"] == "1.05% of the context window: 8,400 characters"
    assert limit["offer"]["fraction"] == 0.011
    assert limit["back"] == {"fraction": "default", "label": "Back to 1%"}
    assert [s["value"] for s in limit["steps"]] == ["default", 0.0105, *CLAUDE_SHARES[1:]]


def manifold_chat(home, names):
    """`names` skills of 1,200 characters on a 200K window (8,000 characters at 1%); the six most
    used got their description. All of them take about 1,207 characters each."""
    for name in names:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 100 - i for i, name in enumerate(names)})
    sent = {name: TEXT if i < 6 else None for i, name in enumerate(names)}
    claude_chat(home, sent, model="claude-sonnet-4-6")


def test_a_share_off_the_list_still_works_and_offers_the_list_values_above_it(home):
    # 25 skills take about 30,200 characters: 3.5% (28,000) is not enough, 4% (32,000) is.
    manifold_chat(home, [f"s{i:02}" for i in range(25)])
    # 0.0375 is not on the list (an older build or a hand wrote it): it is the limit now.
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.0375})
    limit = view(home)["claude_code"]["limit"]
    assert limit["now"] == "3.75% of the context window: 30,000 characters"
    assert limit["offer"]["fraction"] == 0.04
    assert limit["back"] == {"fraction": "default", "label": "Back to 1%"}
    values = [s["value"] for s in limit["steps"]]
    # The default, every share on the list below 3.75%, today's, then 4%.
    assert values == ["default", *CLAUDE_SHARES[1:-1], 0.0375, 0.04]
    assert [s["now"] for s in limit["steps"] if s.get("now")] == [True]


def test_a_share_of_four_and_a_half_percent_is_read_and_offers_only_back(home):
    # 0.045 was a valid share before the list had a ceiling of 4%; it is read, never refused.
    manifold_chat(home, [f"s{i:02}" for i in range(40)])
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.045})
    limit = view(home)["claude_code"]["limit"]
    assert limit["now"] == "4.5% of the context window: 36,000 characters"
    assert limit["offer"] is None
    assert limit["back"] == {"fraction": "default", "label": "Back to 1%"}
    assert [s["value"] for s in limit["steps"]] == ["default", *CLAUDE_SHARES[1:], 0.045]
    assert limit["why"] == words.LIMIT_NOT_ENOUGH.format(share="4.5%")


def test_a_share_of_five_percent_is_above_the_ceiling_with_nothing_to_raise(home):
    manifold_chat(home, [f"s{i:02}" for i in range(40)])
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.05})
    limit = view(home)["claude_code"]["limit"]
    assert limit["now"] == "5% of the context window: 40,000 characters"
    assert limit["offer"] is None
    assert limit["back"] == {"fraction": "default", "label": "Back to 1%"}
    assert [s["value"] for s in limit["steps"]] == ["default", *CLAUDE_SHARES[1:], 0.05]
    assert limit["why"] == words.LIMIT_NOT_ENOUGH.format(share="5%")


def test_a_share_above_the_ceiling_that_fits_everything_offers_only_back(home):
    cut_chat(home)
    for share, now in ((0.045, "4.5%"), (0.05, "5%")):
        write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": share})
        limit = view(home)["claude_code"]["limit"]
        assert limit["now"].startswith(f"{now} of the context window")
        assert limit["offer"] is None and limit["why"] == words.LIMIT_NOT_NEEDED
        assert limit["back"] == {"fraction": "default", "label": "Back to 1%"}
        assert [s["value"] for s in limit["steps"]] == ["default", *CLAUDE_SHARES[1:], share]


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
    assert offer["say"] == "1.1%: all 7 skills get their description"
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


def test_not_offered_past_four_percent(home):
    # 8,000 characters fit 6 descriptions; all 40 take about 48,000, past 4% (32,000).
    manifold_chat(home, [f"s{i:02}" for i in range(40)])
    cc = view(home)["claude_code"]
    assert cc["checked"]
    assert cc["limit"]["why"] == (
        "Kitden does not offer a new skill list limit: even 4% of the window would not fit every "
        "description. Set some skills to Name only or Off."
    )


@pytest.mark.parametrize(
    ("length", "sent", "share"),
    [
        (1091, 27, 0.011),  # 32,969 characters: 1.1% (33,000) is enough
        (1392, 21, 0.014),  # 41,999: just under 1.4% (42,000)
        (1393, 21, 0.015),  # 42,029: just over it, so 1.5%
    ],
)
def test_the_suggestion_is_the_first_share_that_holds_the_whole_list(home, length, sent, share):
    # 30 skills of "s00" to "s29", each a 3-character name, `length` characters of description,
    # 4 characters of ": " and the dash, and 29 line breaks: 239 + 30 x length. A 1M window at
    # 3 characters per token (30,000 characters at 1%); the chat gave the first `sent` a
    # description, and the rest only a name.
    names = [f"s{i:02}" for i in range(30)]
    text = "x" * length
    for name in names:
        skill(home / ".claude/skills", name, text)
    usage(home, {name: 100 - i for i, name in enumerate(names)})
    claude_chat(home, {name: text if i < sent else None for i, name in enumerate(names)})
    limit = view(home)["claude_code"]["limit"]
    assert limit["now"] == "1% of the context window: 30,000 characters"
    assert limit["offer"]["fraction"] == share
    assert limit["offer"]["say"] == f"{words.percent(share)}: all 30 skills get their description"
    fits = {step["value"]: step["short"] for step in limit["steps"]}
    assert all(short for value, short in fits.items() if value < share)
    assert fits[share] == 0


def test_the_share_list():
    # The one list: exact values, smallest first, the default first, 4% the most.
    assert CLAUDE_SHARES == (
        0.01,
        0.011,
        0.012,
        0.013,
        0.014,
        0.015,
        0.017,
        0.02,
        0.025,
        0.03,
        0.035,
        0.04,
    )
    assert list(CLAUDE_SHARES) == sorted(set(CLAUDE_SHARES))
    assert CLAUDE_SHARES[0] == CLAUDE_SHARE
    assert [words.percent(share) for share in CLAUDE_SHARES] == [
        "1%",
        "1.1%",
        "1.2%",
        "1.3%",
        "1.4%",
        "1.5%",
        "1.7%",
        "2%",
        "2.5%",
        "3%",
        "3.5%",
        "4%",
    ]


def test_a_share_is_on_the_list_or_it_is_not():
    for share in CLAUDE_SHARES:
        assert listed_share(share) == share
    # Float noise is the same share; the list's own value comes back.
    assert listed_share(0.011 + 1e-12) == 0.011 and listed_share(0.1 * 0.17) == 0.017
    for bad in (True, False, 0, -0.01, 0.016, 0.045, 0.05, 1, 1.5, "0.015", None, float("nan")):
        assert listed_share(bad) is None, bad
    assert same_share(0.011, 0.011 + 1e-12) and not same_share(0.011, 0.012)
    assert shares_above(0.01) == list(CLAUDE_SHARES[1:])
    assert shares_above(0.0105) == list(CLAUDE_SHARES[1:])
    assert shares_above(0.0150000000001) == list(CLAUDE_SHARES[6:])
    assert shares_above(0.04) == [] and shares_above(0.05) == []
    # Between the default and a share, neither of them: the places below today's.
    assert shares_below(0.013) == [0.011, 0.012]
    assert shares_below(0.1 * 0.13) == [0.011, 0.012]
    assert shares_below(0.0125) == [0.011, 0.012]
    assert shares_below(0.01) == [] and shares_below(0.0105) == [] and shares_below(0.005) == []
    assert shares_below(0.05) == list(CLAUDE_SHARES[1:])


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
        for bad in (True, 1, 1.5, 0, 0.016, 0.045, 0.05, 0.0123, "0.015", None):
            answer = _preview(page, _limit(bad))
            assert answer.status_code == 422
            assert answer.json() == {"detail": words.LIMIT_BAD_SHARE, "row": "r1"}, bad
        answer = _preview(page, _limit(0.015, client="cursor"))
        assert answer.json() == {"detail": words.LIMIT_CLAUDE_ONLY, "row": "r1"}
        # Taking out a key that is not there changes nothing.
        assert _preview(page, _limit("default")).status_code == 422


def test_the_server_accepts_every_share_on_the_list(home):
    write_json(home / ".claude/settings.json", {})
    with _page(home) as page:
        for share in CLAUDE_SHARES:
            answer = _preview(page, _limit(share))
            assert answer.status_code == 200, (share, answer.text)


def test_a_share_a_hair_off_the_list_is_written_as_the_lists_own_value(home):
    settings = home / ".claude/settings.json"
    write_json(settings, {})
    with _page(home) as page:
        _round_trip(page, _limit(0.017 + 1e-12))
        assert json.loads(settings.read_text()) == {"skillListingBudgetFraction": 0.017}


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
        # A hand-written `true` is no share: it is replaced by one on the list. 1 (100%) is no
        # longer on the list, and in Python True == 1 must not get it through.
        assert _preview(page, _limit(1)).status_code == 422
        _, _, undo = _round_trip(page, _limit(0.011))
        assert json.loads(settings.read_text()) == {"skillListingBudgetFraction": 0.011}
        assert undo()["state"] == "undone"
    assert settings.read_text() == before


def test_the_line_drags_back_to_the_default_when_the_user_file_has_a_higher_share(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.015})
    steps = view(home)["claude_code"]["limit"]["steps"]
    # Nothing to raise: 1%, the default, the shares between it and today's 1.5%, and today's;
    # nothing further right. From 1.1% on all fit, as today: no characters fewer.
    assert steps == [
        {
            "value": "default",
            "limit": 8_000,
            "short": 1,
            "say": (
                "1%, the default · 1 of 7 show only a name · about 1,200 fewer characters per chat"
            ),
        },
        {"value": 0.011, "limit": 8_800, "short": 0, "say": "1.1% · all 7 fit"},
        {"value": 0.012, "limit": 9_600, "short": 0, "say": "1.2% · all 7 fit"},
        {"value": 0.013, "limit": 10_400, "short": 0, "say": "1.3% · all 7 fit"},
        {"value": 0.014, "limit": 11_200, "short": 0, "say": "1.4% · all 7 fit"},
        {"value": 0.015, "limit": 12_000, "short": 0, "say": "1.5% now · all 7 fit", "now": True},
    ]


def test_a_share_above_the_default_has_the_places_below_it_and_above_it(home):
    # 25 skills need 4%: at 1.3% the suggestion is 4%, and the line also goes down to 1.1%, 1.2%
    # and the default.
    manifold_chat(home, [f"s{i:02}" for i in range(25)])
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.013})
    limit = view(home)["claude_code"]["limit"]
    assert limit["offer"]["fraction"] == 0.04 and limit["back"]["fraction"] == "default"
    steps = limit["steps"]
    assert [s["value"] for s in steps] == ["default", 0.011, 0.012, 0.013, *CLAUDE_SHARES[4:]]
    assert [s["limit"] for s in steps] == sorted(s["limit"] for s in steps)
    assert [s.get("now", False) for s in steps].index(True) == 3
    # A lower place says what it gives, by the rule, and how much less it sends.
    assert steps[1] == {
        "value": 0.011,
        "limit": 8_800,
        "short": 18,
        "say": "1.1% · 18 of 25 show only a name · about 1,200 fewer characters per chat",
    }
    assert steps[3]["say"] == "1.3% now · 17 of 25 show only a name"


def test_a_share_off_the_list_has_the_list_places_below_it(home):
    manifold_chat(home, [f"s{i:02}" for i in range(25)])
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.0125})
    steps = view(home)["claude_code"]["limit"]["steps"]
    assert [s["value"] for s in steps][:4] == ["default", 0.011, 0.012, 0.0125]
    assert steps[3]["now"] is True


def test_the_default_set_by_hand_has_no_places_below_and_no_back(home):
    cut_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.01})
    limit = view(home)["claude_code"]["limit"]
    assert limit["back"] is None
    assert [s["value"] for s in limit["steps"]] == list(CLAUDE_SHARES)
    assert limit["steps"][0]["now"] is True


def test_a_lower_place_is_written_and_undo_puts_the_share_back(home):
    settings = home / ".claude/settings.json"
    write_json(settings, {"skillListingBudgetFraction": 0.015})
    with _page(home) as page:
        _, _, undo = _round_trip(page, _limit(0.012))
        assert json.loads(settings.read_text()) == {"skillListingBudgetFraction": 0.012}
        assert undo()["state"] == "undone"
    assert json.loads(settings.read_text()) == {"skillListingBudgetFraction": 0.015}


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
        "fraction": 0.017,  # 13,600; 1.5% is 12,000, under 12,059
        "label": "Set to 1.7%",
        "say": "1.7%: all 10 skills get their description",
        # 12,059 - 7,251 characters, at 4 characters per token
        "cost": "About 4,800 more characters in every chat (about 1,200 tokens)",
    }
    # A count cannot say which skills a lower limit keeps. The chat, sent under today's limit,
    # says it for today's.
    places = {step["value"]: step for step in limit["steps"]}
    assert list(places) == list(CLAUDE_SHARES)
    assert places[0.01] == {
        "value": 0.01,
        "limit": 8_000,
        "short": 4,
        "say": "1% now · 4 of 10 show only a name",
        "now": True,
    }
    assert places[0.015] == {
        "value": 0.015,
        "limit": 12_000,
        "short": None,
        "say": "1.5% · not all fit",
    }
    assert places[0.017] == {
        "value": 0.017,
        "limit": 13_600,
        "short": 0,
        "say": "1.7% · all 10 fit · about 4,800 more characters per chat",
    }
    assert [places[share]["short"] for share in CLAUDE_SHARES[1:6]] == [None] * 5
    assert [places[share]["short"] for share in CLAUDE_SHARES[6:]] == [0] * 6
    assert limit["counted"] == [REPLAY] and REPLAY in cc["how"]
    assert not any(line.startswith("Kitden does not offer") for line in cc["how"])


def test_a_count_that_is_exactly_the_limit_fits_and_one_character_more_does_not(home):
    counted_chat(home)
    # 59 characters less in j: 12,000 in all.
    skill(home / ".claude/skills", "j", TEXT[: 1200 - 59])
    assert view(home)["claude_code"]["limit"]["offer"]["fraction"] == 0.015
    skill(home / ".claude/skills", "j", TEXT[: 1200 - 58])
    assert view(home)["claude_code"]["limit"]["offer"]["fraction"] == 0.017


def command_chat(home):
    """As counted_chat, with b (sent whole) and a (name only) listed with a command in brackets:
    `b (go)` and `a (it)` are 10 characters more in all, so 12,069 and 7,261."""
    counted_chat(home)
    shown = {"a": "a (it)", "b": "b (go)"}
    lines = [f"- {shown.get(n, n)}" + (f": {TEXT}" if n in "bcdefg" else "") for n in TEN]
    entry = list_entry(list(TEN), "\n".join(lines), at="2026-11-06T12:00:00Z")
    write_chat(home, "p", "chat", [entry, assistant("claude-sonnet-4-6")], 100)


def test_the_count_holds_the_commands_the_list_shows_after_names(home):
    command_chat(home)
    cc = view(home)["claude_code"]
    assert not cc["checked"] and cc["limit"]["counted"] == [REPLAY]
    assert cc["windows"][0]["result"]["used"] == 7_261
    # 69 characters less in j: 12,000 in all, the limit at 1.5%.
    skill(home / ".claude/skills", "j", TEXT[: 1200 - 69])
    offer = view(home)["claude_code"]["limit"]["offer"]
    assert (offer["fraction"], offer["say"]) == (0.015, "1.5%: all 10 skills get their description")
    skill(home / ".claude/skills", "j", TEXT[: 1200 - 68])
    offer = view(home)["claude_code"]["limit"]["offer"]
    assert (offer["fraction"], offer["say"]) == (0.017, "1.7%: all 10 skills get their description")


def test_the_place_where_a_list_ends_counts_the_commands_after_names(home):
    command_chat(home)
    # 7,261 characters were sent: 7,256 is 5 under that (it may be 14), 7,240 is 21.
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.00907})
    assert view(home)["claude_code"]["windows"][0]["budget"] == 7_256
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.00905})
    assert view(home)["claude_code"]["windows"][0]["budget"] == 8_000


def test_a_description_written_longer_after_the_chat_counts_as_it_is_now(home):
    counted_chat(home)
    skill(home / ".claude/skills", "j", TEXT[: 1200 - 59])
    # 12,000 in all at 1.5%; b's file, sent with 1,200 characters, has 1,290 now.
    skill(home / ".claude/skills", "b", LONG)
    assert view(home)["claude_code"]["limit"]["offer"]["fraction"] == 0.017
    # A shorter file counts as what was sent: the worst case.
    skill(home / ".claude/skills", "b", TEXT[:100])
    assert view(home)["claude_code"]["limit"]["offer"]["fraction"] == 0.015


ADDED = "1 skill was not in this chat's list; it is counted too."


def near_chat(home):
    """As counted_chat, with all ten at exactly 12,000 characters: 1.5% fits them."""
    counted_chat(home)
    skill(home / ".claude/skills", "j", TEXT[: 1200 - 59])


def test_a_skill_added_after_the_chat_moves_the_counted_offer_up(home):
    near_chat(home)
    assert view(home)["claude_code"]["limit"]["offer"]["fraction"] == 0.015
    # 5 + 4 + 1,536 + 1 characters more: 13,546.
    skill(home / ".claude/skills", "later", "y" * 2_000)
    cc = view(home)["claude_code"]
    limit = cc["limit"]
    assert limit["offer"]["fraction"] == 0.017
    assert limit["offer"]["say"] == "1.7%: all 11 skills get their description"
    assert next(s for s in limit["steps"] if s["value"] == 0.017)["say"].startswith(
        "1.7% · all 11 fit · "
    )
    assert limit["counted"] == [REPLAY, ADDED] and ADDED in cc["how"]
    # The chat's list does not hold the new skill, so it does not say what today's limit gives.
    assert limit["steps"][0]["say"] == "1% now · not all fit"
    # It is still no skill of the chat.
    assert cc["windows"][0]["result"]["say"].startswith("In your last chat on Nov 6, 4 of 10 ")
    # Turned off in the tray, it is not in the next list.
    draft = {"claude_code": {"later": "off"}, "limits": {"claude_code": 0.015}}
    after = view(home, draft=draft)["claude_code"]["after"]
    assert "every skill would keep its description" in after["say"]
    assert "later" not in after["result"]["sent"]


@pytest.mark.parametrize("state", ["off", "user-invocable-only"])
def test_a_skill_added_after_the_chat_that_is_not_listed_changes_nothing(home, state):
    near_chat(home)
    skill(home / ".claude/skills", "later", "y" * 2_000)
    write_json(home / ".claude/settings.json", {"skillOverrides": {"later": state}})
    limit = view(home)["claude_code"]["limit"]
    assert limit["offer"]["fraction"] == 0.015
    assert limit["offer"]["say"] == "1.5%: all 10 skills get their description"
    assert limit["counted"] == [REPLAY]


def test_an_added_skill_that_asks_to_be_named_by_the_person_changes_nothing(home):
    near_chat(home)
    asked = "disable-model-invocation: true\n"
    skill(home / ".claude/skills", "later", "y" * 2_000, extra=asked)
    limit = view(home)["claude_code"]["limit"]
    assert limit["offer"]["fraction"] == 0.015 and limit["counted"] == [REPLAY]


def test_an_added_skill_set_to_name_only_counts_as_a_name(home):
    counted_chat(home)
    # 12,059 - 67 = 11,992 characters, and 5 + 2 + 1 for the name: 12,000.
    skill(home / ".claude/skills", "j", TEXT[: 1200 - 67])
    skill(home / ".claude/skills", "later", "y" * 2_000)
    write_json(home / ".claude/settings.json", {"skillOverrides": {"later": "name-only"}})
    limit = view(home)["claude_code"]["limit"]
    assert limit["offer"]["fraction"] == 0.015
    assert limit["offer"]["say"] == "1.5%: all 10 skills get their description"
    assert limit["counted"] == [REPLAY, ADDED]


def test_skills_added_after_a_chat_the_rule_rebuilds_move_its_offer_too(home):
    cut_chat(home)
    for n in "123":
        skill(home / ".claude/skills", f"later{n}", TEXT)
    cc = view(home, draft={"limits": {"claude_code": 0.015}})["claude_code"]
    # 8,446 + 3 x (6 + 4 + 1,200 + 1) = 12,079 characters, over 12,000.
    assert cc["checked"] and cc["windows"][0]["result"]["misfit"]["n"] == 1
    limit = cc["limit"]
    assert limit["offer"]["fraction"] == 0.017
    assert limit["offer"]["say"] == "1.7%: all 10 skills get their description"
    assert limit["steps"][0]["say"] == "1% now · 4 of 10 show only a name"
    assert limit["counted"] == ["3 skills were not in this chat's list; they are counted too."]
    # The estimate after Apply agrees with the place on the line.
    step = next(s for s in limit["steps"] if s["value"] == 0.015)
    assert step["say"].startswith("1.5% · 1 of 10 show only a name")
    assert "1 of 10 skills would show only a name" in cc["after"]["say"]


def test_skills_added_after_a_chat_that_fitted_can_call_for_a_higher_limit(home):
    for name in NAMES[:-1]:
        skill(home / ".claude/skills", name, TEXT)
    claude_chat(home, dict.fromkeys(NAMES[:-1], TEXT), model="claude-sonnet-4-6")
    cc = view(home)["claude_code"]
    assert cc["checked"] and cc["limit"]["why"] == words.LIMIT_NOT_NEEDED
    skill(home / ".claude/skills", "later", TEXT)
    cc = view(home)["claude_code"]
    assert cc["checked"] and cc["limit"]["offer"]["fraction"] == 0.011


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
    assert limit["offer"]["fraction"] == 0.013  # 8,446 + 1,546 = 9,992; 1.2% is 9,600
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
    assert limit["offer"]["fraction"] == 0.013  # 1.2% is 9,600
    assert limit["offer"]["say"] == "1.3%: all 8 skills get their description"
    assert limit["note"].startswith("Skills set to Name only stay as they are. ")


def test_the_count_never_passes_four_percent(home):
    names = [f"s{i:02}" for i in range(40)]
    for name in names:
        skill(home / ".claude/skills", name, TEXT)
    usage(home, {name: 100 - i for i, name in enumerate(names)})
    sent = {name: TEXT if 0 < i < 7 else None for i, name in enumerate(names)}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    cc = view(home)["claude_code"]
    assert not cc["checked"] and cc["limit"]["offer"] is None and cc["limit"]["steps"] == []
    assert cc["limit"]["why"] == words.LIMIT_NOT_ENOUGH.format(share="4%")


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


def test_a_chat_that_sent_everything_does_not_show_that_a_longer_file_fits(home):
    names = [f"s{i:02}" for i in range(40)]
    for name in names:
        skill(home / ".claude/skills", name, TEXT)
    claude_chat(home, dict.fromkeys(names, TEXT), model="claude-sonnet-4-6")
    skill(home / ".claude/skills", "s00", LONG)
    limit = view(home)["claude_code"]["limit"]
    assert limit["why"] == words.LIMIT_NOT_ENOUGH.format(share="4%")


def test_skills_added_during_the_chat_do_not_show_that_everything_fits(home):
    names = [f"s{i:02}" for i in range(40)]
    for name in [*names, "late"]:
        skill(home / ".claude/skills", name, TEXT)
    first = list_entry(names, "\n".join(f"- {n}: {TEXT}" for n in names))
    late = list_entry(["late"], f"- late: {TEXT}", isInitial=False)
    # Sent whole, outside the limit: the next chat's list has to hold it too.
    write_chat(home, "p", "chat", [first, late, assistant("claude-sonnet-4-6")], 100)
    limit = view(home)["claude_code"]["limit"]
    assert limit["why"] == words.LIMIT_NOT_ENOUGH.format(share="4%")


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
    assert limit["why"] == words.LIMIT_NOT_ENOUGH.format(share="4%")


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
    # A count says only where everything fits: from 1.7% (13,600 of the 12,059 needed).
    unknown = [
        {"value": at, "limit": round(at * 800_000), "short": None, "say": f"{p} · not all fit"}
        for at, p in ((0.011, "1.1%"), (0.012, "1.2%"), (0.013, "1.3%"), (0.014, "1.4%"))
    ]
    assert limit["steps"] == [
        {"value": "default", "limit": 8_000, "short": None, "say": "1%, the default · not all fit"},
        *unknown,
        {"value": 0.015, "limit": 12_000, "short": None, "say": "1.5% · not all fit"},
        {"value": 0.017, "limit": 13_600, "short": 0, "say": "1.7% · all 10 fit"},
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
    assert limit["offer"]["fraction"] == 0.017
    # The chat was sent under 1%: its 7,251 characters are not what the list uses at 12,000. The
    # count's run at 12,000 keeps nine descriptions, 10,857 characters: 12,059 is 1,202 more.
    assert limit["offer"]["cost"] == "About 1,200 more characters in every chat (about 300 tokens)"
    # The chat's list was sent under another limit: the place of today cannot say more.
    assert [s["say"] for s in limit["steps"][:6]] == [
        "1%, the default · not all fit",
        "1.1% · not all fit",
        "1.2% · not all fit",
        "1.3% · not all fit",
        "1.4% · not all fit",
        "1.5% now · not all fit",
    ]
    step = next(s for s in limit["steps"] if s["value"] == 0.017)
    assert step["say"] == "1.7% · all 10 fit · about 1,200 more characters per chat"


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
    # Sent at 1.5% (12,000): nine descriptions, but not a's, the most used. They take 10,857, so
    # 1.4% (11,200) gives the same list: the first share on the list that does is the chat's.
    sent = {name: None if name == "a" else TEXT for name in TEN}
    claude_chat(home, sent, model="claude-sonnet-4-6")
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.02})
    cc = view(home)["claude_code"]
    assert cc["windows"][0]["budget"] == 11_200
    assert cc["changed"][0].startswith("The limit was changed after this chat: it is 2% now.")


def test_a_limit_lowered_under_what_the_chat_sent_is_not_its_limit(home):
    counted_chat(home)
    # 6,800 characters: 451 under the chat's list, less than any description it dropped.
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.0085})
    cc = view(home)["claude_code"]
    assert cc["windows"][0]["budget"] == 8_000
    assert cc["changed"][0].startswith("The limit was changed after this chat: it is 0.85% now.")


def test_a_list_a_few_characters_over_the_limit_by_kitdens_count_still_ends_there(home):
    counted_chat(home)
    # 7,251 characters were sent: 7,240 (0.905%) and 7,200 (0.9%) are 11 and 51 under that.
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.00905})
    cc = view(home)["claude_code"]
    assert cc["windows"][0]["budget"] == 7_240 and cc["changed"] == []
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.009})
    assert view(home)["claude_code"]["windows"][0]["budget"] == 8_000


def test_another_settings_change_keeps_the_counted_chats_limit(home):
    counted_chat(home)
    write_json(home / ".claude/settings.json", {"theme": "dark"})
    cc = view(home)["claude_code"]
    # The chat's list still ends at today's limit, so that is its line; nothing is said to change.
    assert cc["windows"][0]["budget"] == 8_000 and cc["changed"] == []
    assert cc["limit"]["offer"]["fraction"] == 0.017


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
            "skillListingBudgetFraction": 0.017,
        }
        cc = page.get("/api/context").json()["clients"][0]
        assert cc["changed"][0].startswith("The limit was changed after this chat: it is 1.7% now.")
        assert cc["windows"][0]["budget"] == 8_000
        assert undo()["state"] == "undone"
        cc = page.get("/api/context").json()["clients"][0]
        assert cc["changed"] == [] and cc["limit"]["offer"]["fraction"] == 0.017
    assert settings.read_text() == before


# A built-in skill has no file: the count takes its description from an earlier chat's list

EARLIER_TWO = (
    "2 built-in skills have no file; their descriptions are counted as an earlier chat sent them."
)
EARLIER_ONE = "1 built-in skill has no file; its description is counted as an earlier chat sent it."
INIT, REVIEW = "i" * 59, "r" * 71


def built_in_chat(home):
    """As a real chat of 2026-11-24, on a 200K window (8,000 characters at 1%): six skills of
    1,200 characters and h of 700 get their description; init and security-review, built in,
    show only a name. The list takes 7,966 characters: at its limit, as no other description
    fits. With init's real 59 characters and security-review's 71 it takes 8,100; at the cap,
    1,536 each, 11,042."""
    for name in "abcdef":
        skill(home / ".claude/skills", name, TEXT)
    skill(home / ".claude/skills", "h", "h" * 700)
    sent = dict.fromkeys("abcdef", TEXT) | {"h": "h" * 700, "init": None, "security-review": None}
    claude_chat(home, sent, model="claude-sonnet-4-6")


def earlier_chat(home, sent: dict[str, str]):
    """An older chat, in another folder, whose list sent these built-in skills with their text."""
    content = "\n".join(f"- {name}: {text}" for name, text in sent.items())
    entry = list_entry(list(sent), content, folder="/work/b", at="2026-11-01T10:00:00Z")
    write_chat(home, "b", "older", [entry, assistant("claude-sonnet-4-6")], 50)


def test_built_in_skills_count_as_an_earlier_chat_sent_them(home):
    built_in_chat(home)
    earlier_chat(home, {"init": INIT, "security-review": REVIEW})
    cc = view(home)["claude_code"]
    assert not cc["checked"] and cc["windows"][0]["budget"] == 8_000
    limit = cc["limit"]
    # 8,100 characters: 1.1% (8,800) holds them, not 1.4% as at the cap.
    assert limit["offer"]["fraction"] == 0.011
    assert limit["offer"]["say"] == "1.1%: all 9 skills get their description"
    # 8,100 - 7,966 characters, at 4 characters per token
    assert limit["offer"]["cost"] == "About 130 more characters in every chat (about 34 tokens)"
    assert limit["counted"] == [REPLAY, EARLIER_TWO] and EARLIER_TWO in cc["how"]
    assert limit["steps"][0]["say"] == "1% now · 2 of 9 show only a name"
    assert limit["steps"][1]["say"] == "1.1% · all 9 fit · about 130 more characters per chat"
    # Only the count uses them: the page shows no description for either skill.
    rows = {s["name"]: s for s in cc["skills"]}
    assert not rows["init"]["description"] and not rows["security-review"]["description"]


def test_built_in_skills_no_earlier_chat_sent_count_at_the_cap(home):
    built_in_chat(home)
    limit = view(home)["claude_code"]["limit"]
    assert limit["offer"]["fraction"] == 0.014  # 11,042; 1.3% is 10,400
    assert limit["offer"]["cost"].startswith("About 3,100 more characters in every chat")
    assert limit["counted"] == [
        REPLAY,
        "2 skills have no description Kitden can find; they are counted at the longest, 1,536 "
        "characters.",
    ]


def test_one_built_in_skill_from_an_earlier_chat_and_one_at_the_cap(home):
    built_in_chat(home)
    # An earlier chat sent init with its text, and security-review by name only.
    content = f"- init: {INIT}\n- security-review"
    entry = list_entry(["init", "security-review"], content, at="2026-11-01T10:00:00Z")
    write_chat(home, "b", "older", [entry], 50)
    limit = view(home)["claude_code"]["limit"]
    assert limit["offer"]["fraction"] == 0.012  # 7,966 + 61 + 1,538 = 9,565; 1.2% is 9,600
    assert limit["counted"] == [
        REPLAY,
        "1 skill has no description Kitden can find; it is counted at the longest, 1,536 "
        "characters.",
        EARLIER_ONE,
    ]


def test_a_built_in_skill_set_to_name_only_or_off_is_in_no_line(home):
    built_in_chat(home)
    earlier_chat(home, {"init": INIT, "security-review": REVIEW})
    overrides = {"init": "name-only", "security-review": "off"}
    write_json(home / ".claude/settings.json", {"skillOverrides": overrides})
    assert view(home)["claude_code"]["limit"]["counted"] == [REPLAY]


def test_an_earlier_chat_does_not_change_a_chat_the_rule_rebuilds(home):
    cut_chat(home)
    # init is off, so in no list: it waits on the page, and its size is not known.
    write_json(home / ".claude/settings.json", {"skillOverrides": {"init": "off"}})
    draft = {"claude_code": {"init": "on"}}
    before = view(home)["claude_code"], view(home, draft=draft)["claude_code"]
    earlier_chat(home, {"init": INIT})
    after = view(home)["claude_code"], view(home, draft=draft)["claude_code"]
    assert before[0]["checked"] and after[0]["checked"]
    assert after[0]["limit"] == before[0]["limit"] and "counted" not in after[0]["limit"]
    # Turned on in the tray, its size is still not known to the rule: no estimate.
    assert before[1]["after"] is None and after[1]["after"] is None


def test_a_chat_at_its_limit_by_built_in_skills_keeps_it_after_a_settings_write(home):
    built_in_chat(home)
    earlier_chat(home, {"init": INIT, "security-review": REVIEW})
    # The settings file is written after the chat, with the same share: the rule cannot say the
    # chat's limit, the place its list stops at can. 34 characters were left, under init's 61.
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.01})
    cc = view(home)["claude_code"]
    assert not cc["checked"] and cc["windows"][0]["budget"] == 8_000 and cc["changed"] == []
    limit = cc["limit"]
    assert limit["steps"][0]["say"] == "1% now · 2 of 9 show only a name"
    # 8,100 - 7,966 characters: from the chat's own number.
    assert limit["offer"]["cost"] == "About 130 more characters in every chat (about 34 tokens)"


def test_with_no_earlier_chat_a_settings_write_leaves_the_chats_limit_unknown(home):
    built_in_chat(home)
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.01})
    cc = view(home)["claude_code"]
    assert cc["windows"][0]["budget"] is None
    assert cc["limit"]["steps"][0]["say"] == "1% now · not all fit"


def test_a_chat_at_its_limit_by_built_in_skills_finds_its_share_after_a_change(home):
    built_in_chat(home)
    earlier_chat(home, {"init": INIT, "security-review": REVIEW})
    write_json(home / ".claude/settings.json", {"skillListingBudgetFraction": 0.015})
    cc = view(home)["claude_code"]
    # The list stops at 8,000 (1%), not at today's 12,000.
    assert cc["windows"][0]["budget"] == 8_000
    assert cc["changed"][0].startswith("The limit was changed after this chat: it is 1.5% now.")
    # 8,100 characters fit in 12,000: nothing to raise; the steps are measured from today's.
    limit = cc["limit"]
    assert limit["offer"] is None and limit["why"] == words.LIMIT_NOT_NEEDED
    # The 8,100 characters fit from 1.1% (8,800) on.
    assert [s["say"] for s in limit["steps"]] == [
        "1%, the default · not all fit",
        "1.1% · all 9 fit",
        "1.2% · all 9 fit",
        "1.3% · all 9 fit",
        "1.4% · all 9 fit",
        "1.5% now · all 9 fit",
    ]
