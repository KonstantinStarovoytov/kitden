"""Claude Code (CLI and the Claude Desktop Code tab). Research R3, write-matrix.md.

Writes go through `claude mcp add-json` and `claude mcp remove` (FR-021). An entry that holds a
secret is written to `~/.claude.json` (where Claude Code keeps user-scope servers) instead:
`add-json` takes the entry as an argument, and `ps` shows a process's arguments. Claude Code
rewrites `~/.claude.json` during normal use, so changes to that file compare only the edited
entry.
"""

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from kitden.changes.json_splice import ABSENT, PRESENT
from kitden.clients.base import (
    PLUGIN_DISABLE,
    PLUGIN_REMOVE,
    REMOVE_DIRECT,
    SETUP_NAME,
    SKILL_REMOVE,
    ClientAdapter,
    Reader,
    Scan,
    check_toggle,
    expand,
    file_source,
    hook_items,
    instruction_items,
    is_direct_entry,
    is_home,
    is_own_skill,
    marketplace_source,
    mcp_item,
    mcp_items,
    need_folder,
    plain_source,
    project,
    skill_items,
    toggle_action,
)
from kitden.clients.claude_folder import ClaudeFolder, claude_folder
from kitden.clients.versions import highest_version, is_supported
from kitden.local_gateway.settings import as_dict
from kitden.model import (
    Client,
    ClientStatus,
    Enabled,
    FileEdit,
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
from kitden.system import claude_desktop_dir
from kitden.views.words import NO_CLAUDE_FOLDER

CLIENT = "claude_code"
WRITABLE_SCOPES = {Scope.USER, Scope.LOCAL, Scope.PROJECT}
NEW_SESSION = "Start a new Claude Code session (or a new Code tab chat) for this to take effect."
# checked 2026-11-23 (/en/settings-reference): a top-level key of any settings file, the share
# of the context window the skill list may use (default 0.01).
LIMIT_KEY = "skillListingBudgetFraction"
RELOAD = "Run /reload-plugins in Claude Code, or start a new session, for this to take effect."
ACCOUNT_HINT = "Stored in your Claude account. Change it in the Claude app or on claude.ai."
DESKTOP = "claude_desktop_code_tab"
# In kitden.system's Claude Desktop folder. On Linux (a beta for Ubuntu 22.04+ and Debian 12+,
# support.claude.com, checked 2026-11-03) the folder is assumed to be ~/.config/Claude, like
# other Electron apps; to confirm on a real install before release.
DESKTOP_CONFIG = "claude_desktop_config.json"
DESKTOP_BUNDLED = "claude-code"
# Plugins that come from these places have no install to remove (plugins/loading docs).
NOT_INSTALLED = ("@synced", "@inline", "@skills-dir")
PROJECT_NOT_INSTALLED = (
    "Turned on by this project, but not installed here, so Claude Code may not load it."
)


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


def _names(value: Any) -> set[str]:
    """The names in a settings list; a value of another shape holds none."""
    return {v for v in value if isinstance(v, str)} if isinstance(value, list) else set()


def _on(value: bool | None) -> Enabled:
    return Enabled.UNKNOWN if value is None else (Enabled.ON if value else Enabled.OFF)


# checked 2026-11-25 (code.claude.com/docs/en/plugins/loading, "Enabled in project settings but
# not installed"): a plugin turned on only in a project's `.claude/settings.json` does not load at
# start until it is installed. Exceptions Kitden cannot see (a seed folder, a relative-path plugin
# in a marketplace added from a local path) are why the state is "unknown", not "off".
# The record's `scope` and `projectPath` keys were seen in a sandbox home (2026-11-25, Claude Code
# 2.1.311, `plugin install -s project` and `-s local`); the docs do not show them.
# checked 2026-11-25 (code.claude.com/docs/en/worktrees, "What worktrees share with the main
# checkout"): a project install made in the main checkout also loads in its worktrees.
def _install_counts(installs: Any, project_path: str) -> bool:
    """The plugin has an install record that serves this project: any record that is not a
    project or local install, or one for this project's folder or its main checkout."""
    serves = [os.path.realpath(p) for p in (project_path, main_checkout(Path(project_path))) if p]
    for record in installs if isinstance(installs, list) else []:
        record = as_dict(record)
        where = record.get("projectPath")
        if record.get("scope") not in ("project", "local") or not isinstance(where, str):
            return True
        if os.path.realpath(where) in serves:
            return True
    return False


# checked 2026-11-15 (code.claude.com/docs/en/mcp; /en/settings-reference gives the three keys
# the scope "Any file"; and Claude Code 2.1.311 run in a sandbox home): `enabledMcpjsonServers`,
# `enableAllProjectMcpServers` and `disabledMcpjsonServers` are settings keys. A name in
# `disabledMcpjsonServers` of any file rejects the server. In a trusted folder the user, project
# and local files approve it; in a folder not trusted only the user file does. Earlier versions
# kept the keys in `~/.claude.json` under `projects.<path>`; Claude Code moves them to the local
# file when it next starts there, so Kitden reads them there too. Not read: managed settings,
# `--settings`, and whether git tracks the local file (a tracked file also waits for trust).
# checked 2026-11-25 (code.claude.com/docs/en/permissions, "When your local settings file needs
# trust"): in the home folder the local file's approvals apply without trust; `scan` counts the
# home folder as trusted, and a folder whose `.claude` is CLAUDE_CONFIG_DIR, as the docs do.
def _approval(
    name: str, user: dict, project_files: list[dict], trusted: bool, unread: bool
) -> Enabled:
    """A project `.mcp.json` server's approval: on, off (rejected), or unknown (pending)."""
    files = [user, *project_files]
    if any(name in _names(f.get("disabledMcpjsonServers")) for f in files):
        return Enabled.OFF
    if unread:
        return Enabled.UNKNOWN
    approving = files if trusted else [user]
    if any(
        f.get("enableAllProjectMcpServers") is True
        or name in _names(f.get("enabledMcpjsonServers"))
        for f in approving
    ):
        return Enabled.ON
    return Enabled.UNKNOWN


def is_trusted(projects: dict, folder: Path, home: Path) -> bool:
    """Claude Code trusts the folder: its entry in `~/.claude.json` has
    `hasTrustDialogAccepted`, or, in a git repository, a folder above it up to the root has.

    checked 2026-11-15 (Claude Code 2.1.311 in a sandbox home): outside a repository a parent
    folder's trust did not count."""
    root = git_root(folder, home)
    places = [folder]
    if root is not None:
        places += [p for p in folder.parents if p == root or root in p.parents]
    return any(as_dict(projects.get(str(p))).get("hasTrustDialogAccepted") is True for p in places)


# checked 2026-10-26 (code.claude.com/docs/en/skills, "Override skill visibility from settings"):
# `skillOverrides` maps a skill name to "on", "name-only", "user-invocable-only" or "off"; a
# skill that is not listed is "on". Only "off" turns a skill off. Plugin skills are not affected.
# It merges key by key across the files, the most specific one winning: the docs do not say so,
# Claude Code was seen to do it (2026-11-24, docs/clients.md).
SKILL_STATES = ("on", "name-only", "user-invocable-only", "off")


def _skill_rules(layers: list[tuple[Scope, dict]]) -> dict[str, tuple[str, Scope]]:
    """Skill name -> (state, file scope). `layers` run from the least to the most specific file.
    Values the docs do not list are ignored."""
    rules: dict[str, tuple[str, Scope]] = {}
    for scope, settings in layers:
        for name, state in as_dict(settings.get("skillOverrides")).items():
            if state in SKILL_STATES:
                rules[name] = (state, scope)
    return rules


def _apply_rules(
    items: list[Item], rules: dict[str, tuple[str, Scope]], known: bool = True
) -> list[Item]:
    """Mark the skills a rule turns off. A rule that keeps a skill on only records its file; one
    that narrows it ("name-only") is kept as the skill's state, and wins over its file.
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
                item,
                enabled=Enabled.OFF if state == "off" else Enabled.ON,
                state_scope=scope,
                skill_state=None if state == "on" else state,
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
                state = rule[0]
                found.append((path, Enabled.OFF if state == "off" else Enabled.ON, rule[1], state))
        ruled.append(replace(item, project_rules=tuple(found)) if found else item)
    return ruled


# checked 2026-11-22 (code.claude.com/docs/en/hooks, "Disable or remove hooks"; and
# code.claude.com/docs/en/settings, "Settings precedence"): `disableAllHooks: true` turns off the
# hooks of settings files. Claude Code uses the value left after precedence, local over project
# over user, so `false` in a project's files turns user hooks back on there. Not read here: managed
# settings (only a managed `disableAllHooks` turns managed hooks off) and `--settings`.
def _hooks_rule(layers: list[tuple[Scope, dict]]) -> tuple[bool, Scope] | None:
    """Whether `disableAllHooks` turns hooks off, and the file that decides; None when no file
    sets it. `layers` run from the least to the most specific file."""
    rule = None
    for scope, settings in layers:
        value = settings.get("disableAllHooks")
        if isinstance(value, bool):
            rule = (value, scope)
    return rule


def _apply_hooks_rule(items: list[Item], rule: tuple[bool, Scope] | None) -> list[Item]:
    """The hooks as `disableAllHooks` leaves them. A hook that is off before (one that never
    runs, see `dead_hook`) stays off: `false` does not bring it back."""
    if rule is None:
        return items
    off, scope = rule
    return [
        i
        if i.enabled is Enabled.OFF and not off
        else replace(i, enabled=Enabled.OFF if off else Enabled.ON, state_scope=scope)
        for i in items
    ]


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


def main_checkout(folder: Path) -> Path | None:
    """The main checkout of a git worktree, from its `.git` file; None for any other folder."""
    try:
        line = (folder / ".git").read_text().strip()
    except (OSError, ValueError):
        return None
    git, mark, _ = line.removeprefix("gitdir: ").partition("/.git/worktrees/")
    return Path(git) if mark else None


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


def holds(path: Path, key: tuple[str, str]) -> bool:
    """The settings file has `key`; a file Kitden cannot read may have it."""
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return True
    return isinstance(data, dict) and key[1] in as_dict(data.get(key[0]))


class ClaudeCodeAdapter(ClientAdapter):
    id = CLIENT
    display_name = "Claude Code"
    config_root = ".claude"
    skills_folder = ".claude/skills"
    skill_note = NEW_SESSION

    def __init__(
        self,
        home: Path,
        read_version: Callable[[], str | None] | None = None,
        folder: ClaudeFolder | None = None,
    ) -> None:
        """`folder` is where Claude Code keeps the user's files; by default the one the
        environment says (claude_folder)."""
        super().__init__(home, read_version)
        self.folder = folder or claude_folder(home)

    def user_root(self) -> Path:
        return self.folder.config

    def user_skills(self) -> Path:
        return self.folder.config / "skills"

    # checked 2026-11-25 (cursor.com/docs/skills): Cursor's docs name only `~/.claude`. Whether it
    # follows the variables is not checked, so a moved folder is taken not to reach it.
    def reaches_cursor(self, kind: ItemKind) -> bool:
        usual = claude_folder(self.home, {})
        here = (self.folder.config, self.folder.plugins)
        there = (usual.config, usual.plugins)
        if kind is not ItemKind.PLUGIN:
            here, there = here[:1], there[:1]
        return [os.path.realpath(p) for p in here] == [os.path.realpath(p) for p in there]

    def extra_clients(self) -> list[Client]:
        """The Claude Desktop Code tab: Claude Code settings plus claude_desktop_config.json."""
        config = claude_desktop_dir(self.home) / DESKTOP_CONFIG
        bundled = claude_desktop_dir(self.home) / DESKTOP_BUNDLED
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
            if item.scope is Scope.PROJECT and item.enabled is Enabled.UNKNOWN:
                return (PLUGIN_DISABLE, PLUGIN_REMOVE)  # on in the file, so it can go off
            return (*toggle_action(item), PLUGIN_REMOVE)
        if is_own_skill(item, CLIENT):
            return (SKILL_REMOVE,)
        return ()

    def plugin_step(self, item: Item, enable: bool) -> Step:
        check_toggle(self, item, enable)
        if item.scope is Scope.PROJECT:
            need_folder(item.project)
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
            return [self.folder.settings]
        holding = [f for f in local_files(Path(project), self.home) if holds(f, key)]
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
    # `/skills` menu saves it to `.claude/settings.local.json`.
    # checked 2026-11-09 (code.claude.com/docs/en/skills, `skillOverrides`): "on", "name-only"
    # (name listed, no description), "user-invocable-only" and "off"; a missing key is "on".
    def skill_rule_steps(self, name: str, project: str | None, state: str) -> list[Step]:
        """`skillOverrides.<name>` set to "off" or "name-only", in the user settings or in one
        project's local settings. With `state` "on" the project's key goes, so the shared rule
        applies there."""
        value = state if state in ("off", "name-only") else ABSENT
        return self._rule_steps(("skillOverrides", name), project, value, NEW_SESSION)

    # Whether Claude Code reads the key again in a chat that is open is not known (a guess,
    # docs/clients.md, 2026-11-23): the note asks for a new chat, as for `skillOverrides`.
    def skill_limit_step(self, value: Any) -> Step:
        """`skillListingBudgetFraction` set to `value` in the user settings; ABSENT takes it out,
        so the default applies again. Never a project's file."""
        path = self.folder.settings
        return Step(
            client=CLIENT,
            scope=Scope.USER,
            name=LIMIT_KEY,
            edit=FileEdit(path=str(path), fmt="json", key=(LIMIT_KEY,), after=value),
            restart_note=NEW_SESSION,
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
        settings = as_dict(read.json(self.folder.settings))
        known = as_dict(read.json(self.folder.plugins / "known_marketplaces.json"))
        sources: dict[str, str | None] = {}
        for name, entry in {**as_dict(settings.get("extraKnownMarketplaces")), **known}.items():
            source = as_dict(as_dict(entry).get("source"))
            value = source.get("repo") or source.get("url") or source.get("path")
            sources[name] = value if isinstance(value, str) else None
        return sources

    def marketplace_add_step(self, name: str, source: str) -> Step:
        plain_source(source, "Claude Code")  # the source goes into the arguments
        # Checked 2026-10-19 (2.1.283): `marketplace add` records the source under
        # extraKnownMarketplaces in ~/.claude/settings.json; `remove` takes it out.
        edit = FileEdit(
            path=str(self.folder.settings),
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
        path, scope = self.folder.settings, Scope.USER
        if project is not None:
            # checked 2026-10-22 (`claude plugin install --help`, 2.1.283, and
            # code.claude.com/docs/en/plugins/install): `-s project`, run in the project, puts
            # the plugin in `enabledPlugins` of <project>/.claude/settings.json, the file the
            # project shares; `uninstall -s project` takes it out there.
            need_folder(project)
            path, scope = Path(project) / ".claude/settings.json", Scope.PROJECT
        edit = FileEdit(
            path=str(path),
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
        if item.scope is Scope.PROJECT:
            need_folder(item.project)
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
        known = as_dict(Reader(CLIENT).json(self.folder.plugins / "known_marketplaces.json"))
        roots = {}
        for name, entry in known.items():
            where = as_dict(entry).get("installLocation")
            if isinstance(where, str) and Path(where).is_dir():
                roots[name] = Path(where)
        return roots

    def plugin_folders(self) -> dict[str, Path]:
        """Plugin id -> its install folder, the first one in `installed_plugins.json` on disk."""
        record = as_dict(Reader(CLIENT).json(self.folder.plugins / "installed_plugins.json"))
        out: dict[str, Path] = {}
        for plugin_id, installs in as_dict(record.get("plugins")).items():
            for install in installs if isinstance(installs, list) else []:
                where = as_dict(install).get("installPath")
                if isinstance(where, str) and Path(where).is_dir():
                    out[plugin_id] = Path(where)
                    break
        return out

    def setup_server_step(self, command: str, args: list[str]) -> Step:
        return self._add_entry(SETUP_NAME, {"type": "stdio", "command": command, "args": args})

    def _add_entry(self, name: str, value: dict[str, Any]) -> Step:
        """A user-scope MCP entry, added with `claude mcp add-json` (FR-021, FR-024), or written
        directly when it holds a secret."""
        edit = FileEdit(
            path=str(self.folder.state),
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
        cli: dict[str, Any] = {}
        if not redact(value)[1]:
            command = ["claude", "mcp", "add-json", "-s", "user", name, json.dumps(value)]
            cli = {"mechanism": "client_cli", "command": command}
        return Step(
            client=CLIENT,
            scope=Scope.USER,
            name=name,
            edit=edit,
            restart_note=NEW_SESSION,
            **cli,
        )

    def remove_step(self, item: Item) -> Step:
        if REMOVE_DIRECT not in self.item_actions(item):
            raise ValueError(f"{item.name} cannot be removed here")
        key: tuple[str, ...] = ("mcpServers", item.name)
        if item.scope is Scope.LOCAL:
            key = ("projects", str(item.project), "mcpServers", item.name)
        if item.scope is not Scope.USER:
            need_folder(item.project)
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
        state_path = self.folder.state
        settings_path = self.folder.settings
        state = as_dict(read.json(state_path))
        settings = as_dict(read.json(settings_path))
        settings_known = not read.failed(settings_path)

        # MCP servers: user scope, then per-project local scope and project .mcp.json files.
        scan.items += mcp_items(CLIENT, state.get("mcpServers"), state_path, Scope.USER)
        project_skill_rules: dict[str, dict[str, tuple[str, Scope]]] = {}
        project_hook_rules: dict[str, tuple[bool, Scope]] = {}
        projects = as_dict(state.get("projects"))
        installed_path = self.folder.plugins / "installed_plugins.json"
        installed = as_dict(as_dict(read.json(installed_path)).get("plugins"))
        installed_known = not read.failed(installed_path)
        # checked 2026-11-25 (code.claude.com/docs/en/mcp, "Disable a server without removing
        # it"): the /mcp menu records the names it turned off per project in `~/.claude.json`,
        # `projects.<path>.disabledMcpServers`; Claude Code does not connect to those. Not read:
        # the names of plugin and claude.ai servers in it (their form is not checked).
        mcp_offs: dict[str, set[str]] = {}
        for path, data in projects.items():
            data = as_dict(data)
            off_names = _names(data.get("disabledMcpServers"))
            if off_names:
                mcp_offs[path] = off_names
            scan.projects.append(project(path, CLIENT))
            scan.items += [
                replace(i, enabled=Enabled.OFF) if i.name in off_names else i
                for i in mcp_items(
                    CLIENT,
                    data.get("mcpServers"),
                    state_path,
                    Scope.LOCAL,
                    project=path,
                    table=f"projects.{path}.mcpServers",
                )
            ]
            found, rules, hooks_rule = self._project_files(
                read,
                Path(path),
                data,
                settings,
                settings_known,
                is_trusted(projects, Path(path), self.home)
                or is_home(Path(path), self.home)
                or self.folder.is_own(Path(path)),
                installed if installed_known else None,
                off_names,
            )
            scan.items += found
            if rules is not None:
                project_skill_rules[path] = rules
            if hooks_rule is not None:
                project_hook_rules[path] = hooks_rule

        # Plugins: user settings decide on/off; project settings may override.
        enabled = as_dict(settings.get("enabledPlugins"))
        # A user server a project turned off is off only there: a rule of that project.
        scan.items = [
            replace(
                i,
                project_rules=tuple(
                    (p, Enabled.OFF, Scope.LOCAL, "off") for p, n in mcp_offs.items() if i.name in n
                ),
            )
            if i.kind is ItemKind.MCP_SERVER
            and i.client == CLIENT
            and i.scope is Scope.USER
            and any(i.name in n for n in mcp_offs.values())
            else i
            for i in scan.items
        ]
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
                where = as_dict(install).get("installPath", "")
                if isinstance(where, str):
                    scan.items += self._plugin_parts(read, Path(where), state_on)
        account = Source(
            kind=SourceKind.ACCOUNT,
            path=None,
            owner_client=CLIENT,
            read_status=ReadStatus.UNKNOWN,
            unknown_reason=UnknownReason.STORED_IN_ACCOUNT,
        )
        for plugin_id, value in enabled.items():
            if plugin_id.endswith("@synced"):
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
                source=account,
                scope=Scope.ACCOUNT,
                enabled=Enabled.UNKNOWN,
                change_hint=ACCOUNT_HINT,
            )
        )

        # Skills, hooks and marketplaces.
        user_skills = _apply_rules(
            skill_items(CLIENT, self.user_skills(), Scope.USER, CLIENT),
            _skill_rules([(Scope.USER, settings)]),
            settings_known,
        )
        scan.items += _project_rules(user_skills, project_skill_rules)
        scan.items += instruction_items(
            CLIENT, _instruction_files(self.folder.config), Scope.USER, CLIENT
        )
        raw_hooks = hook_items(CLIENT, settings, settings_path, Scope.USER, claude_rules=True)
        user_hooks = _apply_hooks_rule(raw_hooks, _hooks_rule([(Scope.USER, settings)]))
        hook_rules = [
            (path, Enabled.OFF if off else Enabled.ON, scope, "off" if off else "on")
            for path, (off, scope) in project_hook_rules.items()
            if scope is not Scope.USER
        ]
        # A hook that never runs gets no project rule: a rule cannot turn it on.
        scan.items += [
            i if dead.enabled is Enabled.OFF else replace(i, project_rules=tuple(hook_rules))
            for dead, i in zip(raw_hooks, user_hooks, strict=True)
        ]
        marketplaces_path = self.folder.plugins / "known_marketplaces.json"
        for name, entry in as_dict(read.json(marketplaces_path)).items():
            where = marketplace_source(as_dict(entry).get("source"))
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
        desktop_path = claude_desktop_dir(self.home) / DESKTOP_CONFIG
        servers = as_dict(read.json(desktop_path)).get("mcpServers")
        scan.items += mcp_items(DESKTOP, servers, desktop_path, Scope.USER)

        scan.problems = read.problems
        return scan

    def _project_files(
        self,
        read: Reader,
        root: Path,
        data: dict,
        user_settings: dict,
        user_known: bool,
        trusted: bool,
        installed: dict | None,
        mcp_off: set[str],
    ) -> tuple[list[Item], dict[str, tuple[str, Scope]] | None, tuple[bool, Scope] | None]:
        """The project's items, its skill rules (None when a settings file was unreadable) and
        its `disableAllHooks` rule (None when no file sets it). `installed` is None when the
        record of installs was unreadable."""
        path = str(root)
        items: list[Item] = []
        # When the project is the home folder, its `.claude/settings.json` and skills are the
        # user's own, already read as user items; reading them again made a project copy. With
        # the user's folder moved, they are the project's.
        at_home = self.folder.is_own(root)
        settings_path = root / ".claude/settings.json"
        settings = {} if at_home else as_dict(read.json(settings_path))
        # The local files, the winning one last; each plugin key comes from the last that has it.
        locals_ = [(path, as_dict(read.json(path))) for path in local_files(root, self.home)]
        mcp_path = root / ".mcp.json"
        servers = as_dict(as_dict(read.json(mcp_path)).get("mcpServers"))
        unread = not user_known or any(read.failed(p) for p in [settings_path, *dict(locals_)])
        project_files = [settings, *(d for _, d in locals_), data]
        for name, entry in servers.items():
            items.append(
                mcp_item(
                    CLIENT,
                    name,
                    entry,
                    file_source(mcp_path, CLIENT, f"mcpServers.{name}"),
                    Scope.PROJECT,
                    project=path,
                    enabled=Enabled.OFF
                    if name in mcp_off
                    else _approval(name, user_settings, project_files, trusted, unread),
                )
            )
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
            for plugin_id, value in as_dict(file_settings.get("enabledPlugins")).items()
        }
        for (scope, plugin_id), (file_path, value) in plugins.items():
            waits = (
                scope is Scope.PROJECT
                and value is True
                and not plugin_id.endswith(NOT_INSTALLED)
                and not _install_counts((installed or {}).get(plugin_id), path)
                and as_dict(user_settings.get("enabledPlugins")).get(plugin_id) is not True
                and not any(
                    as_dict(d.get("enabledPlugins")).get(plugin_id) is True for _, d in locals_
                )
            )
            items.append(
                Item(
                    client=CLIENT,
                    kind=ItemKind.PLUGIN,
                    name=plugin_id,
                    source=file_source(file_path, CLIENT, f"enabledPlugins.{plugin_id}"),
                    scope=scope,
                    project=path,
                    enabled=Enabled.UNKNOWN if waits else _on(value),
                    state_scope=scope,
                    change_hint=PROJECT_NOT_INSTALLED if waits and installed is not None else None,
                )
            )
        layers = [
            (Scope.USER, user_settings),
            (Scope.PROJECT, settings),
            *((Scope.LOCAL, data) for _, data in locals_),
        ]
        hooks_rule = _hooks_rule(layers)
        items += _apply_hooks_rule(
            hook_items(
                CLIENT, settings, settings_path, Scope.PROJECT, project=path, claude_rules=True
            ),
            hooks_rule,
        )
        rules = _skill_rules(layers)
        read_files = [settings_path, *(p for p, _ in locals_)]
        known = user_known and not any(read.failed(p) for p in read_files)
        if not at_home:
            items += _apply_rules(
                skill_items(CLIENT, root / ".claude/skills", Scope.PROJECT, CLIENT, project=path),
                rules,
                known,
            )
        # checked 2026-10-22 (code.claude.com/docs/en/memory): a project's CLAUDE.md and
        # CLAUDE.local.md at its root, besides the files in its `.claude` folder. When the
        # project is the home folder, its `.claude` files are the user's own and are skipped.
        files = [(root / "CLAUDE.md", "instructions"), (root / "CLAUDE.local.md", "instructions")]
        if not at_home:
            files += _instruction_files(root / ".claude")
        items += instruction_items(CLIENT, files, Scope.PROJECT, CLIENT, project=path)
        return items, (rules if known else None), hooks_rule

    def _plugin_parts(self, read: Reader, root: Path, enabled: Enabled) -> list[Item]:
        if not root.is_dir():
            return []
        items = skill_items(
            CLIENT, root / "skills", Scope.PLUGIN, CLIENT, kind=SourceKind.PLUGIN, enabled=enabled
        )
        mcp_path = root / ".mcp.json"
        servers = as_dict(read.json(mcp_path)).get("mcpServers")
        return items + mcp_items(
            CLIENT, servers, mcp_path, Scope.PLUGIN, enabled=enabled, kind=SourceKind.PLUGIN
        )


def user_folder(adapters: Mapping[str, ClientAdapter], home: Path) -> ClaudeFolder:
    """The folder the Claude Code adapter reads. Without one (the client is off) the usual folder
    in `home`, so the demo never follows the environment."""
    adapter = adapters.get(CLIENT)
    return adapter.folder if isinstance(adapter, ClaudeCodeAdapter) else claude_folder(home, {})
