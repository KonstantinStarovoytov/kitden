"""Codex (CLI and the ChatGPT desktop app share ~/.codex). Read-only. Research R3."""

import os
from dataclasses import replace
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

CLIENT = "codex"


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _on(value: Any) -> Enabled:
    return Enabled.OFF if value is False else Enabled.ON


class CodexAdapter(ClientAdapter):
    id = CLIENT
    display_name = "Codex"
    config_root = ".codex"

    def __init__(self, home: Path, read_version=None, codex_home: Path | None = None) -> None:
        super().__init__(home, read_version)
        env_home = os.environ.get("CODEX_HOME")
        self.codex_home = codex_home or (Path(env_home) if env_home else home / ".codex")

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
        """Plugins in the local cache without a config entry: their state is not local."""
        cache = self.codex_home / "plugins/cache"
        items = []
        for marketplace in sorted(cache.iterdir()) if cache.is_dir() else []:
            for plugin in sorted(marketplace.iterdir()) if marketplace.is_dir() else []:
                plugin_id = f"{plugin.name}@{marketplace.name}"
                if plugin.name.startswith(".") or not plugin.is_dir() or plugin_id in configured:
                    continue
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
                        name=plugin_id,
                        source=source,
                        scope=Scope.USER,
                        enabled=Enabled.UNKNOWN,
                    )
                )
        return items
