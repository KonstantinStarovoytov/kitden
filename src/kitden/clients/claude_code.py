"""Claude Code (CLI and the Claude Desktop Code tab). Research R3, write-matrix.md.

Writes go through `claude mcp add-json` and `claude mcp remove` (FR-021). Claude Code rewrites
`~/.claude.json` during normal use, so changes to that file compare only the edited entry.
"""

import json
from pathlib import Path
from typing import Any

from kitden.changes.json_splice import ABSENT, PRESENT
from kitden.clients.base import (
    PLUGIN_REMOVE,
    REMOVE_DIRECT,
    SETUP_NAME,
    SKILL_REMOVE,
    ClientAdapter,
    Reader,
    Scan,
    bearer_header,
    check_toggle,
    file_source,
    is_direct_entry,
    is_own_skill,
    mcp_item,
    project,
    skill_items,
    toggle_action,
)
from kitden.clients.versions import highest_version, is_supported
from kitden.model import (
    Client,
    ClientStatus,
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

CLIENT = "claude_code"
WRITABLE_SCOPES = {Scope.USER, Scope.LOCAL, Scope.PROJECT}
NEW_SESSION = "Start a new Claude Code session (or a new Code tab chat) for this to take effect."
RELOAD = "Run /reload-plugins in Claude Code, or start a new session, for this to take effect."
ACCOUNT_HINT = "Stored in your Claude account. Change it in the Claude app or on claude.ai."
DESKTOP = "claude_desktop_code_tab"
DESKTOP_CONFIG = "Library/Application Support/Claude/claude_desktop_config.json"
DESKTOP_BUNDLED = "Library/Application Support/Claude/claude-code"
# Plugins that come from these places have no install to remove (plugins/loading docs).
NOT_INSTALLED = ("@synced", "@inline", "@skills-dir")


def _on(value: bool | None) -> Enabled:
    return Enabled.UNKNOWN if value is None else (Enabled.ON if value else Enabled.OFF)


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


class ClaudeCodeAdapter(ClientAdapter):
    id = CLIENT
    display_name = "Claude Code"
    config_root = ".claude"
    skills_folder = ".claude/skills"
    skill_note = NEW_SESSION

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

    def item_actions(self, item: Item) -> tuple[str, ...]:
        if is_direct_entry(item, CLIENT, WRITABLE_SCOPES):
            return (REMOVE_DIRECT,)
        if (
            item.kind is ItemKind.PLUGIN
            and item.client == CLIENT
            and item.source.kind is SourceKind.FILE
            and item.source.read_status is ReadStatus.OK
            and item.scope in (Scope.USER, Scope.PROJECT)
        ):
            if item.name.endswith(NOT_INSTALLED):
                return toggle_action(item)
            return (*toggle_action(item), PLUGIN_REMOVE)
        if is_own_skill(item, CLIENT):
            return (SKILL_REMOVE,)
        return ()

    def plugin_step(self, item: Item, enable: bool) -> Step:
        check_toggle(self, item, enable)
        if item.scope is Scope.PROJECT and not Path(str(item.project)).is_dir():
            raise ValueError(f"the project folder {item.project} is missing")
        edit = FileEdit(
            path=str(item.source.path),
            fmt="json",
            key=("enabledPlugins", item.name),
            after=enable,
        )
        verb = "enable" if enable else "disable"
        return Step(
            client=CLIENT,
            scope=item.scope,
            name=item.name,
            edit=edit,
            mechanism="client_cli",
            command=["claude", "plugin", verb, item.name, "-s", str(item.scope), "--json"],
            cwd=item.project if item.scope is Scope.PROJECT else None,
            restart_note=RELOAD,
            shared_file=item.scope is Scope.PROJECT,
        )

    def marketplace_sources(self) -> dict[str, str | None]:
        read = Reader(CLIENT)
        settings = _dict(read.json(self.home / ".claude/settings.json"))
        known = _dict(read.json(self.home / ".claude/plugins/known_marketplaces.json"))
        sources: dict[str, str | None] = {}
        for name, entry in {**_dict(settings.get("extraKnownMarketplaces")), **known}.items():
            source = _dict(_dict(entry).get("source"))
            value = source.get("repo") or source.get("url") or source.get("path")
            sources[name] = value if isinstance(value, str) else None
        return sources

    def marketplace_add_step(self, name: str, source: str) -> Step:
        # Checked 2026-10-19 (2.1.283): `marketplace add` records the source under
        # extraKnownMarketplaces in ~/.claude/settings.json; `remove` takes it out.
        edit = FileEdit(
            path=str(self.home / ".claude/settings.json"),
            fmt="json",
            key=("extraKnownMarketplaces", name),
            after=PRESENT,
            check="entry",
        )
        return Step(
            client=CLIENT,
            scope=Scope.USER,
            name=name,
            edit=edit,
            mechanism="client_cli",
            command=["claude", "plugin", "marketplace", "add", source],
            undo_command=["claude", "plugin", "marketplace", "remove", name],
        )

    def plugin_install_step(self, plugin_id: str) -> Step:
        # No -y: a plugin that installs by running a command stops here and says so.
        edit = FileEdit(
            path=str(self.home / ".claude/settings.json"),
            fmt="json",
            key=("enabledPlugins", plugin_id),
            after=True,
            check="entry",
        )
        return Step(
            client=CLIENT,
            scope=Scope.USER,
            name=plugin_id,
            edit=edit,
            mechanism="client_cli",
            command=["claude", "plugin", "install", plugin_id, "-s", "user", "--json"],
            undo_command=["claude", "plugin", "uninstall", plugin_id, "-s", "user", "--json"],
            restart_note=RELOAD,
        )

    # checked 2026-10-22 (`claude plugin uninstall --help`, 2.1.283, and
    # code.claude.com/docs/en/plugins/cli-reference): `uninstall <id> -s <scope> --json`
    # removes the plugin from that scope's settings file; it fails when the settings still
    # switch it on. `install` writes `true` again, so Undo of an "off" plugin sets it back off.
    # `--keep-data` keeps the plugin's data folder for Undo (checked 2026-10-22, same help); its
    # saved options and secrets still go.
    def plugin_remove_step(self, item: Item) -> Step:
        if PLUGIN_REMOVE not in self.item_actions(item):
            raise ValueError(f"{item.name} cannot be removed here")
        if item.scope is Scope.PROJECT and not Path(str(item.project)).is_dir():
            raise ValueError(f"the project folder {item.project} is missing")
        edit = FileEdit(
            path=str(item.source.path),
            fmt="json",
            key=("enabledPlugins", item.name),
            after=ABSENT,
            check="entry",
        )
        scope = str(item.scope)
        return Step(
            client=CLIENT,
            scope=item.scope,
            name=item.name,
            edit=edit,
            mechanism="client_cli",
            command=[
                "claude",
                "plugin",
                "uninstall",
                item.name,
                "-s",
                scope,
                "--keep-data",
                "--json",
            ],
            undo_command=["claude", "plugin", "install", item.name, "-s", scope, "--json"],
            cwd=item.project if item.scope is Scope.PROJECT else None,
            restart_note=RELOAD,
            shared_file=item.scope is Scope.PROJECT,
        )

    def marketplace_roots(self) -> dict[str, Path]:
        known = _dict(Reader(CLIENT).json(self.home / ".claude/plugins/known_marketplaces.json"))
        roots = {}
        for name, entry in known.items():
            where = _dict(entry).get("installLocation")
            if isinstance(where, str) and Path(where).is_dir():
                roots[name] = Path(where)
        return roots

    def gateway_step(self, gateway: Gateway, name: str) -> Step:
        value: dict[str, Any] = {"type": "http", "url": gateway.url}
        headers = bearer_header(gateway, "${{{}}}")
        if headers:
            value["headers"] = headers
        login = None
        if gateway.auth is GatewayAuth.OAUTH:
            login = f"In Claude Code, run /mcp, choose {name}, then choose Authenticate."
        return self._add_entry(name, value, login)

    def setup_server_step(self, command: str, args: list[str]) -> Step:
        return self._add_entry(SETUP_NAME, {"type": "stdio", "command": command, "args": args})

    def add_server_step(self, name: str, entry: dict) -> Step:
        return self._add_entry(name, entry)

    def _add_entry(self, name: str, value: dict[str, Any], login: str | None = None) -> Step:
        """A user-scope MCP entry, added with `claude mcp add-json` (FR-021, FR-024)."""
        edit = FileEdit(
            path=str(self.home / ".claude.json"),
            fmt="json",
            key=("mcpServers", name),
            after=value,
            check="entry",
        )
        return Step(
            client=CLIENT,
            scope=Scope.USER,
            name=name,
            edit=edit,
            mechanism="client_cli",
            command=["claude", "mcp", "add-json", "-s", "user", name, json.dumps(value)],
            restart_note=NEW_SESSION,
            login_note=login,
        )

    def remove_step(self, item: Item) -> Step:
        if REMOVE_DIRECT not in self.item_actions(item):
            raise ValueError(f"{item.name} cannot be removed here")
        key: tuple[str, ...] = ("mcpServers", item.name)
        if item.scope is Scope.LOCAL:
            key = ("projects", str(item.project), "mcpServers", item.name)
        if item.scope is not Scope.USER and not Path(str(item.project)).is_dir():
            raise ValueError(f"the project folder {item.project} is missing")
        edit = FileEdit(
            path=str(item.source.path),
            fmt="json",
            key=key,
            after=ABSENT,
            check="file" if item.scope is Scope.PROJECT else "entry",
        )
        return Step(
            client=CLIENT,
            scope=item.scope,
            name=item.name,
            edit=edit,
            mechanism="client_cli",
            command=["claude", "mcp", "remove", "-s", str(item.scope), item.name],
            cwd=None if item.scope is Scope.USER else item.project,
            restart_note=NEW_SESSION,
            shared_file=item.scope is Scope.PROJECT,
        )

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
                        change_hint=ACCOUNT_HINT,
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
                change_hint=ACCOUNT_HINT,
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
