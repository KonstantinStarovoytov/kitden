"""Stands in for the client commands in `kitden demo` only. No real client runs.

It knows the Claude Code and Codex commands Kitden's own changes run, and writes only the
entry each change checks, in the sample home, keeping the file's format:
- `claude mcp add-json -s user <name> <json>`;
- `claude mcp remove -s user|local|project <name>`;
- `claude plugin install|uninstall|enable|disable <id> -s user|project ...`;
- `codex plugin add <id> --json` and `codex plugin remove <id>`.

Anything else, such as adding a marketplace, and any folder outside the sample, answers
NOT_IN_DEMO and writes nothing. A user-scope plugin install writes only `enabledPlugins`: the
change checks out, but Claude Code lists its plugins from `installed_plugins.json`, so the
plugin does not show after Rescan.
"""

import json
import os
from pathlib import Path
from typing import Any

from kitden.changes import json_splice, toml_edit
from kitden.changes.atomic import write_atomic
from kitden.changes.client_cli import CommandResult
from kitden.changes.json_splice import ABSENT

NOT_IN_DEMO = "Not part of the demo."
REFUSED = CommandResult(1, NOT_IN_DEMO)
# What each plugin command leaves in `enabledPlugins`; ABSENT removes the key.
PLUGIN_VALUES = {"install": True, "enable": True, "disable": False, "uninstall": ABSENT}


class DemoRunner:
    """The engine's command runner in the demo: `(command, cwd) -> CommandResult`."""

    def __init__(self, home: Path) -> None:
        # Resolved once: on macOS the temp folder /var is a link to /private/var.
        self.home = Path(home).resolve()

    def __call__(self, command: list[str], cwd: str | None) -> CommandResult:
        folder = None
        if cwd is not None:
            folder = Path(os.path.realpath(cwd))
            if folder != self.home and self.home not in folder.parents:
                return REFUSED
        found = self._entry(command, folder)
        if found is None:
            return REFUSED
        path, key, value = found
        editor: Any = toml_edit if path.suffix == ".toml" else json_splice
        old = path.read_text() if path.exists() else ("" if editor is toml_edit else "{}")
        if value is ABSENT:
            new = editor.delete_value(old, key)
        else:
            new = editor.set_value(old, key, value)
        if new != old:
            path.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(path, new.encode())
        return CommandResult(0, "")

    def _entry(
        self, command: list[str], folder: Path | None
    ) -> tuple[Path, tuple[str, ...], Any] | None:
        """The file, the key and the value a command leaves there; None for a command the demo
        does not know."""
        home = self.home
        match command:
            case ["claude", "mcp", "add-json", "-s", "user", name, value]:
                return home / ".claude.json", ("mcpServers", name), json.loads(value)
            case ["claude", "mcp", "remove", "-s", "user", name]:
                return home / ".claude.json", ("mcpServers", name), ABSENT
            case ["claude", "mcp", "remove", "-s", "local", name] if folder is not None:
                return home / ".claude.json", ("projects", str(folder), "mcpServers", name), ABSENT
            case ["claude", "mcp", "remove", "-s", "project", name] if folder is not None:
                return folder / ".mcp.json", ("mcpServers", name), ABSENT
            case ["claude", "plugin", verb, plugin, "-s", scope, *_] if verb in PLUGIN_VALUES:
                root = {"user": home, "project": folder}.get(scope)
                if root is None:
                    return None
                key = ("enabledPlugins", plugin)
                return root / ".claude/settings.json", key, PLUGIN_VALUES[verb]
            case ["codex", "plugin", "add", plugin, "--json"]:
                return home / ".codex/config.toml", ("plugins", plugin, "enabled"), True
            case ["codex", "plugin", "remove", plugin]:
                return home / ".codex/config.toml", ("plugins", plugin), ABSENT
        return None
