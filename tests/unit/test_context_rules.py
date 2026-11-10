"""The skill list rules of Claude Code and Codex: which descriptions fit the context limit."""

import pytest

from kitden.context.rules import (
    ClaudeSkill,
    CodexSkill,
    claude_rule,
    claude_weight,
    codex_budget,
    codex_line,
    codex_rule,
    codex_tokens,
)
from kitden.context.tables import CODEX_FIXED_TOKENS, CODEX_MAX_LIMIT

DAY_MS = 86_400_000


def skill(name, description="d" * 20, *, full=False, only=False, weight=0.0):
    return ClaudeSkill(name, description, full, only, weight)


def test_claude_all_fit_sends_every_description():
    skills = [skill("a"), skill("b"), skill("c")]
    fit = claude_rule(skills, 10_000)
    assert fit.full == {"a", "b", "c"}
    assert fit.name_only == set()


def test_claude_built_ins_and_name_only_keep_their_place_then_the_most_used():
    # A full entry is 1 + 4 + 20 = 25, a name is 3, there are 4 separators.
    skills = [
        skill("a", full=True),
        skill("b", full=True),
        skill("n", only=True),
        skill("x", weight=5.0),
        skill("y", weight=1.0),
    ]
    # Fixed part: 25 + 25 + 3 + 3 + 3 + 4 = 63; one more description costs 22.
    fit = claude_rule(skills, 85)
    assert fit.full == {"a", "b", "x"}
    assert fit.name_only == {"n", "y"}
    assert fit.used == 85
    assert fit.size == 25 * 4 + 3 + 4


def test_claude_built_ins_alone_can_pass_the_limit():
    skills = [skill("a", full=True), skill("b", full=True), skill("c")]
    fit = claude_rule(skills, 20)
    assert fit.full == {"a", "b"}
    assert fit.name_only == {"c"}
    assert fit.used > 20


def test_claude_caps_a_description_at_1536():
    fit = claude_rule([skill("abc", "x" * 3000)], 100_000)
    assert fit.size == len("abc") + 4 + 1536


def test_claude_entry_sizes():
    skills = [skill("ab", "x" * 10), skill("cde", only=True)]
    # (2 + 4 + 10) + (3 + 2) + 1 separator
    assert claude_rule(skills, 1000).size == 22


def test_claude_weight_halves_every_week_and_stops_at_a_tenth():
    t = 1_700_000_000_000
    assert claude_weight(8, t, t + 7 * DAY_MS) == 4.0
    assert claude_weight(8, t, t + 70 * DAY_MS) == 0.8


def test_claude_weight_of_a_use_after_the_chat_is_the_full_count():
    # A lastUsedAt in microseconds, not ms, lies far in the future: no overflow.
    t = 1_700_000_000_000
    assert claude_weight(8, t * 1000, t) == 8.0


def test_claude_needs_a_description_unless_name_only():
    assert claude_rule([skill("a", None, only=True)], 100).name_only == {"a"}
    with pytest.raises(ValueError):
        claude_rule([skill("a", None)], 100)


def codex(name, description):
    return CodexSkill(name, description, f"/s/{name}/SKILL.md")


def total(skills, m):
    return sum(codex_tokens(codex_line(s, s.description[:m])) for s in skills)


def test_codex_cuts_every_long_description_to_one_length():
    skills = [codex("a", "x" * 500), codex("b", "short one"), codex("c", "y" * 600)]
    budget = CODEX_FIXED_TOKENS + 150
    fit = codex_rule(skills, budget)
    cap = fit.sent["a"]
    assert fit.sent["c"] == cap
    assert 0 < cap < 500
    assert fit.sent["b"] == len("short one")
    assert fit.cap == cap
    assert fit.used <= budget
    assert CODEX_FIXED_TOKENS + total(skills, cap + 1) > budget  # the largest cap that fits


def test_codex_leaves_skills_out_when_names_do_not_fit():
    skills = [codex(n, "x" * 100) for n in "abcdef"]
    names_only = [codex_tokens(codex_line(s, "")) for s in skills]
    budget = CODEX_FIXED_TOKENS + names_only[0] + names_only[1]
    fit = codex_rule(skills, budget)
    assert fit.sent == {"a": 0, "b": 0, "c": None, "d": None, "e": None, "f": None}
    assert fit.used == budget
    assert fit.cap is None


def test_codex_keeps_a_short_name_after_a_long_one_that_does_not_fit():
    skills = [codex("a", "x"), codex("b" * 200, "x"), codex("c", "x")]
    line = codex_tokens(codex_line(skills[0], ""))
    fit = codex_rule(skills, CODEX_FIXED_TOKENS + 2 * line)
    assert fit.sent == {"a": 0, "b" * 200: None, "c": 0}


def test_codex_counts_bytes_so_russian_costs_more():
    assert codex_tokens("я" * 8) > codex_tokens("a" * 8)


def test_codex_never_sends_more_than_1024():
    fit = codex_rule([codex("a", "x" * 2000)], 100_000)
    assert fit.sent == {"a": 1024}
    assert fit.cap == 1024


def test_codex_budget_uses_the_limit_or_two_percent_of_the_window():
    assert codex_budget(258_000, None) == 5160
    assert codex_budget(258_000, 3000) == 3000
    assert codex_budget(258_000, 50_000) == CODEX_MAX_LIMIT
