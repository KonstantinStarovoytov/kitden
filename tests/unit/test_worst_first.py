"""Step 5 of the UX audit: lead to the worst problem and the simplest fix."""

import json
from datetime import datetime

from kitden.views import words
from kitden.views.context_view import _before, context_view
from kitden.views.inventory import build_inventory
from tests.unit.test_overview import _claude_chat_with_names_only, _context_home


def _claude_card(home):
    clients = context_view(build_inventory(home), home, home / ".codex", None, {})["clients"]
    return next(c for c in clients if c["client"] == "claude_code")


def test_your_skills_say_why_they_have_no_group_switch(tmp_path):
    # 05-P3, 02-N03: the group with most cut skills had no switch and no reason.
    home = _context_home(tmp_path)
    _claude_chat_with_names_only(home)
    [own] = [g for g in _claude_card(home)["groups"] if g["kind"] == "own"]
    assert own["switch"] is None
    assert own["why"] == words.GROUP_WHY_OWN


def test_a_skill_says_how_often_claude_code_used_it(tmp_path):
    # 05-P4: Kitden read the use counts and showed them nowhere.
    home = _context_home(tmp_path)
    _claude_chat_with_names_only(home)
    at = int(datetime(2026, 10, 1, 12).astimezone().timestamp() * 1000)
    state = home / ".claude.json"
    data = json.loads(state.read_text()) if state.exists() else {}
    data["skillUsage"] = {"alpha": {"usageCount": 6, "lastUsedAt": at}}
    state.write_text(json.dumps(data))
    used = {s["name"]: s["used"] for s in _claude_card(home)["skills"]}
    assert used["alpha"] == "6 times, last on Oct 1"
    assert used["beta"] == "Claude Code has no record of its use"


def test_how_this_is_counted_does_not_repeat_the_unmeasured_rest(tmp_path):
    # 05-P6: the picture's own label says what is not measured; How does not say it again.
    home = _context_home(tmp_path)
    _claude_chat_with_names_only(home)
    assert not [line for line in _claude_card(home)["how"] if "not measured" in line]


def test_the_estimate_before_apply_shows_only_when_it_differs_from_the_chat():
    # 02-N13: "57 of 72" in the chat against "about 54 of 71" after Apply read as one skill
    # freeing three. The estimate without the change is said beside it when it differs.
    chat = [{"result": {"misfit": {"n": 57}}}]
    differs = {"say": "Without the change, estimate: 55 of 72", "misfit": {"n": 55}}
    assert _before(differs, chat) == differs["say"]
    assert _before({"say": "x", "misfit": {"n": 57}}, chat) is None
    assert _before(differs, []) is None
