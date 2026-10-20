"""Cursor (IDE and the `agent` CLI). Research R3, R5; spikes S1, S5; write-matrix.md.

Cursor keeps plugin installs and some switches in internal SQLite databases. We read them in
read-only mode and only through an allowlist of non-secret keys, and never write them. The only
writes are minimal JSON edits of `mcp.json`.
"""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from kitden.changes.json_splice import ABSENT
from kitden.clients.base import (
    REMOVE_DIRECT,
    SETUP_NAME,
    ClientAdapter,
    Reader,
    Scan,
    bearer_header,
    file_source,
    is_direct_entry,
    mcp_item,
    project,
    skill_items,
)
from kitden.model import (
    Enabled,
    FileEdit,
    Gateway,
    GatewayAuth,
    Item,
    ItemKind,
    ReadStatus,
    Scope,
    Source,
    SourceKind,
    Step,
    UnknownReason,
)

CLIENT = "cursor"
RESTART = "Restart Cursor for this to take effect."
CURSOR_HINT = (
    "Cursor has no plugin on/off. Change it in Cursor: Customize → Plugins → the plugin's menu "
    "(Add for Myself / Add to Project)."
)
IMPORT_HINT = (
    "Cursor loads this Claude Code plugin. Turn it off in Claude Code, or turn off "
    "Include Third-Party Plugins in Cursor Settings."
)
STATE_DB = "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
WORKSPACE_STATE = "Library/Application Support/Cursor/User/workspaceStorage"
SNAPSHOT_PREFIX = "workbench.customize.primitiveSourceSnapshot."
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
    skills_folder = ".cursor/skills"
    skill_note = RESTART

    def item_actions(self, item: Item) -> tuple[str, ...]:
        direct = is_direct_entry(item, CLIENT, {Scope.USER, Scope.PROJECT})
        return (REMOVE_DIRECT,) if direct else ()

    def reads_other_clients(self) -> bool:
        """Include Third-Party Plugins is on (the default): Cursor also reads ~/.claude/skills
        and ~/.codex/skills, so a skill there reaches Cursor too."""
        _, flags = self._state(Reader(CLIENT))
        return flags.get("thirdPartyExtensibilityEnabled", True) is not False

    def imports_claude_plugins(self) -> bool:
        """Include Third-Party Plugins and the import of Claude Code plugins are both on (the
        defaults): Cursor loads the plugins Claude Code has, as the scan reads them."""
        _, flags = self._state(Reader(CLIENT))
        third_party = flags.get("thirdPartyExtensibilityEnabled", True) is not False
        return third_party and flags.get("importPluginsFromClaudeOnBoot", True) is not False

    def gateway_step(self, gateway: Gateway, name: str) -> Step:
        value: dict[str, Any] = {"url": gateway.url}
        headers = bearer_header(gateway, "${{env:{}}}")
        if headers:
            value["headers"] = headers
        login = None
        if gateway.auth is GatewayAuth.OAUTH:
            login = f"In Cursor, open Settings → MCP, find {name} and choose Connect to log in."
        return self._add_entry(name, value, login)

    def setup_server_step(self, command: str, args: list[str]) -> Step:
        return self._add_entry(SETUP_NAME, {"command": command, "args": args})

    def _add_entry(self, name: str, value: dict[str, Any], login: str | None = None) -> Step:
        edit = FileEdit(
            path=str(self.home / ".cursor/mcp.json"),
            fmt="json",
            key=("mcpServers", name),
            after=value,
        )
        return Step(
            client=CLIENT,
            scope=Scope.USER,
            name=name,
            edit=edit,
            restart_note=RESTART,
            login_note=login,
        )

    def remove_step(self, item: Item) -> Step:
        if REMOVE_DIRECT not in self.item_actions(item):
            raise ValueError(f"{item.name} cannot be removed here")
        edit = FileEdit(
            path=str(item.source.path),
            fmt="json",
            key=("mcpServers", item.name),
            after=ABSENT,
        )
        return Step(
            client=CLIENT,
            scope=item.scope,
            name=item.name,
            edit=edit,
            restart_note=RESTART,
            shared_file=item.scope is Scope.PROJECT,
        )

    def scan(self) -> Scan:
        read = Reader(CLIENT)
        scan = Scan()
        installed, flags = self._state(read)
        third_party = flags.get("thirdPartyExtensibilityEnabled", True) is not False
        import_claude_plugins = flags.get("importPluginsFromClaudeOnBoot", True) is not False

        workspaces = sorted({p for key in installed for p in _workspaces(key) if p})
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

    def _state(self, read: Reader) -> tuple[dict[str, list], dict]:
        """Installed-plugin rows by key, and the reactive-storage switches (S5)."""
        db = self.home / STATE_DB
        if not db.is_file():
            return {}, {}
        query = "SELECT key, value FROM ItemTable WHERE key LIKE ? OR key = ?"
        try:
            with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as con:
                rows = con.execute(query, (INSTALLED_PREFIX + "%", REACTIVE_KEY)).fetchall()
        except sqlite3.DatabaseError:
            read.problem(db, UnknownReason.UNRECOGNIZED_FORMAT)
            return {}, {}
        installed: dict[str, list] = {}
        flags: dict = {}
        for key, value in rows:
            try:
                data = json.loads(value)
            except (TypeError, ValueError):
                continue
            if key == REACTIVE_KEY:
                flags = _dict(data)
            else:
                installed[key] = data if isinstance(data, list) else []
        return installed, flags

    def _plugins(self, installed: dict[str, list]) -> list[Item]:
        """Installed plugins (spike S1).

        Cursor has no plugin on/off switch: a plugin is installed for the user or for a project,
        and installed means loaded. Each `installedIds.<team>|<workspace>` row lists the user's
        plugins (`sources: ["user"]`) and that project's own (`["project"]`). Project rows are
        updated only when Cursor opens the project, so user installs come from the
        `no-workspace` row when there is one. A multi-folder window shows the project installs
        of all its folders, so its rows only add plugins that none of its folders has already,
        and only to folders without a row of their own.
        """
        if not installed:
            return self._cached_plugins()
        places = {key: _workspaces(key) for key in installed}
        has_user_row = [None] in places.values()
        own_rows = {p[0] for p in places.values() if len(p) == 1 and p[0]}
        found: dict[tuple[str, str | None], str] = {}
        for key in sorted(installed, key=lambda k: len(places[k])):  # single folders first
            for entry in installed[key]:
                plugin_id = _dict(entry).get("id")
                if not isinstance(plugin_id, str):
                    continue
                if "project" in (_dict(entry).get("sources") or []):
                    folders = [p for p in places[key] if p]
                    if len(folders) > 1:
                        if any((plugin_id, p) in found for p in folders):
                            continue
                        folders = [p for p in folders if p not in own_rows]
                    targets = folders
                elif places[key] == [None] or not has_user_row:
                    targets = [None]
                else:
                    continue  # an old copy of the user's installs
                for place in targets:
                    found.setdefault((plugin_id, place), key)

        names = self._plugin_names()
        db = str(self.home / STATE_DB)
        items = []
        for (plugin_id, place), key in found.items():
            if "@" in plugin_id:
                name = plugin_id
            else:
                name = names.get(plugin_id, f"plugin {plugin_id} (name not stored locally)")
            fresh = place is None and has_user_row
            source = Source(
                kind=SourceKind.STATE_DATABASE,
                path=db,
                owner_client=CLIENT,
                key_path=key,
                read_status=ReadStatus.UNKNOWN,
                unknown_reason=(
                    UnknownReason.NOT_DOCUMENTED if fresh else UnknownReason.MAY_BE_STALE
                ),
            )
            items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=name,
                    source=source,
                    scope=Scope.PROJECT if place else Scope.USER,
                    project=place,
                    enabled=Enabled.ON,
                    change_hint=CURSOR_HINT,
                )
            )
        return items

    def _plugin_names(self) -> dict[str, str]:
        """Plugin id -> 'name@marketplace', from Customize snapshots in workspace state (S1).

        Best effort: an unreadable snapshot only means some plugins are shown by number.
        """
        cache = self.home / ".cursor/plugins/cache"
        names: dict[str, str] = {}
        for db in sorted((self.home / WORKSPACE_STATE).glob("*/state.vscdb")):
            try:
                with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as con:
                    query = "SELECT value FROM ItemTable WHERE key LIKE ?"
                    values = [v for (v,) in con.execute(query, (SNAPSHOT_PREFIX + "%",))]
            except sqlite3.DatabaseError:
                continue
            for value in values:
                try:
                    descriptors = _dict(json.loads(value)).get("descriptors")
                except (TypeError, ValueError):
                    continue
                for descriptor in descriptors if isinstance(descriptors, list) else []:
                    plugin_id = _dict(descriptor).get("pluginId")
                    path = _dict(descriptor).get("filePath")
                    if plugin_id is None or not isinstance(path, str):
                        continue
                    try:
                        parts = Path(path).relative_to(cache).parts
                    except ValueError:
                        continue  # e.g. a Claude Code plugin that Cursor imports
                    if len(parts) >= 2:
                        names.setdefault(str(plugin_id), f"{parts[1]}@{parts[0]}")
        return names

    def _cached_plugins(self) -> list[Item]:
        """Without install records, list downloaded plugins; a download may be uninstalled."""
        cache = self.home / ".cursor/plugins/cache"
        items = []
        for marketplace in sorted(cache.iterdir()) if cache.is_dir() else []:
            for plugin in sorted(marketplace.iterdir()) if marketplace.is_dir() else []:
                if plugin.is_dir() and not plugin.name.startswith("."):
                    source = Source(
                        kind=SourceKind.PLUGIN,
                        path=str(plugin),
                        owner_client=CLIENT,
                        read_status=ReadStatus.UNKNOWN,
                        unknown_reason=UnknownReason.NOT_DOCUMENTED,
                    )
                    items.append(
                        Item(
                            client=CLIENT,
                            kind=ItemKind.PLUGIN,
                            name=f"{plugin.name}@{marketplace.name}",
                            source=source,
                            scope=Scope.USER,
                            enabled=Enabled.UNKNOWN,
                            change_hint=CURSOR_HINT,
                        )
                    )
        return items

    def plugin_folders(self) -> dict[str, Path]:
        """Plugin id -> the newest downloaded version of it in Cursor's plugin cache.

        The cache is `plugins/cache/<marketplace>/<plugin>/<version>/`, where a version is a
        commit-hash folder and a plugin may keep several (checked on a real Cursor install,
        2026-10-20). Hidden folders are skipped.
        """

        def folders(parent: Path) -> list[Path]:
            found = parent.iterdir() if parent.is_dir() else []
            return sorted(p for p in found if p.is_dir() and not p.name.startswith("."))

        out: dict[str, Path] = {}
        for marketplace in folders(self.home / ".cursor/plugins/cache"):
            for plugin in folders(marketplace):
                versions = folders(plugin)
                if versions:
                    newest = max(versions, key=lambda v: v.stat().st_mtime)
                    out[f"{plugin.name}@{marketplace.name}"] = newest
        return out

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
                    change_hint=IMPORT_HINT,
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
