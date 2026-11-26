"""The plugins of the user's Claude account, as the Claude app gives them to Claude Code.

checked 2026-11-26 (real files and the app's log, Claude app 6.28899.6 with Claude Code 2.1.330):
the app downloads the account's plugins to local-agent-mode-sessions/<account>/<org>/rpm/<id>/ in
its own folder, where manifest.json lists them (`plugins[].id`, `installationPreference`), and
gives those folders to each Code tab session. A plugin given so has the id `<name>@inline`, with
the name its plugin.json says (seen in `pluginUsage` of ~/.claude.json and, for a made-up plugin,
in a session's first message). plugin-list/<account>/<org>/plugins.json keeps the app's own
`enabled` of each, with its folder as `installPath`; only `true` was seen there, so that `false`
means the app does not give it is a guess.

Terminal sessions get the same plugins another way (code.claude.com/docs/en/plugins/loading,
checked 2026-11-26): Claude Code downloads them itself into ~/.claude/plugins/synced, and they
load as `<name>@synced`. No plugin was seen in that folder, so Kitden does not read it.
"""

from dataclasses import dataclass
from pathlib import Path

from kitden.clients.base import Reader
from kitden.local_gateway.settings import as_dict
from kitden.model import Item, ItemKind, Scope

# The end of the id Claude Code gives a plugin that comes from the app.
FROM_APP = "@inline"


@dataclass(frozen=True)
class AccountPlugin:
    id: str  # `<name>@inline`
    folder: Path
    on_by_default: bool  # plugin.json says `defaultEnabled: false` when it is not
    required: bool  # the organization requires it
    off_in_account: bool  # the app does not give it to Claude Code


def is_account_plugin(item: Item) -> bool:
    """The plugin of the Claude account itself, not a project's own setting for it."""
    return (
        item.kind is ItemKind.PLUGIN and item.scope is Scope.USER and item.name.endswith(FROM_APP)
    )


def _newest(folder: Path, pattern: str) -> Path | None:
    """The file that changed last. The app keeps one folder per account and organization, and
    writes the one in use at each sync (every 20 minutes, by its log)."""
    found = []
    for path in folder.glob(pattern):
        try:
            found.append((path.stat().st_mtime, path))
        except OSError:  # gone since the folder was listed
            continue
    return max(found)[1] if found else None


def _rows(value: object) -> list[dict]:
    rows = as_dict(value).get("plugins")
    return [as_dict(row) for row in rows] if isinstance(rows, list) else []


def account_plugins(app: Path, read: Reader) -> list[AccountPlugin]:
    """The plugins in the app's folder, for the account in use. One whose files or name are not
    there is left out: Claude Code has nothing to load."""
    manifest = _newest(app, "local-agent-mode-sessions/*/*/rpm/manifest.json")
    if manifest is None:
        return []
    rpm = manifest.parent
    # The same two folders, account and organization, as the manifest's.
    listed = app / "plugin-list" / rpm.parent.parent.name / rpm.parent.name / "plugins.json"
    # By the folder's name: the folder is in `rpm`, wherever the app's folder is.
    off = {
        Path(where).name
        for row in _rows(read.json(listed))
        if row.get("enabled") is False and isinstance(where := row.get("installPath"), str)
    }
    found: dict[str, AccountPlugin] = {}
    for row in _rows(read.json(manifest)):
        folder_name = row.get("id")
        # One folder inside `rpm`, never a path that leads out of it.
        if (
            not isinstance(folder_name, str)
            or Path(folder_name).name != folder_name
            or folder_name.startswith(".")
        ):
            continue
        folder = rpm / folder_name
        about = as_dict(read.json(folder / ".claude-plugin/plugin.json"))
        name = about.get("name")
        if not isinstance(name, str) or not name or "@" in name:
            continue
        plugin = AccountPlugin(
            id=name + FROM_APP,
            folder=folder,
            on_by_default=about.get("defaultEnabled") is not False,
            required=row.get("installationPreference") == "required",
            off_in_account=folder_name in off,
        )
        found.setdefault(plugin.id, plugin)
    return list(found.values())
