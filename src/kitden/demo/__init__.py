"""The demo: a sample home in three sizes, and how Kitden reads it.

The sample is synthetic, for `kitden demo` and tests; no real client wrote it.
"""

from collections.abc import Callable
from pathlib import Path

from kitden.clients.base import ClientAdapter
from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.codex import CodexAdapter
from kitden.clients.cursor import CursorAdapter
from kitden.demo.sample import DEMO_SECRET, SIZES, build_demo_home, demo_command, keychain_file
from kitden.views.inventory import Inventory, build_inventory

__all__ = [
    "DEMO_SECRET",
    "SIZES",
    "VERSIONS",
    "build_demo_home",
    "demo_adapters",
    "demo_build",
    "demo_command",
    "keychain_file",
]

# The client versions whose file shapes the sample copies.
VERSIONS = {"claude_code": "2.1.283", "codex": "0.159.2", "cursor": "3.21.16"}


def _version(home: Path, adapter: type[ClientAdapter]) -> Callable[[], str | None]:
    """The sample's version of a client, while its folder is in the sample."""
    return lambda: VERSIONS[adapter.id] if (home / adapter.config_root).exists() else None


def demo_adapters(home: Path) -> list[ClientAdapter]:
    """The three clients, reading only the sample: no client command runs, CODEX_HOME is not
    read, and Codex's plugin list answers at once with no plugins."""
    return [
        ClaudeCodeAdapter(home, _version(home, ClaudeCodeAdapter)),
        CodexAdapter(
            home,
            _version(home, CodexAdapter),
            codex_home=home / ".codex",
            list_plugins=lambda: {"installed": []},
        ),
        CursorAdapter(home, _version(home, CursorAdapter)),
    ]


def demo_build(home: Path) -> Callable[..., Inventory]:
    """How the demo reads the sample: with `demo_adapters` and no app folder."""
    return lambda **options: build_inventory(home, demo_adapters(home), [], **options)
