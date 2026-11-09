"""Which skill descriptions a client sends, for a given limit (spec "Where the facts come from")."""

from dataclasses import dataclass
from math import ceil

from kitden.context.tables import (
    CLAUDE_DESCRIPTION_CAP,
    CLAUDE_SHARE,
    CODEX_DESCRIPTION_CAP,
    CODEX_FIXED_TOKENS,
    CODEX_MAX_LIMIT,
    CODEX_SHARE,
)


@dataclass(frozen=True)
class ClaudeSkill:
    name: str
    description: str | None  # None = size not known
    always_full: bool
    name_only: bool
    weight: float


@dataclass(frozen=True)
class ClaudeFit:
    full: frozenset[str]
    name_only: frozenset[str]
    used: int  # characters sent
    size: int  # characters with every description


def claude_budget(window: int, per_token: int) -> int:
    return int(window * per_token * CLAUDE_SHARE)


def claude_weight(count: int, last_used_ms: int, at_ms: int) -> float:
    days = (at_ms - last_used_ms) / 86_400_000
    return count * max(0.5 ** (days / 7), 0.1)


def _description_size(skill: ClaudeSkill) -> int:
    if skill.description is None:
        raise ValueError(f"the description of {skill.name} is not known")
    return min(len(skill.description), CLAUDE_DESCRIPTION_CAP)


def claude_rule(skills: list[ClaudeSkill], budget: int) -> ClaudeFit:
    # checked 2026-11-07 (Claude Code 2.1.311, two test chats): everything when it fits; else
    # built-ins and Name only keep their entry, every other skill shows its name, and
    # descriptions go to the most used.
    def entry(s: ClaudeSkill) -> int:
        return len(s.name) + 2 if s.name_only else len(s.name) + 4 + _description_size(s)

    separators = max(0, len(skills) - 1)
    size = sum(entry(s) for s in skills) + separators
    if size <= budget:
        full = {s.name for s in skills if not s.name_only}
        return ClaudeFit(
            frozenset(full), frozenset(s.name for s in skills if s.name_only), size, size
        )

    def fixed(s: ClaudeSkill) -> bool:
        return s.always_full or s.name_only

    used = sum(entry(s) if fixed(s) else len(s.name) + 2 for s in skills) + separators
    full = {s.name for s in skills if s.always_full and not s.name_only}
    # sorted is stable: the order of the skills breaks ties
    for s in sorted((s for s in skills if not fixed(s)), key=lambda s: -s.weight):
        extra = _description_size(s) + 2
        if used + extra <= budget:
            used += extra
            full.add(s.name)
    return ClaudeFit(frozenset(full), frozenset(s.name for s in skills) - full, used, size)


@dataclass(frozen=True)
class CodexSkill:
    name: str
    description: str
    path: str


@dataclass(frozen=True)
class CodexFit:
    sent: dict[str, int | None]  # characters of description sent; None = left out of the list
    used: int  # tokens sent
    size: int  # tokens with every description (cut at the cap)
    cap: int | None  # the one length long descriptions are cut to; None = names only


def codex_tokens(text: str) -> int:
    return ceil(len((text + "\n").encode()) / 4)


def codex_line(skill: CodexSkill, description: str) -> str:
    if description == "":
        return f"- {skill.name}: (file: {skill.path})"
    return f"- {skill.name}: {description} (file: {skill.path})"


def codex_budget(window: int, limit: int | None) -> int:
    if limit is not None:
        return min(limit, CODEX_MAX_LIMIT)
    return int(window * CODEX_SHARE)


def codex_rule(skills: list[CodexSkill], budget: int) -> CodexFit:
    # Fitted to the real list of 2026-10-30 (not read from the Codex source): when the list
    # does not fit, every long description is cut to the same length; when even the names do
    # not fit, the names that do not fit are left out.
    def total(m: int) -> int:
        return sum(codex_tokens(codex_line(s, s.description[:m])) for s in skills)

    size = CODEX_FIXED_TOKENS + total(CODEX_DESCRIPTION_CAP)
    room = budget - CODEX_FIXED_TOKENS
    if total(0) > room:
        used = CODEX_FIXED_TOKENS
        sent: dict[str, int | None] = {}
        for s in skills:
            line = codex_tokens(codex_line(s, ""))
            fits = used + line <= budget  # a later, shorter name may still fit
            if fits:
                used += line
            sent[s.name] = 0 if fits else None
        return CodexFit(sent, used, size, None)
    if total(CODEX_DESCRIPTION_CAP) <= room:
        cap = CODEX_DESCRIPTION_CAP
    else:
        low, high = 0, CODEX_DESCRIPTION_CAP  # total(low) fits, total(high) does not
        while high - low > 1:
            mid = (low + high) // 2
            low, high = (mid, high) if total(mid) <= room else (low, mid)
        cap = low
    sent = {s.name: min(len(s.description), cap) for s in skills}
    return CodexFit(sent, CODEX_FIXED_TOKENS + total(cap), size, cap)
