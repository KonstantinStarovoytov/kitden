"""The `skill.limit` change for Codex: `[skills] max_context_tokens` in config.toml, offered on
the Context page and written with preview, Apply and Undo (spec limit-line-control, stage 2).
The view tests use the Codex chats of test_context_view; the change runs through the preview
tray's endpoint on a sandbox home, as the page does."""

import json
import tomllib

import pytest

from kitden.clients.codex import RESTART
from kitden.context.rules import CodexSkill, codex_rule
from kitden.views import words
from kitden.views.context_view import _codex_limit_card
from tests.unit.test_context_view import (
    CODEX_A,
    CODEX_B,
    CODEX_C,
    a_budget,
    codex_chat,
    codex_home,
    rule_skills,
    view,
    window_for,
)
from tests.unit.test_skill_rule import _page, _preview, _round_trip

# A user's config.toml with only `[[skills.config]]` tables: no `[skills]` table yet.
CONFIG = (
    "# my Codex setup\n"
    'model = "gpt-5"\n'
    "\n"
    "[[skills.config]]\n"
    'path = "/skills/a/SKILL.md"\n'
    "enabled = false\n"
)


@pytest.fixture
def home(tmp_path):
    home = tmp_path / "home"
    for root in (".claude", ".codex", ".cursor"):
        (home / root).mkdir(parents=True)
    return home


def cut_chat(home, at="2026-10-30T12:00:00Z"):
    """test_context_view's cut-short chat: 2 of 3 descriptions cut on a tiny window. Returns the
    limit that chat had."""
    paths = codex_home(home, window=1)
    budget = a_budget(paths, lambda fit: fit.cap is not None and fit.cap >= 30)
    cap = codex_rule(rule_skills(paths), budget).cap
    assert cap is not None
    codex_home(home, window=window_for(budget))
    codex_chat(
        home,
        [
            f"- alpha: {CODEX_A[:cap]} (file: {paths['alpha']})",
            f"- beta: {CODEX_B[: cap - 1]} (file: {paths['beta']})",
            f"- gamma: {CODEX_C} (file: {paths['gamma']})",
        ],
        at=at,
    )
    return budget


def test_the_codex_card_offers_the_smallest_500_tokens_that_fit_and_every_place(home):
    budget = cut_chat(home)
    cx = view(home)["codex"]
    limit = cx["limit"]
    steps = limit.pop("steps")
    cost = limit["offer"].pop("cost")
    assert limit == {
        "now": f"2% of the context window: {budget} tokens",
        "offer": {
            "tokens": 500,
            "label": "Set to 500 tokens",
            "say": "500 tokens: no description is cut and no skill is left out",
        },
        "back": None,
        "note": (
            "Kitden writes it in your Codex settings, for all projects. Start a new chat to see "
            "the new list."
        ),
        "why": None,
        "param": "tokens",
    }
    assert cost.startswith("About ") and cost.endswith(" more tokens in every chat")
    # Today's place, then every 500 up to 10,000, in tokens, the card's unit.
    assert [s["value"] for s in steps] == [budget, *range(500, 10_001, 500)]
    assert steps[0]["now"] is True and steps[0]["short"] == 2
    assert steps[0]["say"] == f"{budget} tokens now · 2 of 3 cut short or left out"
    assert steps[1]["limit"] == 500 and steps[1]["short"] == 0
    assert steps[1]["say"].startswith("500 tokens · all 3 fit · about ")
    assert not any(line.startswith("Kitden does not offer") for line in cx["how"])


def test_the_draft_carries_the_codex_limit_and_the_estimate_uses_it(home):
    cut_chat(home)
    after = view(home, draft={"limits": {"codex": 500}})["codex"]["after"]
    assert after["budget"] == 500
    assert after["gets"] == ["alpha", "beta"]
    assert after["say"].startswith("After Apply, estimate: With this limit, every skill would")
    # With a skill switch in the tray too, both count.
    both = view(home, draft={"codex": {"gamma": "off"}, "limits": {"codex": 500}})["codex"]
    assert "gamma" not in both["after"]["result"]["sent"] and both["after"]["budget"] == 500


def test_after_a_raise_the_codex_chat_keeps_its_own_limit_and_says_it_changed(home):
    budget = cut_chat(home)
    (home / ".codex/config.toml").write_text("[skills]\nmax_context_tokens = 500\n")
    cx = view(home)["codex"]
    assert cx["checked"] is True
    assert cx["windows"][0]["budget"] == budget
    assert cx["windows"][0]["result"]["misfit"]["n"] == 2
    window = cx["windows"][0]["title"].split(" ")[0]
    assert cx["changed"] == [
        "The limit was changed after this chat: it is 500 tokens now. Start a new chat to see "
        "the new list.",
        f"Estimate: On a {window} window, every skill would keep its full description.",
    ]
    limit = cx["limit"]
    assert limit["offer"] is None and limit["why"] is None
    assert limit["back"] == {"tokens": "default", "label": "Back to the default"}
    assert limit["now"] == "Set in config.toml: 500 tokens"
    assert [s["value"] for s in limit["steps"]] == ["default", 500]
    assert limit["steps"][0]["say"].startswith(f"{budget} tokens, the default · 2 of 3 cut short")


def test_not_offered_when_everything_fits_or_there_is_no_estimate(home):
    paths = codex_home(home, window=272_000)
    codex_chat(home, [f"- alpha: {CODEX_A} (file: {paths['alpha']})"])
    cx = view(home)["codex"]
    assert cx["limit"]["why"] is None and cx["limit"]["steps"] == []
    assert not any("every description fits" in line for line in cx["how"])
    codex_home(home)  # the model cache gives no window: no estimate
    cx = view(home)["codex"]
    assert cx["limit"]["why"] == words.LIMIT_NOT_ESTIMATED


def test_not_offered_when_even_10000_tokens_do_not_fit():
    skills = [CodexSkill(f"s{i:02}", "x" * 1024, f"/s{i:02}/SKILL.md") for i in range(60)]
    base = (skills, codex_rule(skills, 5_440))
    lengths = {s.name: 1024 for s in skills}
    card = _codex_limit_card(
        272_000, None, 5_440, base, True, lengths, lambda b: codex_rule(skills, b)
    )
    assert card["offer"] is None
    assert card["why"] == (
        "Kitden does not offer a new skill list limit: even 10,000 tokens, the most Codex allows, "
        "would not fit every description. Turn some skills off."
    )


# The change itself


def _limit(tokens, client="codex"):
    return {
        "id": "r1",
        "kind": "skill.limit",
        "title": "Set the skill list limit",
        "targets": [{"client": client}],
        "params": {"tokens": tokens},
    }


def test_set_the_codex_limit_beside_skills_config_tables_and_undo(home):
    config = home / ".codex/config.toml"
    config.write_text(CONFIG)
    with _page(home) as page:
        change, _, undo = _round_trip(page, _limit(6000))
        (row,) = change["rows"]
        assert row["after"] == [{"client": "codex", "state": "on", "word": "Limit 6,000 tokens"}]
        (step,) = change["steps"]
        assert step["restart_note"] == RESTART
        written = tomllib.loads(config.read_text())
        # Codex reads it as skills.max_context_tokens, and the skill rule stays valid.
        assert written["skills"]["max_context_tokens"] == 6000
        assert written["skills"]["config"] == [{"path": "/skills/a/SKILL.md", "enabled": False}]
        assert written["model"] == "gpt-5"
        assert config.read_text().startswith("# my Codex setup\n")
        assert undo()["state"] == "undone"
    assert config.read_text() == CONFIG


def test_back_to_the_default_takes_the_codex_key_out(home):
    config = home / ".codex/config.toml"
    config.write_text(CONFIG + "\n[skills]\nmax_context_tokens = 8000\n")
    with _page(home) as page:
        change, _, _ = _round_trip(page, _limit("default"))
        word = change["rows"][0]["after"][0]["word"]
        assert word == "Limit 2% of the window, the default"
    written = tomllib.loads(config.read_text())
    assert "max_context_tokens" not in written["skills"]
    assert written["skills"]["config"] == [{"path": "/skills/a/SKILL.md", "enabled": False}]


def test_the_server_refuses_a_codex_limit_it_would_not_offer(home):
    (home / ".codex/config.toml").write_text(CONFIG)
    with _page(home) as page:
        for bad in (True, 6001, 0, -500, 10_500, "6000", 6000.0, None):
            answer = _preview(page, _limit(bad))
            assert answer.status_code == 422
            assert answer.json() == {"detail": words.CODEX_LIMIT_BAD, "row": "r1"}, bad
        # Taking out a key that is not there changes nothing.
        assert _preview(page, _limit("default")).status_code == 422


def test_a_hand_written_true_in_config_toml_is_replaced_and_undo_puts_it_back(home):
    config = home / ".codex/config.toml"
    before = "[skills]\nmax_context_tokens = true\n"
    config.write_text(before)
    with _page(home) as page:
        _, _, undo = _round_trip(page, _limit(500))
        assert tomllib.loads(config.read_text())["skills"]["max_context_tokens"] == 500
        assert undo()["state"] == "undone"
    assert config.read_text() == before


def test_a_codex_limit_in_the_draft_is_accepted(home):
    with _page(home) as page:
        ok = {"codex": {"x": "off"}, "limits": {"codex": 6000, "claude_code": 0.015}}
        assert page.get("/api/context", params={"draft": json.dumps(ok)}).status_code == 200
        bad = {"limits": {"codex": True}}
        assert page.get("/api/context", params={"draft": json.dumps(bad)}).status_code == 422


def test_a_limit_below_the_default_keeps_the_places_in_order_so_a_key_only_goes_up(home):
    budget = cut_chat(home)
    # config.toml sets less than the default (2% of the window), which is the chat's limit.
    (home / ".codex/config.toml").write_text(f"[skills]\nmax_context_tokens = {budget // 2}\n")
    steps = view(home)["codex"]["limit"]["steps"]
    values = [s["value"] for s in steps]
    assert values[:2] == [budget // 2, "default"]
    assert [s["limit"] for s in steps] == sorted(s["limit"] for s in steps)
    assert steps[0]["now"] is True and "now" not in steps[1]


def _card(limit, skills, now_fits=True):
    """The card on a 272K window (the default is 2%: 5,440 tokens), with config.toml at `limit`."""
    budget = limit if limit is not None else 5_440
    rerun = lambda b: codex_rule(skills, b)  # noqa: E731
    base = (skills, rerun(budget)) if now_fits else None
    lengths = {s.name: len(s.description) for s in skills}
    return _codex_limit_card(272_000, limit, budget, base, now_fits, lengths, rerun)


def test_a_limit_above_the_default_has_the_steps_of_500_between_them(home):
    # 60 long skills: nothing up to 10,000 fits them all, so only Back is offered.
    many = [CodexSkill(f"s{i:02}", "x" * 1024, f"/s{i:02}/SKILL.md") for i in range(60)]
    card = _card(7_000, many)
    assert card["offer"] is None and card["back"]["tokens"] == "default"
    steps = card["steps"]
    assert [s["value"] for s in steps] == ["default", 5_500, 6_000, 6_500, 7_000]
    assert steps[-1]["now"] is True
    # A lower place gives what the rule gives there, and how much less it sends.
    assert steps[1]["short"] == 60
    assert steps[1]["say"].startswith("5,500 tokens · 60 of 60 cut short or left out · about ")
    assert steps[1]["say"].endswith(" fewer tokens per chat")
    # Everything fits: the places below are there too, with Back.
    few = [CodexSkill(f"s{i}", "Does a thing.", f"/s{i}/SKILL.md") for i in range(3)]
    fits = _card(7_000, few)
    assert fits["why"] is None
    assert [s["value"] for s in fits["steps"]] == ["default", 5_500, 6_000, 6_500, 7_000]
    assert fits["steps"][1]["say"] == "5,500 tokens · all 3 fit"
    # With no estimate the places stand, and say nothing of what fits.
    unknown = _card(7_000, few, now_fits=False)
    assert unknown["why"] == words.LIMIT_NOT_ESTIMATED
    assert [s["value"] for s in unknown["steps"]] == ["default", 5_500, 6_000, 6_500, 7_000]
    lower = {"value": 5_500, "limit": 5_500, "short": None, "say": "5,500 tokens"}
    assert unknown["steps"][1] == lower


def test_a_limit_above_the_default_with_an_offer_has_the_places_below_too():
    # 30 skills of 1,024 characters need about 8,000 tokens: more than 7,000, less than 10,000.
    skills = [CodexSkill(f"s{i:02}", "x" * 1024, f"/s{i:02}/SKILL.md") for i in range(30)]
    card = _card(7_000, skills)
    assert card["offer"] is not None
    values = [s["value"] for s in card["steps"]]
    assert values[:5] == ["default", 5_500, 6_000, 6_500, 7_000]
    assert values[5:] == list(range(7_500, 10_001, 500))


def test_a_limit_below_the_default_has_no_places_between():
    few = [CodexSkill(f"s{i}", "Does a thing.", f"/s{i}/SKILL.md") for i in range(3)]
    card = _card(3_000, few)
    assert [s["value"] for s in card["steps"]] == [3_000, "default"]


def test_with_a_file_gone_the_codex_line_counts_with_todays_skills(home):
    # The chat's gamma file is gone: the rule cannot rebuild the chat, so Kitden counts, gamma as
    # the chat sent it, and the limit line gets its places all the same.
    budget = cut_chat(home)
    gone = home / ".agents/skills/gamma/SKILL.md"
    gone.unlink()
    cx = view(home)["codex"]
    assert cx["checked"] is False
    assert words.CODEX_COUNTED in cx["changed"]
    assert cx["now"]["budget"] == budget
    limit = cx["limit"]
    assert limit["now"] == f"2% of the context window: {budget} tokens"
    assert limit["counted"] == [words.CODEX_LIMIT_COUNTED]
    assert limit["steps"] and any(step.get("now") for step in limit["steps"])
    assert limit["offer"]["label"].startswith("Set to ")
    # A limit in the preview gets its estimate after Apply, from the same count.
    after = view(home, draft={"limits": {"codex": limit["offer"]["tokens"]}})["codex"]["after"]
    assert after["say"].startswith("After Apply, estimate:")


def test_with_no_window_and_no_limit_the_page_says_why_there_is_no_line(home):
    paths = codex_home(home)  # no models cache: the window is not known
    codex_chat(home, [f"- alpha: {CODEX_A[:20]} (file: {paths['alpha']})"])
    cx = view(home)["codex"]
    assert cx["message"] == words.CODEX_NO_WINDOW
    assert cx["limit"]["steps"] == []


def test_a_description_an_update_changed_counts_as_its_file_has_it_now(home):
    # The next chat sends the new text, so the count takes it; only a file that is gone counts as
    # the chat sent it.
    budget = cut_chat(home)
    beta = home / ".agents/skills/beta/SKILL.md"
    beta.write_text("---\nname: beta\ndescription: Short now.\n---\n")
    (home / ".agents/skills/gamma/SKILL.md").unlink()
    cx = view(home)["codex"]
    assert cx["checked"] is False and cx["now"]["budget"] == budget
    assert "beta" in cx["now"]["sent"]
    assert cx["limit"]["counted"] == [words.CODEX_LIMIT_COUNTED]
    assert "each description as its file has it" in words.CODEX_LIMIT_COUNTED
