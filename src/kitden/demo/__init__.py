"""The demo: a sample home in three sizes, how Kitden reads it, and the stand-ins that keep
every change inside it (client commands, the Keychain, tool lists, the sign-in check).

The sample is synthetic, for `kitden demo` and tests; no real client wrote it.
"""

from collections.abc import Callable, Iterable
from pathlib import Path

from kitden.clients.base import ClientAdapter
from kitden.clients.claude_code import ClaudeCodeAdapter
from kitden.clients.codex import CodexAdapter
from kitden.clients.cursor import CursorAdapter
from kitden.demo.keychain import DemoKeychain
from kitden.demo.runner import NOT_IN_DEMO, DemoRunner
from kitden.demo.sample import (
    DEMO_SECRET,
    SIZES,
    _tool,
    build_demo_home,
    demo_command,
    keychain_file,
)
from kitden.local_gateway.settings import load_settings, load_tools, save_tools
from kitden.views.inventory import Inventory, build_inventory

__all__ = [
    "CANNED_TOOLS",
    "DEMO_SECRET",
    "NOT_IN_DEMO",
    "SIZES",
    "VERSIONS",
    "DemoKeychain",
    "DemoRunner",
    "build_demo_home",
    "canned_refresh",
    "demo_adapters",
    "demo_build",
    "demo_command",
    "keychain_file",
    "no_sign_in",
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


# The tools a server moved in during the demo lists, as no server starts: one that reads, one
# that may write by its name, and one Kitden cannot tell.
CANNED_TOOLS: tuple[dict, ...] = (
    _tool("search", "Search the items.", {"readOnlyHint": True}),
    _tool("create_item", "Add an item."),
    _tool("summarize", "Sum up the items."),
)


async def canned_refresh(home: Path, names: Iterable[str] | None = None) -> dict[str, str | None]:
    """`refresh_tools` in the demo: starts nothing. Each held server asked (all when `names` is
    None) answers None; one without a known list gets `CANNED_TOOLS`, a known list stays."""
    servers = load_settings(home)["servers"]
    held = [name for name in (servers if names is None else names) if name in servers]
    known = load_tools(home)
    for name in held:
        if name not in known:
            save_tools(home, name, list(CANNED_TOOLS))
    return dict.fromkeys(held)


def no_sign_in(url: str, headers: dict) -> bool:
    """`needs_sign_in` in the demo: the sample's remote servers send a header and need no
    sign-in, and nothing goes online."""
    return False
