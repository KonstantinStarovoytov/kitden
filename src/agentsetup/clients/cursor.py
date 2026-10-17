"""Cursor (IDE and the `agent` CLI). Read-only. Research R3, R5; spike S5.

Cursor keeps plugin installs and some switches in an internal SQLite database. We read it in
read-only mode and only through an allowlist of non-secret keys. Plugin on/off stays unknown
until spike S1 shows where it is stored.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from agentsetup.clients.base import (
    ClientAdapter,
    Reader,
    Scan,
    file_source,
    mcp_item,
    project,
    skill_items,
)
from agentsetup.model import (
    Enabled,
    Item,
    ItemKind,
    ReadStatus,
    Scope,
    Source,
    SourceKind,
    UnknownReason,
)

CLIENT = "cursor"
STATE_DB = "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
REACTIVE_KEY = (
    "src.vs.platform.reactivestorage.browser.reactiveStorageServiceImpl"
    ".persistentStorage.applicationUser"
)
INSTALLED_PREFIX = "cursor.plugins.installedIds."


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _workspaces(key: str) -> list[str | None]:
    """'cursor.plugins.installedIds.<team>|<workspace>' -> project paths (None = no project)."""
    workspace = key.split("|", 1)[1] if "|" in key else "no-workspace"
    if workspace == "no-workspace":
        return [None]
    return [unquote(urlsplit(uri).path) for uri in workspace.split(",")]


class CursorAdapter(ClientAdapter):
    id = CLIENT
    display_name = "Cursor"
    config_root = ".cursor"

    def scan(self) -> Scan:
        read = Reader(CLIENT)
        scan = Scan()
        installed, flags = self._state(read)
        third_party = flags.get("thirdPartyExtensibilityEnabled", True) is not False
        import_claude_plugins = flags.get("importPluginsFromClaudeOnBoot", True) is not False

        workspaces = sorted({p for paths in installed.values() for p in paths if p})
        scan.projects = [project(path, CLIENT) for path in workspaces]

        user_mcp = self.home / ".cursor/mcp.json"
        for name, entry in _dict(_dict(read.json(user_mcp)).get("mcpServers")).items():
            scan.items.append(
                mcp_item(
                    CLIENT,
                    name,
                    entry,
                    file_source(user_mcp, CLIENT, f"mcpServers.{name}"),
                    Scope.USER,
                )
            )
        for path in workspaces:
            mcp_path = Path(path) / ".cursor/mcp.json"
            for name, entry in _dict(_dict(read.json(mcp_path)).get("mcpServers")).items():
                scan.items.append(
                    mcp_item(
                        CLIENT,
                        name,
                        entry,
                        file_source(mcp_path, CLIENT, f"mcpServers.{name}"),
                        Scope.PROJECT,
                        project=path,
                    )
                )

        scan.items += self._skills(self.home, Scope.USER, None, third_party)
        for path in workspaces:
            scan.items += self._skills(Path(path), Scope.PROJECT, path, third_party)

        scan.items += self._plugins(installed)
        if third_party and import_claude_plugins:
            scan.items += self._claude_plugins(read)

        marketplaces = self.home / ".cursor/plugins/marketplaces"
        for folder in sorted(marketplaces.iterdir()) if marketplaces.is_dir() else []:
            if folder.is_dir() and not folder.name.startswith("."):
                scan.items.append(
                    Item(
                        client=CLIENT,
                        kind=ItemKind.MARKETPLACE,
                        name=folder.name,
                        source=file_source(folder, CLIENT, kind=SourceKind.FOLDER),
                        scope=Scope.USER,
                    )
                )

        scan.items += self._hooks(read, third_party)
        scan.problems = read.problems
        return scan

    def _state(self, read: Reader) -> tuple[dict[str, list[str | None]], dict]:
        """Installed plugin ids per key, and the reactive-storage switches (S5)."""
        db = self.home / STATE_DB
        if not db.is_file():
            return {}, {}
        query = "SELECT key, value FROM ItemTable WHERE key LIKE ? OR key = ?"
        try:
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
                rows = con.execute(query, (INSTALLED_PREFIX + "%", REACTIVE_KEY)).fetchall()
        except sqlite3.DatabaseError:
            read.problem(db, UnknownReason.UNRECOGNIZED_FORMAT)
            return {}, {}
        installed: dict[str, list[str | None]] = {}
        flags: dict = {}
        for key, value in rows:
            try:
                data = json.loads(value)
            except (TypeError, ValueError):
                continue
            if key == REACTIVE_KEY:
                flags = _dict(data)
                continue
            for entry in data if isinstance(data, list) else []:
                plugin_id = _dict(entry).get("id")
                if isinstance(plugin_id, str):
                    installed.setdefault(plugin_id, []).extend(_workspaces(key))
        return installed, flags

    def _plugins(self, installed: dict[str, list[str | None]]) -> list[Item]:
        """Installed plugins.

        Cursor stores numeric marketplace ids whose names live in the Cursor account. Names
        then come from the local cache, and per-project numeric installs are shown as a count
        (FR-005).
        """
        db = str(self.home / STATE_DB)
        unknown = {
            "read_status": ReadStatus.UNKNOWN,
            "unknown_reason": UnknownReason.NOT_DOCUMENTED,
        }
        items = []
        named = {pid: places for pid, places in installed.items() if "@" in pid}
        numeric = {pid: places for pid, places in installed.items() if "@" not in pid}
        for plugin_id, places in sorted(named.items()):
            for place in dict.fromkeys(places):
                source = Source(
                    kind=SourceKind.STATE_DATABASE,
                    path=db,
                    owner_client=CLIENT,
                    key_path=INSTALLED_PREFIX,
                    **unknown,
                )
                items.append(
                    Item(
                        client=CLIENT,
                        kind=ItemKind.PLUGIN,
                        name=plugin_id,
                        source=source,
                        scope=Scope.PROJECT if place else Scope.USER,
                        project=place,
                        enabled=Enabled.UNKNOWN,
                    )
                )
        if not installed or any(None in places for places in numeric.values()):
            items += self._cached_plugins(set(named), unknown)
        per_project: dict[str, int] = {}
        for places in numeric.values():
            for place in {p for p in places if p}:
                per_project[place] = per_project.get(place, 0) + 1
        for place, count in sorted(per_project.items()):
            label = (
                f"{count} plugin installed (name not stored locally)"
                if count == 1
                else f"{count} plugins installed (names not stored locally)"
            )
            source = Source(
                kind=SourceKind.STATE_DATABASE,
                path=db,
                owner_client=CLIENT,
                key_path=INSTALLED_PREFIX,
                **unknown,
            )
            items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=label,
                    source=source,
                    scope=Scope.PROJECT,
                    project=place,
                    enabled=Enabled.UNKNOWN,
                )
            )
        return items

    def _cached_plugins(self, skip: set[str], unknown: dict) -> list[Item]:
        cache = self.home / ".cursor/plugins/cache"
        items = []
        for marketplace in sorted(cache.iterdir()) if cache.is_dir() else []:
            for plugin in sorted(marketplace.iterdir()) if marketplace.is_dir() else []:
                plugin_id = f"{plugin.name}@{marketplace.name}"
                if plugin.is_dir() and not plugin.name.startswith(".") and plugin_id not in skip:
                    source = Source(
                        kind=SourceKind.PLUGIN, path=str(plugin), owner_client=CLIENT, **unknown
                    )
                    items.append(
                        Item(
                            client=CLIENT,
                            kind=ItemKind.PLUGIN,
                            name=plugin_id,
                            source=source,
                            scope=Scope.USER,
                            enabled=Enabled.UNKNOWN,
                        )
                    )
        return items

    def _skills(
        self, root: Path, scope: Scope, project_path: str | None, third_party: bool
    ) -> list[Item]:
        folders = [
            (root / ".cursor/skills", CLIENT, SourceKind.FOLDER),
            (root / ".agents/skills", "shared", SourceKind.FOLDER),
        ]
        if third_party:
            folders += [
                (root / ".claude/skills", "claude_code", SourceKind.OTHER_CLIENT_FOLDER),
                (root / ".codex/skills", "codex", SourceKind.OTHER_CLIENT_FOLDER),
            ]
        items = []
        for folder, owner, kind in folders:
            items += skill_items(CLIENT, folder, scope, owner, kind=kind, project=project_path)
        return items

    def _claude_plugins(self, read: Reader) -> list[Item]:
        """Claude Code plugins that Cursor imports (on by default)."""
        installed_path = self.home / ".claude/plugins/installed_plugins.json"
        installed = _dict(_dict(read.json(installed_path)).get("plugins"))
        enabled = _dict(_dict(read.json(self.home / ".claude/settings.json")).get("enabledPlugins"))
        items = []
        for plugin_id in installed:
            on = enabled.get(plugin_id, True) is not False
            source = file_source(
                installed_path, "claude_code", plugin_id, kind=SourceKind.OTHER_CLIENT_FOLDER
            )
            items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=plugin_id,
                    source=source,
                    scope=Scope.USER,
                    enabled=Enabled.ON if on else Enabled.OFF,
                )
            )
        return items

    def _hooks(self, read: Reader, third_party: bool) -> list[Item]:
        items = []
        hooks_path = self.home / ".cursor/hooks.json"
        for event in _dict(_dict(read.json(hooks_path)).get("hooks")):
            items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.HOOK,
                    name=event,
                    source=file_source(hooks_path, CLIENT, f"hooks.{event}"),
                    scope=Scope.USER,
                )
            )
        if third_party:
            claude_path = self.home / ".claude/settings.json"
            for event, groups in _dict(_dict(read.json(claude_path)).get("hooks")).items():
                for group in groups if isinstance(groups, list) else []:
                    matcher = _dict(group).get("matcher") or "*"
                    source = file_source(
                        claude_path,
                        "claude_code",
                        f"hooks.{event}",
                        kind=SourceKind.OTHER_CLIENT_FOLDER,
                    )
                    items.append(
                        Item(
                            client=CLIENT,
                            kind=ItemKind.HOOK,
                            name=f"{event}: {matcher}",
                            source=source,
                            scope=Scope.USER,
                        )
                    )
        return items
