"""Where Claude Code keeps the user's own files. Every read and write takes the paths from here,
so they move together. A project's own `.claude` folder does not move.

checked 2026-11-25 (code.claude.com/docs/en/env-vars, /en/claude-directory): CLAUDE_CONFIG_DIR
replaces `~/.claude`, and `.claude.json` is then inside it. checked 2026-11-25
(/en/plugins/loading): CLAUDE_CODE_PLUGIN_CACHE_DIR is the plugins folder itself.
Seen 2026-11-25 (Claude Code 2.1.311 in sandbox homes): `.claude.json` moves also when the
variable names `~/.claude` itself; an empty value counts as none; a leading `~` is the home folder
for the plugins folder only. Not read: the variables in a settings file's `env`.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClaudeFolder:
    config: Path  # settings, skills, instruction files, chats
    state: Path  # .claude.json
    plugins: Path  # installed_plugins.json, known_marketplaces.json

    @property
    def settings(self) -> Path:
        return self.config / "settings.json"

    def is_own(self, project: Path) -> bool:
        """The project's `.claude` folder is this one: its files are the user's own."""
        real = os.path.realpath
        return self.config.name == ".claude" and real(project) == real(self.config.parent)


def claude_folder(home: Path, env: Mapping[str, str] | None = None) -> ClaudeFolder:
    """The folders in `env`, this process's environment by default. The demo passes {}."""
    env = os.environ if env is None else env
    moved, plugins = env.get("CLAUDE_CONFIG_DIR"), env.get("CLAUDE_CODE_PLUGIN_CACHE_DIR")
    config = Path(moved) if moved else home / ".claude"
    if plugins and _from_home(plugins):
        plugins = str(home / plugins[2:])
    return ClaudeFolder(
        config=config,
        state=(config if moved else home) / ".claude.json",
        plugins=Path(plugins) if plugins else config / "plugins",
    )


def _from_home(plugins: str) -> bool:
    return plugins == "~" or plugins.startswith("~/")


def make_absolute() -> None:
    """Pin a relative folder to the start folder: the page and the client commands that Kitden
    runs work in other folders, and would each take it from there."""
    for name in ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_PLUGIN_CACHE_DIR"):
        value = os.environ.get(name)
        if value and not (name == "CLAUDE_CODE_PLUGIN_CACHE_DIR" and _from_home(value)):
            os.environ[name] = str(Path(value).absolute())
