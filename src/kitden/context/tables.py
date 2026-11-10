"""Numbers behind the skill list rules. Each one is a fact about a client and can change."""

# checked 2026-11-06 (Claude Code 2.1.311 binary, `EH`): model id -> (window, characters per token).
CLAUDE_WINDOWS: dict[str, tuple[int, int]] = {
    "claude-opus-5-5": (1_000_000, 3),
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

# The estimate for a chat whose model is not known: the other kind of window than the last one.
# last window -> (window, characters per token, name shown)
CLAUDE_OTHER_WINDOW: dict[int, tuple[int, int, str]] = {
    1_000_000: (200_000, 4, "Older models"),
    200_000: (1_000_000, 3, "Opus 5.5, Fable 5.1"),
}

# checked 2026-11-07 (Claude Code 2.1.311, two test chats): skills that always keep their
# description, whatever the budget.
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
# Fitted to the real list of 2026-10-30, not read from Codex: tokens the list spends on its
# own text before the first skill.
CODEX_FIXED_TOKENS = 166
CODEX_DESCRIPTION_CAP = 1024
# checked 2026-11-06 (Codex docs, skills.max_context_tokens: "up to 10,000 tokens")
CODEX_MAX_LIMIT = 10_000
