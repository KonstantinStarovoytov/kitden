"""Numbers behind the skill list rules. Each one is a fact about a client and can change."""

# model id -> (window, characters per token). checked 2026-11-13 (Claude Code 2.1.321 binary:
# `context.window` in its model list, and `bytesPerTokenForModel`, which gives 4 only to older
# ids such as sonnet-4-6; code.claude.com/docs/en/model-config: Fable, Sonnet 5 and later,
# Haiku 5.5 and Opus 4.7 and later run with 1M by default). Older ids stay while chats name them.
CLAUDE_WINDOWS: dict[str, tuple[int, int]] = {
    "claude-opus-5-5": (1_000_000, 3),
    "claude-sonnet-5-5": (1_000_000, 3),
    "claude-fable-5-2": (1_000_000, 3),
    "claude-haiku-5-5": (1_000_000, 3),
    "claude-fable-5-1": (1_000_000, 3),
    "claude-sonnet-4-6": (200_000, 4),
}

# checked 2026-11-10 (real logs): the log does not say the window, and a model can run with
# another one than the table says. The limits Kitden tries then: (window, characters per token).
CLAUDE_CANDIDATES: tuple[tuple[int, int], ...] = (
    (200_000, 3),
    (200_000, 4),
    (1_000_000, 3),
    (1_000_000, 4),
)

# The estimate for the other kind of window than the last chat's: last window -> (window,
# characters per token).
CLAUDE_OTHER_WINDOW: dict[int, tuple[int, int]] = {
    1_000_000: (200_000, 4),
    200_000: (1_000_000, 3),
}

# checked 2026-11-07 (Claude Code 2.1.311, two test chats): skills that always keep their
# description, whatever the budget. Every chat checks them: with a wrong name the rule does not
# rebuild the list, and Kitden shows no estimate. One chat cannot tell them apart from skills
# that simply fit. checked 2026-11-12 (real log, Claude Code 2.1.309): the same 15.
CLAUDE_ALWAYS_FULL = frozenset(
    {
        "dataviz",
        "artifact-design",
        "artifact-diagramming",
        "artifact-capabilities",
        "update-config",
        "keybindings-help",
        "code-review",
        "simplify",
        "fewer-permission-prompts",
        "loop",
        "schedule",
        "claude-api",
        "workflow-authoring",
        "run",
        "plugin-authoring",
    }
)

# checked 2026-11-07 (Claude Code 2.1.311, two test chats): the skill list may use 1% of the
# window, and one description is cut at 1536 characters.
CLAUDE_SHARE = 0.01
CLAUDE_DESCRIPTION_CAP = 1536

# checked 2026-11-06 (codex-rs/ext/skills/src/render.rs): the list may use 2% of the window,
# and one description is cut at 1024 characters.
CODEX_SHARE = 0.02
CODEX_DESCRIPTION_CAP = 1024
# checked 2026-11-12 (codex-rs/ext/skills/src/catalog_prompt.rs): the list's opening words, with
# full paths and with short paths and a roots table. Only the difference in tokens is charged.
CODEX_INTRO = (
    "A skill is a set of instructions provided through a `SKILL.md` source. Below is the list of "
    "skills that can be used. Each entry includes a name, description, and source locator. `file` "
    "locators are on the host filesystem, `executor package` locators are owned by their "
    "execution environment, `cloud package` locators are opaque package identifiers, and `custom "
    "resource` locators use their provider's access mechanism."
)
CODEX_INTRO_ROOTS = (
    "A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below "
    "is the list of skills that can be used. Each entry includes a name, description, and a short "
    "path that can be expanded into an absolute path using the skill roots table."
)
# checked 2026-11-06 (Codex docs, skills.max_context_tokens: "up to 10,000 tokens")
CODEX_MAX_LIMIT = 10_000
