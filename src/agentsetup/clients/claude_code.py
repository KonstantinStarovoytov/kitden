"""Claude Code (CLI and the Claude Desktop Code tab). Read-only. Research R3."""

from pathlib import Path
from typing import Any

from agentsetup.clients.base import (
    ClientAdapter,
    Reader,
    Scan,
    file_source,
    mcp_item,
    project,
    skill_items,
)
from agentsetup.clients.versions import highest_version, is_supported
from agentsetup.model import (
    Client,
    ClientStatus,
    Enabled,
    Item,
    ItemKind,
    ReadStatus,
    Scope,
    Source,
    SourceKind,
    UnknownReason,
)

CLIENT = "claude_code"
DESKTOP = "claude_desktop_code_tab"
DESKTOP_CONFIG = "Library/Application Support/Claude/claude_desktop_config.json"
DESKTOP_BUNDLED = "Library/Application Support/Claude/claude-code"


def _on(value: bool | None) -> Enabled:
    return Enabled.UNKNOWN if value is None else (Enabled.ON if value else Enabled.OFF)


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


class ClaudeCodeAdapter(ClientAdapter):
    id = CLIENT
    display_name = "Claude Code"
    config_root = ".claude"

    def extra_clients(self) -> list[Client]:
        """The Claude Desktop Code tab: Claude Code settings plus claude_desktop_config.json."""
        config = self.home / DESKTOP_CONFIG
        bundled = self.home / DESKTOP_BUNDLED
        if not config.exists() and not bundled.is_dir():
            return []
        version = highest_version(p.name for p in bundled.iterdir()) if bundled.is_dir() else None
        return [
            Client(
                id=DESKTOP,
                display_name="Claude Desktop (Code tab)",
                status=ClientStatus.FOUND,
                version=version,
                version_supported=is_supported(DESKTOP, version),
                config_roots=(str(config.parent),),
            )
        ]

    def scan(self) -> Scan:
        read = Reader(CLIENT)
        scan = Scan()
        state_path = self.home / ".claude.json"
        settings_path = self.home / ".claude/settings.json"
        state = _dict(read.json(state_path))
        settings = _dict(read.json(settings_path))
        settings_known = not read.failed(settings_path)

        # MCP servers: user scope, then per-project local scope and project .mcp.json files.
        for name, entry in _dict(state.get("mcpServers")).items():
            scan.items.append(
                mcp_item(
                    CLIENT,
                    name,
                    entry,
                    file_source(state_path, CLIENT, f"mcpServers.{name}"),
                    Scope.USER,
                )
            )
        for path, data in _dict(state.get("projects")).items():
            data = _dict(data)
            scan.projects.append(project(path, CLIENT))
            for name, entry in _dict(data.get("mcpServers")).items():
                key = f"projects.{path}.mcpServers.{name}"
                scan.items.append(
                    mcp_item(
                        CLIENT,
                        name,
                        entry,
                        file_source(state_path, CLIENT, key),
                        Scope.LOCAL,
                        project=path,
                    )
                )
            scan.items += self._project_files(read, Path(path), data)

        # Plugins: user settings decide on/off; project settings may override.
        enabled = _dict(settings.get("enabledPlugins"))
        installed = _dict(
            _dict(read.json(self.home / ".claude/plugins/installed_plugins.json")).get("plugins")
        )
        for plugin_id, installs in installed.items():
            state_on = _on(enabled.get(plugin_id)) if settings_known else Enabled.UNKNOWN
            if settings_known and plugin_id not in enabled:
                state_on = Enabled.ON  # installed plugins are on unless turned off
            source = file_source(settings_path, CLIENT, f"enabledPlugins.{plugin_id}")
            scan.items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=plugin_id,
                    source=source,
                    scope=Scope.USER,
                    enabled=state_on,
                )
            )
            for install in installs if isinstance(installs, list) else []:
                scan.items += self._plugin_parts(
                    read, Path(_dict(install).get("installPath", "")), state_on
                )
        for plugin_id, value in enabled.items():
            if plugin_id.endswith("@synced"):
                account = Source(
                    kind=SourceKind.ACCOUNT,
                    path=None,
                    owner_client=CLIENT,
                    read_status=ReadStatus.UNKNOWN,
                    unknown_reason=UnknownReason.STORED_IN_ACCOUNT,
                )
                scan.items.append(
                    Item(
                        client=CLIENT,
                        kind=ItemKind.PLUGIN,
                        name=plugin_id,
                        source=account,
                        scope=Scope.ACCOUNT,
                        enabled=_on(value),
                    )
                )
        scan.items.append(
            Item(
                client=CLIENT,
                kind=ItemKind.PLUGIN,
                name="Claude account plugins and connectors",
                source=Source(
                    kind=SourceKind.ACCOUNT,
                    path=None,
                    owner_client=CLIENT,
                    read_status=ReadStatus.UNKNOWN,
                    unknown_reason=UnknownReason.STORED_IN_ACCOUNT,
                ),
                scope=Scope.ACCOUNT,
                enabled=Enabled.UNKNOWN,
            )
        )

        # Skills, hooks and marketplaces.
        scan.items += skill_items(CLIENT, self.home / ".claude/skills", Scope.USER, CLIENT)
        scan.items += self._hooks(settings, settings_path, Scope.USER)
        marketplaces_path = self.home / ".claude/plugins/known_marketplaces.json"
        for name in _dict(read.json(marketplaces_path)):
            scan.items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.MARKETPLACE,
                    name=name,
                    source=file_source(marketplaces_path, CLIENT, name),
                    scope=Scope.USER,
                )
            )

        # Claude Desktop Code tab also loads claude_desktop_config.json.
        desktop_path = self.home / DESKTOP_CONFIG
        for name, entry in _dict(_dict(read.json(desktop_path)).get("mcpServers")).items():
            scan.items.append(
                mcp_item(
                    DESKTOP,
                    name,
                    entry,
                    file_source(desktop_path, DESKTOP, f"mcpServers.{name}"),
                    Scope.USER,
                )
            )

        scan.problems = read.problems
        return scan

    def _project_files(self, read: Reader, root: Path, data: dict) -> list[Item]:
        path = str(root)
        items: list[Item] = []
        approved = set(data.get("enabledMcpjsonServers") or [])
        rejected = set(data.get("disabledMcpjsonServers") or [])
        mcp_path = root / ".mcp.json"
        for name, entry in _dict(_dict(read.json(mcp_path)).get("mcpServers")).items():
            state = (
                Enabled.OFF
                if name in rejected
                else (
                    Enabled.ON
                    if name in approved or data.get("enableAllProjectMcpServers")
                    else Enabled.UNKNOWN
                )
            )
            items.append(
                mcp_item(
                    CLIENT,
                    name,
                    entry,
                    file_source(mcp_path, CLIENT, f"mcpServers.{name}"),
                    Scope.PROJECT,
                    project=path,
                    enabled=state,
                )
            )
        settings_path = root / ".claude/settings.json"
        settings = _dict(read.json(settings_path))
        for plugin_id, value in _dict(settings.get("enabledPlugins")).items():
            items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=plugin_id,
                    source=file_source(settings_path, CLIENT, f"enabledPlugins.{plugin_id}"),
                    scope=Scope.PROJECT,
                    project=path,
                    enabled=_on(value),
                )
            )
        items += self._hooks(settings, settings_path, Scope.PROJECT, project=path)
        items += skill_items(CLIENT, root / ".claude/skills", Scope.PROJECT, CLIENT, project=path)
        return items

    def _plugin_parts(self, read: Reader, root: Path, enabled: Enabled) -> list[Item]:
        if not root.is_dir():
            return []
        items = skill_items(
            CLIENT, root / "skills", Scope.PLUGIN, CLIENT, kind=SourceKind.PLUGIN, enabled=enabled
        )
        mcp_path = root / ".mcp.json"
        for name, entry in _dict(_dict(read.json(mcp_path)).get("mcpServers")).items():
            source = file_source(mcp_path, CLIENT, f"mcpServers.{name}", kind=SourceKind.PLUGIN)
            items.append(mcp_item(CLIENT, name, entry, source, Scope.PLUGIN, enabled=enabled))
        return items

    def _hooks(
        self, settings: dict, path: Path, scope: Scope, project: str | None = None
    ) -> list[Item]:
        items = []
        for event, groups in _dict(settings.get("hooks")).items():
            for group in groups if isinstance(groups, list) else []:
                matcher = _dict(group).get("matcher") or "*"
                items.append(
                    Item(
                        client=CLIENT,
                        kind=ItemKind.HOOK,
                        name=f"{event}: {matcher}",
                        source=file_source(path, CLIENT, f"hooks.{event}"),
                        scope=scope,
                        project=project,
                    )
                )
        return items
