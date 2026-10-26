"""Codex (CLI and the ChatGPT desktop app share ~/.codex). Research R3, write-matrix.md.

Writes are format-preserving TOML edits of `config.toml` (not `codex mcp add`, which drops
comments). Spike S4: the running app keeps outside edits.
"""

import json
import os
import subprocess  # noqa: S404 - runs the codex command without a shell
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from kitden.changes import toml_edit
from kitden.changes.json_splice import ABSENT, PRESENT
from kitden.clients.base import (
    PLUGIN_REMOVE,
    REMOVE_DIRECT,
    SETUP_NAME,
    SKILL_REMOVE,
    ClientAdapter,
    Reader,
    Scan,
    check_toggle,
    file_source,
    instruction_items,
    is_direct_entry,
    is_own_skill,
    marketplace_source,
    mcp_item,
    plain_source,
    project,
    skill_items,
    toggle_action,
)
from kitden.clients.versions import version_command
from kitden.model import (
    Client,
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
# Lists being asked for in the background, so a second quick scan does not ask again.
_FILLING: set[tuple] = set()
_FILL_LOCK = threading.Lock()
REMOTE_INSTALL_RECORD = ".codex-remote-plugin-install.json"


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _on(value: Any) -> Enabled:
    return Enabled.OFF if value is False else Enabled.ON


def _agents_md(folder: Path) -> list[tuple[Path, str]]:
    """The instruction files Codex looks for in one folder.

    checked 2026-10-22 (learn.chatgpt.com/docs/agent-configuration/agents-md): in CODEX_HOME
    (default ~/.codex) Codex reads AGENTS.override.md if it exists, else AGENTS.md; in a project
    it walks from the project root down to the working folder and reads the same two names in
    each folder (plus names set in `project_doc_fallback_filenames`, not read here). Kitden
    lists both files when both exist. The docs do not say whether an untrusted project's
    AGENTS.md is read (not checked); Kitden lists it either way.
    """
    return [(folder / "AGENTS.override.md", "instructions"), (folder / "AGENTS.md", "instructions")]


class CodexAdapter(ClientAdapter):
    id = CLIENT
    display_name = "Codex"
    config_root = ".codex"
    # Codex also reads ~/.codex/skills; the shared folder is the one Cursor reads too.
    skills_folder = ".agents/skills"
    skill_note = RESTART

    def __init__(
        self,
        home: Path,
        read_version=None,
        codex_home: Path | None = None,
        list_plugins: Callable[[], dict] | None = None,
        quick: bool = False,
        on_slow_answer: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(home, read_version)
        # A quick scan does not wait for `codex plugin list` (15 s on a real Mac, 2026-10-20):
        # it asks in the background, and plugins without a config.toml entry show "Unknown"
        # until `on_slow_answer` says the answer is in and a new scan reads it.
        self.quick = quick
        self.on_slow_answer = on_slow_answer
        env_home = os.environ.get("CODEX_HOME")
        self.codex_home = codex_home or (Path(env_home) if env_home else home / ".codex")
        self._list_plugins = list_plugins or self._run_plugin_list

    def detect(self) -> Client:
        """The base answer; the settings folder is CODEX_HOME, which can sit elsewhere."""
        return replace(super().detect(), config_roots=(str(self.codex_home),))

    def _list_key(self) -> tuple:
        config = self.codex_home / "config.toml"
        stat = config.stat() if config.exists() else None
        return (str(self.codex_home), stat.st_mtime_ns if stat else 0, stat.st_size if stat else 0)

    def _run_plugin_list(self) -> dict:
        """`codex plugin list --json`, the only local view of remote plugins' on/off."""
        command = version_command(CLIENT)
        if command is None:
            return {}
        key = self._list_key()
        if key in _LIST_CACHE:
            return _LIST_CACHE[key]
        if self.quick:
            self.skipped = True
            self._ask_later(command, key)
            return {}
        return self._ask(command, key)

    def _ask(self, command: list[str], key: tuple) -> dict:
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

    def _ask_later(self, command: list[str], key: tuple) -> None:
        """Ask for the list in a thread, once per config.toml; then call `on_slow_answer`."""
        with _FILL_LOCK:
            if key in _FILLING:
                return
            _FILLING.add(key)

        def ask() -> None:
            try:
                self._ask(command, key)
            except (OSError, ValueError, subprocess.SubprocessError):
                _LIST_CACHE[key] = {}  # no answer: the plugins stay "Unknown", no retry loop
            finally:
                with _FILL_LOCK:
                    _FILLING.discard(key)
            if self.on_slow_answer:
                self.on_slow_answer()

        threading.Thread(target=ask, name="codex-plugin-list", daemon=True).start()

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
            return (*toggle_action(item), PLUGIN_REMOVE)
        if is_own_skill(item, CLIENT):
            return (SKILL_REMOVE,)
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

    # checked 2026-10-26 (learn.chatgpt.com/docs/build-skills, "Enable or disable local Codex
    # skills"): a `[[skills.config]]` entry in ~/.codex/config.toml whose `path` is the skill's
    # SKILL.md, with `enabled = false`, turns the skill off without deleting it; restart Codex
    # after the change. The docs name no project file for it.
    def skill_rule_step(self, item: Item) -> Step:
        """Turn one skill off for all projects: its `[[skills.config]]` entry gets
        `enabled = false`, or a new entry is added after the others."""
        config = self.codex_home / "config.toml"
        text = config.read_text() if config.is_file() else ""
        found = toml_edit.get_value(text, ("skills", "config"))
        rules = [] if found is ABSENT else found
        if not isinstance(rules, list) or not all(isinstance(r, dict) for r in rules):
            raise ValueError(
                "Codex's skills settings are not a list of tables; Kitden leaves them."
            )
        path = str(item.source.path)
        mine = [os.path.realpath(str(r.get("path", ""))) == path for r in rules]
        if any(mine):
            after = [{**r, "enabled": False} if m else r for r, m in zip(rules, mine, strict=True)]
        else:
            after = [*rules, {"path": path, "enabled": False}]
        edit = FileEdit(path=str(config), fmt="toml", key=("skills", "config"), after=after)
        return Step(
            client=CLIENT, scope=Scope.USER, name=item.name, edit=edit, restart_note=RESTART
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

    def marketplace_add_step(self, name: str, source: str) -> Step:
        plain_source(source, "Codex")  # the source goes into the arguments
        # Checked 2026-10-19 (0.163): these commands touch only their own tables in config.toml;
        # comments and order stay, and `remove` gives back the exact bytes.
        edit = FileEdit(
            path=str(self.codex_home / "config.toml"),
            fmt="toml",
            key=("marketplaces", name),
            after=PRESENT,
            check="entry",
        )
        return Step(
            client=CLIENT,
            scope=Scope.USER,
            name=name,
            edit=edit,
            mechanism="client_cli",
            command=["codex", "plugin", "marketplace", "add", source, "--json"],
            undo_command=["codex", "plugin", "marketplace", "remove", name],
        )

    # checked 2026-10-22 (learn.chatgpt.com/docs/plugins): Codex installs a plugin for its
    # whole environment; the docs show no per-project install.
    def plugin_install_step(self, plugin_id: str, project: str | None = None) -> Step:
        if project is not None:
            raise ValueError(
                "Codex has no project place for a plugin here; add it for all projects."
            )
        edit = FileEdit(
            path=str(self.codex_home / "config.toml"),
            fmt="toml",
            key=("plugins", plugin_id, "enabled"),
            after=True,
            check="entry",
        )
        return Step(
            client=CLIENT,
            scope=Scope.USER,
            name=plugin_id,
            edit=edit,
            mechanism="client_cli",
            command=["codex", "plugin", "add", plugin_id, "--json"],
            undo_command=["codex", "plugin", "remove", plugin_id],
            restart_note=RESTART,
        )

    # checked 2026-10-22: no codex command on this Mac, and the plugins docs
    # (learn.chatgpt.com/docs/plugins) show only the /plugins browser. `codex plugin remove <id>`
    # is in `codex plugin --help` of 0.163 (research of 2026-10-19); that it deletes the
    # `[plugins."<id>"]` table is assumed, and a different result fails the check and is undone.
    def plugin_remove_step(self, item: Item) -> Step:
        if PLUGIN_REMOVE not in self.item_actions(item):
            raise ValueError(f"{item.name} cannot be removed here")
        edit = FileEdit(
            path=str(item.source.path),
            fmt="toml",
            key=("plugins", item.name),
            after=ABSENT,
            check="entry",
        )
        return Step(
            client=CLIENT,
            scope=item.scope,
            name=item.name,
            edit=edit,
            mechanism="client_cli",
            command=["codex", "plugin", "remove", item.name],
            undo_command=["codex", "plugin", "add", item.name, "--json"],
            restart_note=RESTART,
        )

    def trusts(self, project: str) -> bool:
        """config.toml marks the project as trusted."""
        config = _dict(Reader(CLIENT).toml(self.codex_home / "config.toml"))
        settings = _dict(_dict(config.get("projects")).get(project))
        return settings.get("trust_level") == "trusted"

    def skill_copy_step(self, folder: Path, readers: list[str], project: str | None = None) -> Step:
        if project is not None and not self.trusts(project):
            name = Path(project).name
            raise ValueError(
                f"Codex does not trust {name} yet, so it would not load the skill there."
            )
        return super().skill_copy_step(folder, readers, project)

    def marketplace_roots(self) -> dict[str, Path]:
        """Marketplaces from config.toml, plus the curated one Codex keeps in `.tmp`. A local
        one is its folder; a git one is the copy Codex clones into `.tmp/marketplaces/<name>`
        (seen with Codex 0.163.0, 2026-10-20)."""
        config = _dict(Reader(CLIENT).toml(self.codex_home / "config.toml"))
        roots = {}
        for name, entry in _dict(config.get("marketplaces")).items():
            source = _dict(entry).get("source")
            kind = _dict(entry).get("source_type")
            if kind == "local" and isinstance(source, str) and Path(source).is_dir():
                roots[name] = Path(source)
            elif kind == "git" and (self.codex_home / ".tmp/marketplaces" / name).is_dir():
                roots[name] = self.codex_home / ".tmp/marketplaces" / name
        curated = self.codex_home / ".tmp/plugins"
        listed = _dict(Reader(CLIENT).json(curated / ".agents/plugins/marketplace.json"))
        if isinstance(listed.get("name"), str):
            roots.setdefault(listed["name"], curated)
        return roots

    def gateway_step(self, gateway: Gateway, name: str) -> Step:
        value = {"url": gateway.url}
        if gateway.auth is GatewayAuth.ENV_KEY and gateway.key_env_var:
            value["bearer_token_env_var"] = gateway.key_env_var
        login = f"Run: codex mcp login {name}" if gateway.auth is GatewayAuth.OAUTH else None
        return self._add_entry(name, value, login)

    def setup_server_step(self, command: str, args: list[str]) -> Step:
        return self._add_entry(SETUP_NAME, {"command": command, "args": args})

    def add_server_step(self, name: str, entry: dict) -> Step:
        return self._add_entry(name, entry)

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
            enabled = _on(_dict(entry).get("enabled"))
            scan.items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=plugin_id,
                    source=file_source(config_path, CLIENT, f"plugins.{plugin_id}"),
                    scope=Scope.USER,
                    enabled=enabled,
                )
            )
            scan.items += self._plugin_servers(read, self._plugin_folder(plugin_id), enabled)
        scan.items += self._cached_plugins(set(configured))

        for name, entry in _dict(config.get("marketplaces")).items():
            where = marketplace_source(_dict(entry))
            scan.items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.MARKETPLACE,
                    name=name,
                    source=file_source(config_path, CLIENT, f"marketplaces.{name}"),
                    scope=Scope.USER,
                    summary=(("source", where),) if where else (),
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

        scan.items += instruction_items(CLIENT, _agents_md(self.codex_home), Scope.USER, CLIENT)

        for path, settings in _dict(config.get("projects")).items():
            scan.projects.append(project(path, CLIENT))
            trusted = _dict(settings).get("trust_level") == "trusted"
            scan.items += self._project(read, Path(path), trusted)
            # The user's file lives in codex_home, so a home-folder project's files are its own.
            files = _agents_md(Path(path))
            scan.items += instruction_items(CLIENT, files, Scope.PROJECT, CLIENT, project=path)

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
        # checked 2026-10-22 (learn.chatgpt.com/docs/build-skills): Codex reads `.agents/skills`
        # from the folder it starts in up to the repository root. The docs do not say whether an
        # untrusted project's skills load; Kitden counts them only in a trusted project, as it
        # does the project's config.toml.
        if trusted:
            items += skill_items(
                CLIENT, root / ".agents/skills", Scope.PROJECT, CLIENT, project=str(root)
            )
        return items

    def _plugin_folder(self, plugin_id: str) -> Path:
        name, _, marketplace = plugin_id.partition("@")
        return self.codex_home / "plugins/cache" / marketplace / name

    def plugin_folders(self) -> dict[str, Path]:
        """Plugin id -> its folder in Codex's plugin cache.

        The cache is `plugins/cache/<marketplace>/<plugin>/`, and the files may sit one version
        folder down (the newest one is used). Hidden folders are skipped.
        """

        def folders(parent: Path) -> list[Path]:
            found = parent.iterdir() if parent.is_dir() else []
            return sorted(p for p in found if p.is_dir() and not p.name.startswith("."))

        out: dict[str, Path] = {}
        for marketplace in folders(self.codex_home / "plugins/cache"):
            for plugin in folders(marketplace):
                versions = folders(plugin)
                has_files = (plugin / ".codex-plugin").is_dir() or not versions
                newest = plugin if has_files else max(versions, key=lambda v: v.stat().st_mtime)
                out[f"{plugin.name}@{marketplace.name}"] = newest
        return out

    def _plugin_servers(self, read: Reader, folder: Path, enabled: Enabled) -> list[Item]:
        """MCP servers a plugin bundles: `mcp.json` (the portable format) or `.mcp.json`, in the
        plugin folder or in one of its version folders (feature 003, research R8)."""
        items: list[Item] = []
        if not folder.is_dir():
            return items
        for place in [folder, *sorted(p for p in folder.iterdir() if p.is_dir())]:
            names = ("mcp.json", ".mcp.json")
            mcp_path = next((place / n for n in names if (place / n).is_file()), None)
            if mcp_path is None:
                continue
            for name, entry in _dict(_dict(read.json(mcp_path)).get("mcpServers")).items():
                source = file_source(mcp_path, CLIENT, f"mcpServers.{name}", kind=SourceKind.PLUGIN)
                items.append(mcp_item(CLIENT, name, entry, source, Scope.PLUGIN, enabled=enabled))
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
