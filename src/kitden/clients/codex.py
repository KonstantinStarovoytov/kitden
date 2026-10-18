"""Codex (CLI and the ChatGPT desktop app share ~/.codex). Research R3, write-matrix.md.

Writes are format-preserving TOML edits of `config.toml` (not `codex mcp add`, which drops
comments). Spike S4: the running app keeps outside edits.
"""

import json
import os
import subprocess  # noqa: S404 - runs the codex command without a shell
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from kitden.changes.json_splice import ABSENT
from kitden.clients.base import (
    REMOVE_DIRECT,
    SETUP_NAME,
    ClientAdapter,
    Reader,
    Scan,
    check_toggle,
    file_source,
    is_direct_entry,
    mcp_item,
    project,
    skill_items,
    toggle_action,
)
from kitden.clients.versions import version_command
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

CLIENT = "codex"
RESTART = "Restart Codex (the app and any open CLI sessions) for this to take effect."
REMOTE_HINT = "On/off is stored in your ChatGPT account. Change it in Codex: Plugins."
# Built-in marketplaces live in folders Codex manages itself; other clients cannot add them.
BUILT_IN_FOLDERS = (".codex/.tmp", ".cache/codex-runtimes")
LIST_TIMEOUT_SECONDS = 15
# `codex plugin list --json` results, reused until config.toml changes (the app rewrites it on
# every plugin toggle, spike S4).
_LIST_CACHE: dict[tuple, dict] = {}
REMOTE_INSTALL_RECORD = ".codex-remote-plugin-install.json"


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _on(value: Any) -> Enabled:
    return Enabled.OFF if value is False else Enabled.ON


class CodexAdapter(ClientAdapter):
    id = CLIENT
    display_name = "Codex"
    config_root = ".codex"

    def __init__(
        self,
        home: Path,
        read_version=None,
        codex_home: Path | None = None,
        list_plugins: Callable[[], dict] | None = None,
    ) -> None:
        super().__init__(home, read_version)
        env_home = os.environ.get("CODEX_HOME")
        self.codex_home = codex_home or (Path(env_home) if env_home else home / ".codex")
        self._list_plugins = list_plugins or self._run_plugin_list

    def _run_plugin_list(self) -> dict:
        """`codex plugin list --json`, the only local view of remote plugins' on/off."""
        command = version_command(CLIENT)
        if command is None:
            return {}
        config = self.codex_home / "config.toml"
        stat = config.stat() if config.exists() else None
        key = (str(self.codex_home), stat.st_mtime_ns if stat else 0, stat.st_size if stat else 0)
        if key not in _LIST_CACHE:
            env = {**os.environ, "HOME": str(self.home), "CODEX_HOME": str(self.codex_home)}
            done = subprocess.run(  # noqa: S603 - fixed client command, no shell
                [command[0], "plugin", "list", "--json"],
                env=env,
                capture_output=True,
                text=True,
                timeout=LIST_TIMEOUT_SECONDS,
                check=False,
            )
            _LIST_CACHE[key] = json.loads(done.stdout) if done.returncode == 0 else {}
        return _LIST_CACHE[key]

    def _plugin_states(self) -> dict[str, bool]:
        if self._read_version() is None:
            return {}
        try:
            listing = self._list_plugins()
        except (OSError, ValueError, subprocess.SubprocessError):
            return {}
        installed = _dict(listing).get("installed")
        plugins = installed if isinstance(installed, list) else []
        return {
            p["pluginId"]: bool(p.get("enabled"))
            for p in plugins
            if isinstance(p, dict) and isinstance(p.get("pluginId"), str)
        }

    def item_actions(self, item: Item) -> tuple[str, ...]:
        if is_direct_entry(item, CLIENT, {Scope.USER, Scope.PROJECT}):
            return (REMOVE_DIRECT,)
        if (
            item.kind is ItemKind.PLUGIN
            and item.client == CLIENT
            and item.source.kind is SourceKind.FILE
            and item.source.read_status is ReadStatus.OK
        ):
            return toggle_action(item)
        return ()

    def plugin_step(self, item: Item, enable: bool) -> Step:
        check_toggle(self, item, enable)
        edit = FileEdit(
            path=str(item.source.path),
            fmt="toml",
            key=("plugins", item.name, "enabled"),
            after=enable,
        )
        return Step(
            client=CLIENT, scope=item.scope, name=item.name, edit=edit, restart_note=RESTART
        )

    def marketplace_sources(self) -> dict[str, str | None]:
        config = _dict(Reader(CLIENT).toml(self.codex_home / "config.toml"))
        sources: dict[str, str | None] = {}
        for name, entry in _dict(config.get("marketplaces")).items():
            source = _dict(entry).get("source")
            built_in = name.startswith("openai-") or (
                isinstance(source, str) and any(f in source for f in BUILT_IN_FOLDERS)
            )
            sources[name] = None if built_in or not isinstance(source, str) else source
        return sources

    def gateway_step(self, gateway: Gateway, name: str) -> Step:
        value = {"url": gateway.url}
        if gateway.auth is GatewayAuth.ENV_KEY and gateway.key_env_var:
            value["bearer_token_env_var"] = gateway.key_env_var
        login = f"Run: codex mcp login {name}" if gateway.auth is GatewayAuth.OAUTH else None
        return self._add_entry(name, value, login)

    def setup_server_step(self, command: str, args: list[str]) -> Step:
        return self._add_entry(SETUP_NAME, {"command": command, "args": args})

    def _add_entry(self, name: str, value: dict[str, Any], login: str | None = None) -> Step:
        edit = FileEdit(
            path=str(self.codex_home / "config.toml"),
            fmt="toml",
            key=("mcp_servers", name),
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
            fmt="toml",
            key=("mcp_servers", item.name),
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
        config_path = self.codex_home / "config.toml"
        config = _dict(read.toml(config_path))

        for name, entry in _dict(config.get("mcp_servers")).items():
            scan.items.append(
                mcp_item(
                    CLIENT,
                    name,
                    entry,
                    file_source(config_path, CLIENT, f"mcp_servers.{name}"),
                    Scope.USER,
                    enabled=_on(_dict(entry).get("enabled")),
                )
            )

        configured = _dict(config.get("plugins"))
        for plugin_id, entry in configured.items():
            scan.items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=plugin_id,
                    source=file_source(config_path, CLIENT, f"plugins.{plugin_id}"),
                    scope=Scope.USER,
                    enabled=_on(_dict(entry).get("enabled")),
                )
            )
        scan.items += self._cached_plugins(set(configured))

        for name in _dict(config.get("marketplaces")):
            scan.items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.MARKETPLACE,
                    name=name,
                    source=file_source(config_path, CLIENT, f"marketplaces.{name}"),
                    scope=Scope.USER,
                )
            )

        disabled_skills = (
            {
                os.path.realpath(_dict(rule).get("path", ""))
                for rule in config.get("skills", {}).get("config", [])
                if isinstance(rule, dict) and rule.get("enabled") is False
            }
            if isinstance(config.get("skills"), dict)
            else set()
        )
        for folder in (self.home / ".agents/skills", self.codex_home / "skills"):
            for item in skill_items(CLIENT, folder, Scope.USER, CLIENT):
                off = item.source.path in disabled_skills
                scan.items.append(replace(item, enabled=Enabled.OFF if off else Enabled.ON))

        for path, settings in _dict(config.get("projects")).items():
            scan.projects.append(project(path, CLIENT))
            trusted = _dict(settings).get("trust_level") == "trusted"
            scan.items += self._project(read, Path(path), trusted)

        scan.problems = read.problems
        return scan

    def _project(self, read: Reader, root: Path, trusted: bool) -> list[Item]:
        items = []
        layer_path = root / ".codex/config.toml"
        layer = _dict(read.toml(layer_path))
        for name, entry in _dict(layer.get("mcp_servers")).items():
            state = _on(_dict(entry).get("enabled")) if trusted else Enabled.OFF
            items.append(
                mcp_item(
                    CLIENT,
                    name,
                    entry,
                    file_source(layer_path, CLIENT, f"mcp_servers.{name}"),
                    Scope.PROJECT,
                    project=str(root),
                    enabled=state,
                )
            )
        if trusted:
            items += skill_items(
                CLIENT, root / ".agents/skills", Scope.PROJECT, CLIENT, project=str(root)
            )
        return items

    def _cached_plugins(self, configured: set[str]) -> list[Item]:
        """Plugins in the local cache without a config entry: their state is not local.

        A remote plugin (with an install record) keeps its on/off in the ChatGPT account
        (spike S4).
        """
        cache = self.codex_home / "plugins/cache"
        folders = [
            (f"{plugin.name}@{marketplace.name}", plugin)
            for marketplace in (sorted(cache.iterdir()) if cache.is_dir() else [])
            for plugin in (sorted(marketplace.iterdir()) if marketplace.is_dir() else [])
            if plugin.is_dir() and not plugin.name.startswith(".")
        ]
        folders = [(plugin_id, path) for plugin_id, path in folders if plugin_id not in configured]
        states = self._plugin_states() if folders else {}
        items = []
        for plugin_id, plugin in folders:
            remote = (plugin / REMOTE_INSTALL_RECORD).is_file()
            known = plugin_id in states
            source = Source(
                kind=SourceKind.PLUGIN,
                path=str(plugin),
                owner_client=CLIENT,
                read_status=ReadStatus.OK if known else ReadStatus.UNKNOWN,
                unknown_reason=None
                if known
                else (UnknownReason.STORED_IN_ACCOUNT if remote else UnknownReason.NOT_DOCUMENTED),
            )
            items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=plugin_id,
                    source=source,
                    scope=Scope.USER,
                    enabled=_on(states[plugin_id]) if known else Enabled.UNKNOWN,
                    change_hint=REMOTE_HINT if remote else None,
                )
            )
        return items
