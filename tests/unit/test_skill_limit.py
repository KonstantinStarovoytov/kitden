"""The `skill.limit` change: Claude Code's skill list limit raised from the Context page (spec
skill-list-limit). The suggestion and its words come from the context view; the change goes
through the preview tray's endpoint, Apply and Undo, on a sandbox home, as the page does.
"""

import json
import os

import pytest

from kitden.context.rules import on_share_grid
from kitden.views import words
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
        answer = _preview(page, _limit(0.015, client="codex"))
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


def test_a_chat_no_share_rebuilds_after_a_settings_change_draws_no_limit(home):
    cut_chat(home)
    # g is the most used now: no share gives the chat's list (g only a name) any more.
    usage(home, {name: i + 1 for i, name in enumerate(NAMES)})
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
