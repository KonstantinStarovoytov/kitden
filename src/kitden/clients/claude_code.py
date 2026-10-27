"""Claude Code (CLI and the Claude Desktop Code tab). Research R3, write-matrix.md.

Writes go through `claude mcp add-json` and `claude mcp remove` (FR-021). An entry that holds a
secret is written to `~/.claude.json` (where Claude Code keeps user-scope servers) instead:
`add-json` takes the entry as an argument, and `ps` shows a process's arguments. Claude Code
rewrites `~/.claude.json` during normal use, so changes to that file compare only the edited
entry.
"""

import json
import os
from dataclasses import replace
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
    expand,
    file_source,
    instruction_items,
    is_direct_entry,
    is_home,
    is_own_skill,
    marketplace_source,
    mcp_item,
    plain_source,
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
from kitden.redact import redact
from kitden.views.words import NO_CLAUDE_FOLDER

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


def _instruction_files(folder: Path) -> list:
    """Instruction files, rules, commands and agents in a `.claude` folder.

    checked 2026-10-22 (code.claude.com/docs/en/memory, /en/claude-directory): Claude Code reads
    `~/.claude/CLAUDE.md`, `<project>/.claude/CLAUDE.md` and `rules/*.md` in both folders,
    sub-folders too. checked 2026-10-22 (/en/slash-commands, /en/claude-directory):
    `commands/*.md` in both folders; a file in a sub-folder is named `<folder>:<name>`.
    checked 2026-10-22 (/en/sub-agents): `agents/*.md` in both folders, sub-folders too.
    """
    return [
        (folder / "CLAUDE.md", "instructions"),
        *expand(folder / "rules", "instructions"),
        *expand(folder / "commands", "command"),
        *expand(folder / "agents", "agent"),
    ]


def _on(value: bool | None) -> Enabled:
    return Enabled.UNKNOWN if value is None else (Enabled.ON if value else Enabled.OFF)


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


# checked 2026-10-26 (code.claude.com/docs/en/skills, "Override skill visibility from settings"):
# `skillOverrides` maps a skill name to "on", "name-only", "user-invocable-only" or "off"; a
# skill that is not listed is "on". Only "off" turns a skill off. Plugin skills are not affected.
# The docs do not say how `skillOverrides` merges across settings files (their precedence list,
# checked 2026-10-26 at /en/settings, is project local > shared project > user, for a key as a
# whole). Kitden merges it key by key, the most specific file winning: not confirmed by the docs.
SKILL_STATES = ("on", "name-only", "user-invocable-only", "off")


def _skill_rules(layers: list[tuple[Scope, dict]]) -> dict[str, tuple[str, Scope]]:
    """Skill name -> (state, file scope). `layers` run from the least to the most specific file.
    Values the docs do not list are ignored."""
    rules: dict[str, tuple[str, Scope]] = {}
    for scope, settings in layers:
        for name, state in _dict(settings.get("skillOverrides")).items():
            if state in SKILL_STATES:
                rules[name] = (state, scope)
    return rules


def _apply_rules(
    items: list[Item], rules: dict[str, tuple[str, Scope]], known: bool = True
) -> list[Item]:
    """Mark the skills a rule turns off. A rule that keeps a skill on only records its file.
    When a settings file could not be read (`known` is False) the skills' state is unknown."""
    ruled = []
    for item in items:
        rule = rules.get(item.name)
        if item.kind is not ItemKind.SKILL:
            pass
        elif not known:
            item = replace(item, enabled=Enabled.UNKNOWN)
        elif rule:
            state, scope = rule
            item = replace(
                item, enabled=Enabled.OFF if state == "off" else Enabled.ON, state_scope=scope
            )
        ruled.append(item)
    return ruled


def _project_rules(
    items: list[Item], by_project: dict[str, dict[str, tuple[str, Scope]]]
) -> list[Item]:
    """Give each user skill the rules that a project's own settings hold for it."""
    ruled = []
    for item in items:
        found = []
        for path, rules in by_project.items():
            rule = rules.get(item.name)
            if item.kind is ItemKind.SKILL and rule and rule[1] is not Scope.USER:
                found.append((path, Enabled.OFF if rule[0] == "off" else Enabled.ON, rule[1]))
        ruled.append(replace(item, project_rules=tuple(found)) if found else item)
    return ruled


# checked 2026-10-27 (code.claude.com/docs/en/settings, "Where Claude Code keeps the local file
# in a git repository"): since v2.1.211, Claude Code started in a subfolder of a git repository
# reads and writes `.claude/settings.local.json` at the repository root. It still reads a file an
# earlier version left in the starting folder; where both set a key, the root's value applies.
# The file stays in the starting folder outside a repository, when the root is the home folder,
# or when the root, its `.git` or its `.claude` is not the user's own.
# Known gaps: a worktree uses its main checkout's root (Kitden does not follow a worktree's
# `.git` file); the docs keep the file in the starting folder on Windows (not checked here); a
# home folder reached through a link is compared as written; and Kitden's permission checks
# (changes/actions.py) still read only the project's own local file.
def git_root(folder: Path, home: Path) -> Path | None:
    """The repository root above `folder` whose local settings Claude Code uses there, or None:
    the nearest folder with a `.git` folder, never the home folder or above it (the walk stops
    there; a folder outside home walks up to `/`)."""
    for place in (folder, *folder.parents):
        if place == home:
            return None
        git = place / ".git"
        if git.exists():
            mine = [place, git] + ([place / ".claude"] if (place / ".claude").exists() else [])
            owned = git.is_dir() and all(_owned(p) for p in mine)
            return place if owned and place != folder else None
    return None


def _owned(path: Path) -> bool:
    try:
        return path.stat().st_uid == os.getuid()
    except OSError:
        return False


def local_files(project: Path, home: Path) -> list[Path]:
    """The local settings files Claude Code reads in `project`, the winning one last."""
    own = project / ".claude/settings.local.json"
    root = git_root(project, home)
    return [own, root / ".claude/settings.local.json"] if root else [own]


def rule_file(project: Path, home: Path) -> Path | None:
    """The local file a one-project rule goes to: the root's, which Claude Code reads first, when
    its `.claude` folder is there, else the project's own when its folder is there; None when
    neither is (Kitden makes no folder)."""
    return next((f for f in reversed(local_files(project, home)) if f.parent.is_dir()), None)


def _holds(path: Path, key: tuple[str, str]) -> bool:
    """The settings file has `key`; a file Kitden cannot read may have it."""
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return True
    return isinstance(data, dict) and key[1] in _dict(data.get(key[0]))


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

    def _rule_files(self, project: str | None, key: tuple[str, str], off: bool) -> list[Path]:
        """Where a rule goes: the user settings, or one project's `rule_file`. A project's rule
        taken out goes from each local file that holds it."""
        if project is None:
            return [self.home / ".claude/settings.json"]
        holding = [f for f in local_files(Path(project), self.home) if _holds(f, key)]
        if not off and holding:
            return holding
        # A rule set goes to `rule_file`. So does a removal no local file holds (the key is
        # already gone): its step then finds nothing to take out, and the engine says so
        # (NothingToChangeError) instead of writing a file.
        target = rule_file(Path(project), self.home)
        if target is None:
            raise ValueError(NO_CLAUDE_FOLDER.format(folder=Path(project).name))
        return [target]

    def _rule_steps(
        self, key: tuple[str, str], project: str | None, after: Any, note: str
    ) -> list[Step]:
        """One step per file. `cwd` names the project the rule is for (the file may be its
        repository's); no command runs."""
        scope = Scope.USER if project is None else Scope.LOCAL
        return [
            Step(
                client=CLIENT,
                scope=scope,
                name=key[1],
                edit=FileEdit(path=str(path), fmt="json", key=key, after=after),
                cwd=project,
                restart_note=note,
            )
            for path in self._rule_files(project, key, after is not ABSENT)
        ]

    # checked 2026-10-26 (code.claude.com/docs/en/settings-reference, `skillOverrides`): any
    # settings file may hold it, and "off" hides the skill from Claude and from `/`. The
    # `/skills` menu saves it to `.claude/settings.local.json`. The docs still do not say whether
    # the object merges key by key across files (also /en/settings and /en/skills, same day).
    def skill_rule_steps(self, name: str, project: str | None, off: bool) -> list[Step]:
        """`skillOverrides.<name>` set to "off", in the user settings or in one project's local
        settings. With `off` False the project's key goes, so the shared rule applies there."""
        return self._rule_steps(
            ("skillOverrides", name), project, "off" if off else ABSENT, NEW_SESSION
        )

    # checked 2026-10-26 (code.claude.com/docs/en/settings-reference, `enabledPlugins`): "To opt
    # out of a project-enabled plugin on your machine, set it to false in
    # .claude/settings.local.json"; plugins/loading says the files merge key by key, local first.
    def plugin_rule_steps(self, plugin_id: str, project: str, off: bool) -> list[Step]:
        """`enabledPlugins.<id>` set to false in one project's local settings; with `off` False
        the key goes, so the project follows its shared settings again."""
        return self._rule_steps(
            ("enabledPlugins", plugin_id), project, False if off else ABSENT, RELOAD
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
        plain_source(source, "Claude Code")  # the source goes into the arguments
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

    def plugin_install_step(self, plugin_id: str, project: str | None = None) -> Step:
        # No -y: a plugin that installs by running a command stops here and says so.
        root, scope = self.home, Scope.USER
        if project is not None:
            # checked 2026-10-22 (`claude plugin install --help`, 2.1.283, and
            # code.claude.com/docs/en/plugins/install): `-s project`, run in the project, puts
            # the plugin in `enabledPlugins` of <project>/.claude/settings.json, the file the
            # project shares; `uninstall -s project` takes it out there.
            if not Path(project).is_dir():
                raise ValueError(f"the project folder {project} is missing")
            root, scope = Path(project), Scope.PROJECT
        edit = FileEdit(
            path=str(root / ".claude/settings.json"),
            fmt="json",
            key=("enabledPlugins", plugin_id),
            after=True,
            check="entry",
        )
        return Step(
            client=CLIENT,
            scope=scope,
            name=plugin_id,
            edit=edit,
            mechanism="client_cli",
            command=["claude", "plugin", "install", plugin_id, "-s", str(scope), "--json"],
            undo_command=["claude", "plugin", "uninstall", plugin_id, "-s", str(scope), "--json"],
            cwd=project,
            restart_note=RELOAD,
            shared_file=project is not None,
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

    def plugin_folders(self) -> dict[str, Path]:
        """Plugin id -> its install folder, the first one in `installed_plugins.json` on disk."""
        record = _dict(Reader(CLIENT).json(self.home / ".claude/plugins/installed_plugins.json"))
        out: dict[str, Path] = {}
        for plugin_id, installs in _dict(record.get("plugins")).items():
            for install in installs if isinstance(installs, list) else []:
                where = _dict(install).get("installPath")
                if isinstance(where, str) and Path(where).is_dir():
                    out[plugin_id] = Path(where)
                    break
        return out

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
        """A user-scope MCP entry, added with `claude mcp add-json` (FR-021, FR-024), or written
        directly when it holds a secret."""
        edit = FileEdit(
            path=str(self.home / ".claude.json"),
            fmt="json",
            key=("mcpServers", name),
            after=value,
            check="entry",
        )
        # checked 2026-10-22 (code.claude.com/docs/en/mcp): the docs show `claude mcp add-json
        # <name> '<json>'` with the JSON as an argument and no stdin or file option, and say
        # Claude Code keeps user-scope servers in ~/.claude.json. They do not describe editing
        # that file by hand. A secret in the arguments is visible to `ps` while the command
        # runs, so Kitden writes an entry with one into the file itself, with a backup.
        if redact(value)[1]:
            return Step(
                client=CLIENT,
                scope=Scope.USER,
                name=name,
                edit=edit,
                restart_note=NEW_SESSION,
                login_note=login,
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
        project_skill_rules: dict[str, dict[str, tuple[str, Scope]]] = {}
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
            found, rules = self._project_files(read, Path(path), data, settings, settings_known)
            scan.items += found
            if rules is not None:
                project_skill_rules[path] = rules

        # Plugins: user settings decide on/off; project settings may override.
        enabled = _dict(settings.get("enabledPlugins"))
        installed = _dict(
            _dict(read.json(self.home / ".claude/plugins/installed_plugins.json")).get("plugins")
        )
        for plugin_id, installs in installed.items():
            state_on = _on(enabled.get(plugin_id)) if settings_known else Enabled.UNKNOWN
            if settings_known and plugin_id not in enabled:
                state_on = Enabled.ON  # installed plugins are on unless turned off
            ruled = settings_known and plugin_id in enabled
            source = file_source(settings_path, CLIENT, f"enabledPlugins.{plugin_id}")
            scan.items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=plugin_id,
                    source=source,
                    scope=Scope.USER,
                    enabled=state_on,
                    state_scope=Scope.USER if ruled else None,
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
        user_skills = _apply_rules(
            skill_items(CLIENT, self.home / ".claude/skills", Scope.USER, CLIENT),
            _skill_rules([(Scope.USER, settings)]),
            settings_known,
        )
        scan.items += _project_rules(user_skills, project_skill_rules)
        scan.items += instruction_items(
            CLIENT, _instruction_files(self.home / ".claude"), Scope.USER, CLIENT
        )
        scan.items += self._hooks(settings, settings_path, Scope.USER)
        marketplaces_path = self.home / ".claude/plugins/known_marketplaces.json"
        for name, entry in _dict(read.json(marketplaces_path)).items():
            where = marketplace_source(_dict(entry).get("source"))
            scan.items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.MARKETPLACE,
                    name=name,
                    source=file_source(marketplaces_path, CLIENT, name),
                    scope=Scope.USER,
                    summary=(("source", where),) if where else (),
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

    def _project_files(
        self, read: Reader, root: Path, data: dict, user_settings: dict, user_known: bool
    ) -> tuple[list[Item], dict[str, tuple[str, Scope]] | None]:
        """The project's items, and its skill rules (None when a settings file was unreadable)."""
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
        # The local files, the winning one last; each plugin key comes from the last that has it.
        locals_ = [(path, _dict(read.json(path))) for path in local_files(root, self.home)]
        # checked 2026-10-26 (code.claude.com/docs/en/plugins/loading, "Find where a plugin is
        # enabled"): `enabledPlugins` is read from user, project (`.claude/settings.json`) and
        # local (`.claude/settings.local.json`) files; the highest source that names a plugin
        # wins, local over project over user. Each file gives its own item here, and the
        # effective view picks the winner by scope rank.
        plugins = {
            (scope, plugin_id): (file_path, value)
            for file_path, file_settings, scope in (
                (settings_path, settings, Scope.PROJECT),
                *((p, data, Scope.LOCAL) for p, data in locals_),
            )
            for plugin_id, value in _dict(file_settings.get("enabledPlugins")).items()
        }
        for (scope, plugin_id), (file_path, value) in plugins.items():
            items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=plugin_id,
                    source=file_source(file_path, CLIENT, f"enabledPlugins.{plugin_id}"),
                    scope=scope,
                    project=path,
                    enabled=_on(value),
                    state_scope=scope,
                )
            )
        items += self._hooks(settings, settings_path, Scope.PROJECT, project=path)
        rules = _skill_rules(
            [
                (Scope.USER, user_settings),
                (Scope.PROJECT, settings),
                *((Scope.LOCAL, data) for _, data in locals_),
            ]
        )
        read_files = [settings_path, *(p for p, _ in locals_)]
        known = user_known and not any(read.failed(p) for p in read_files)
        items += _apply_rules(
            skill_items(CLIENT, root / ".claude/skills", Scope.PROJECT, CLIENT, project=path),
            rules,
            known,
        )
        # checked 2026-10-22 (code.claude.com/docs/en/memory): a project's CLAUDE.md and
        # CLAUDE.local.md at its root, besides the files in its `.claude` folder. When the
        # project is the home folder, its `.claude` files are the user's own and are skipped.
        files = [(root / "CLAUDE.md", "instructions"), (root / "CLAUDE.local.md", "instructions")]
        if not is_home(root, self.home):
            files += _instruction_files(root / ".claude")
        items += instruction_items(CLIENT, files, Scope.PROJECT, CLIENT, project=path)
        return items, (rules if known else None)

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
