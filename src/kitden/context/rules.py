"""Which skill descriptions a client sends, for a given limit (spec "Where the facts come from")."""

from dataclasses import dataclass
from math import ceil

from kitden.context.tables import (
    CLAUDE_DESCRIPTION_CAP,
    CLAUDE_SHARE,
    CODEX_DESCRIPTION_CAP,
    CODEX_INTRO,
    CODEX_INTRO_ROOTS,
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


def claude_weight(count: float, last_used_ms: float, at_ms: int) -> float:
    # A use after the chat (or a time in other units) counts as fresh: no huge power.
    days = max(0.0, (at_ms - last_used_ms) / 86_400_000)
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


def codex_catalog(description: str) -> str:
    """The description as Codex lists it: at most 1,024 characters, ending in `...` if cut."""
    if len(description) <= CODEX_DESCRIPTION_CAP:
        return description
    return description[: CODEX_DESCRIPTION_CAP - 3] + "..."


def codex_table(roots: tuple[str, ...]) -> int:
    """Tokens a roots table costs: the list's text with it, less the plain list's; never below 0.

    # checked 2026-11-12 (codex-rs/ext/skills/src/render.rs aliased_metadata_overhead_cost,
    # catalog_prompt.rs render_available_skills_body)
    """
    if not roots:
        return 0

    def body(intro: str, rows: tuple[str, ...]) -> str:
        table = ("### Skill roots", *rows) if rows else ()
        return "\n" + "\n".join(("## Skills", intro, *table, "### Available skills")) + "\n"

    plain = ceil(len(body(CODEX_INTRO, ()).encode()) / 4)
    return max(0, ceil(len(body(CODEX_INTRO_ROOTS, roots).encode()) / 4) - plain)


def codex_rule(skills: list[CodexSkill], budget: int, roots: tuple[str, ...] = ()) -> CodexFit:
    """Codex's own rule, read from codex-rs/ext/skills/src/render.rs (checked 2026-11-12, and
    against a real list of Codex 0.167.0: all 60 lengths the same). A roots table, when the list
    has one, is paid first. If every line fits whole, all are sent whole. If the names fit, the
    room left is shared one character at a time, skill by skill in list order, while the tokens
    a character adds still fit. If even the names do not fit, names are kept in order while they
    fit and the rest are left out. A skill's `path` is the path as the list shows it."""
    table = codex_table(roots)
    limit = budget - table
    texts = {s.name: codex_catalog(s.description) for s in skills}

    def cost(s: CodexSkill, chars: int) -> int:
        return codex_tokens(codex_line(s, texts[s.name][:chars]))

    size = table + sum(cost(s, len(texts[s.name])) for s in skills)
    least = [cost(s, 0) for s in skills]
    sent: dict[str, int | None] = {}
    if size - table <= limit:
        sent = {s.name: len(texts[s.name]) for s in skills}
    elif sum(least) <= limit:
        chars = [0] * len(skills)
        spent = least[:]  # tokens of each line as it stands
        room = limit - sum(least)
        changed = True
        while changed:
            changed = False
            for i, s in enumerate(skills):
                if chars[i] >= len(texts[s.name]):
                    continue
                more = cost(s, chars[i] + 1) - spent[i]
                if more <= room:
                    chars[i] += 1
                    spent[i] += more
                    room -= more
                    changed = True
        sent = {s.name: n for s, n in zip(skills, chars, strict=True)}
    else:
        used = 0
        for s, line in zip(skills, least, strict=True):
            fits = used + line <= limit  # a later, shorter name may still fit
            used += line if fits else 0
            sent[s.name] = 0 if fits else None
        return CodexFit(sent, table + used, size, None)
    used = table + sum(cost(s, n) for s in skills if (n := sent[s.name]) is not None)
    cut = [n for s in skills if (n := sent[s.name]) is not None and n < len(texts[s.name])]
    return CodexFit(sent, used, size, max(cut) if cut else CODEX_DESCRIPTION_CAP)
