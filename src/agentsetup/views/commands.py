"""Commands the page shows but never runs (FR-029): install, update, move, marketplaces.

Command syntax checked against `--help` of Claude Code 2.1.283 and Codex CLI 0.159.2 on
2026-10-17. Cursor has no command line here, so Cursor gets directions in its interface.
"""

import shlex
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from agentsetup.clients.base import ClientAdapter
from agentsetup.model import Item, ItemKind, Scope
from agentsetup.redact import redact_text

CLAUDE = "claude_code"
CODEX = "codex"
CURSOR = "cursor"
CURSOR_LOADS_CLAUDE = (
    "Cursor loads Claude Code plugins when Include Third-Party Plugins is on in Cursor Settings."
)
CURSOR_ADD = "In Cursor: Customize → Plugins, find the plugin and choose Add to Cursor."


@dataclass(frozen=True)
class Command:
    label: str
    command: str | None = None  # the developer runs it; None when there is no command
    note: str | None = None


def _safe(source: str) -> str:
    """A marketplace source without credentials."""
    parts = urlsplit(source)
    if parts.scheme and parts.netloc and "@" in parts.netloc:
        source = urlunsplit(parts._replace(netloc=parts.netloc.rsplit("@", 1)[1]))
    return redact_text(source)


def marketplace_add(client: str, source: str) -> str:
    tool = "claude" if client == CLAUDE else "codex"
    return f"{tool} plugin marketplace add {shlex.quote(_safe(source))}"


def _sources(adapters: dict[str, ClientAdapter], client: str) -> dict[str, str | None]:
    adapter = adapters.get(client)
    return adapter.marketplace_sources() if adapter else {}


def _claude_plugin(item: Item, adapters: dict[str, ClientAdapter]) -> list[Command]:
    plugin_id = shlex.quote(item.name)
    marketplace = item.name.partition("@")[2]
    commands = [
        Command("Update in Claude Code", f"claude plugin update {plugin_id}"),
        Command(
            "Uninstall from Claude Code", f"claude plugin uninstall {plugin_id} -s {item.scope}"
        ),
    ]
    source = _sources(adapters, CLAUDE).get(marketplace)
    if source:
        steps = f"{marketplace_add(CODEX, source)}\ncodex plugin add {plugin_id}"
        commands.append(Command("Install in Codex", steps))
    else:
        commands.append(Command("Install in Codex", note="The marketplace source is not known."))
    commands.append(Command("Use in Cursor", note=CURSOR_LOADS_CLAUDE))
    return commands


def _codex_plugin(item: Item, adapters: dict[str, ClientAdapter]) -> list[Command]:
    plugin_id = shlex.quote(item.name)
    marketplace = item.name.partition("@")[2]
    commands = [Command("Uninstall from Codex", f"codex plugin remove {plugin_id}")]
    sources = _sources(adapters, CODEX)
    source = sources.get(marketplace)
    if source:
        commands.append(
            Command(
                "Update in Codex", f"codex plugin marketplace upgrade {shlex.quote(marketplace)}"
            )
        )
        steps = f"{marketplace_add(CLAUDE, source)}\nclaude plugin install {plugin_id}"
        commands.append(Command("Install in Claude Code", steps))
    elif marketplace in sources or marketplace.startswith("openai-"):
        commands.append(
            Command(
                "Install in Claude Code",
                note="This plugin comes with Codex; it cannot be installed elsewhere.",
            )
        )
    else:
        commands.append(
            Command("Install in Claude Code", note="The marketplace source is not known.")
        )
    return commands


def _marketplace(item: Item, adapters: dict[str, ClientAdapter]) -> list[Command]:
    name = shlex.quote(item.name)
    if item.client == CLAUDE:
        source = _sources(adapters, CLAUDE).get(item.name)
        commands = [Command("Remove from Claude Code", f"claude plugin marketplace remove {name}")]
        if source:
            commands.append(Command("Add to Codex", marketplace_add(CODEX, source)))
        return commands
    if item.client == CODEX:
        source = _sources(adapters, CODEX).get(item.name)
        commands = [Command("Remove from Codex", f"codex plugin marketplace remove {name}")]
        if source:
            commands.append(Command("Add to Claude Code", marketplace_add(CLAUDE, source)))
        else:
            commands.append(
                Command("Add to Claude Code", note="This marketplace comes with Codex.")
            )
        return commands
    return [Command("Change in Cursor", note="In Cursor: Customize → Plugins → Marketplaces.")]


def commands_for(item: Item, adapters: dict[str, ClientAdapter]) -> list[Command]:
    """Show-only commands for one plugin or marketplace item."""
    if item.kind is ItemKind.MARKETPLACE:
        return _marketplace(item, adapters)
    if item.kind is not ItemKind.PLUGIN:
        return []
    if item.scope is Scope.ACCOUNT or "@" not in item.name:
        return [Command("Change it", note=item.change_hint)] if item.change_hint else []
    if item.client == CLAUDE:
        return _claude_plugin(item, adapters)
    if item.client == CODEX:
        return _codex_plugin(item, adapters)
    if item.client == CURSOR:
        return [Command("Change in Cursor", note=item.change_hint or CURSOR_ADD)]
    return []
