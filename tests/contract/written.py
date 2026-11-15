"""The shapes of the files the clients write: keys and value types, never values. Only the
parts Kitden reads count. The contract test makes the newest clients write and compares the
shapes with the newest fixture folder of each client."""

import json
import os
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

from kitden.clients.versions import highest_version

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# Maps whose keys the user names, such as the names in `env`: only their values' shapes count.
FREE = frozenset({"env", "headers", "http_headers", "env_http_headers", "enabledPlugins"})

# Per client, a file under the home and a key path; `*` means every key.
WATCHED: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "claude_code": (
        (".claude.json", ("mcpServers", "*")),
        (".claude/settings.json", ("enabledPlugins",)),
        (".claude/settings.json", ("extraKnownMarketplaces", "*")),
        (".claude/plugins/installed_plugins.json", ("plugins", "*")),
        (".claude/plugins/known_marketplaces.json", ("*",)),
    ),
    "codex": (
        (".codex/config.toml", ("mcp_servers", "*")),
        (".codex/config.toml", ("plugins", "*")),
        (".codex/config.toml", ("marketplaces", "*")),
    ),
}


def _once_sorted(shapes) -> list:
    """Each shape once, in a fixed order."""
    unique = {json.dumps(s, sort_keys=True): s for s in shapes}
    return [unique[k] for k in sorted(unique)]


def shape(value, free: bool = False) -> object:
    """The keys and types of a value, without the value."""
    if isinstance(value, dict):
        if free:
            return {"*": _once_sorted(shape(v) for v in value.values())}
        return {k: shape(value[k], k in FREE) for k in sorted(value)}
    if isinstance(value, list):
        return _once_sorted(shape(v) for v in value)
    if value is None:
        return "null"
    return type(value).__name__


def _read(path: Path):
    if path.suffix == ".toml":
        return tomllib.loads(path.read_text())
    return json.loads(path.read_text())


def parts(home: Path, client: str) -> dict[str, list[object]]:
    """Per watched part, labelled "<file>: <path>", the shapes found there, each once."""
    found: dict[str, list[object]] = {}
    for name, path in WATCHED[client]:
        file = home / name
        if not file.is_file():
            continue
        values = [_read(file)]
        for key in path:
            if key == "*":
                values = [v for d in values if isinstance(d, dict) for v in d.values()]
            else:
                values = [d[key] for d in values if isinstance(d, dict) and key in d]
        shapes = _once_sorted(shape(v, path[-1] in FREE) for v in values)
        if shapes:
            found[f"{name}: {'.'.join(path)}"] = shapes
    return found


def _shared(a, b) -> int:
    """How many keys two shapes share; a list counts its best item."""
    if isinstance(a, dict) and isinstance(b, dict):
        return len(a.keys() & b.keys())
    if isinstance(a, list) and isinstance(b, list) and a and b:
        return max(_shared(x, y) for x in a for y in b)
    return 0


def _closest(real, stored: list):
    return max(stored, key=lambda s: _shared(real, s))


def _differences(real, stored, where: str) -> list[str]:
    """What `real` has that `stored` does not, as short phrases. A list or map with fewer
    kinds of items than the fixture is not a difference."""
    if isinstance(real, dict) and isinstance(stored, dict):
        out = [f"new key {where}{k} ({_text(real[k])})" for k in real if k not in stored]
        out += [f"missing key {where}{k}" for k in stored if k not in real]
        for k in sorted(real.keys() & stored.keys()):
            out += _differences(real[k], stored[k], f"{where}{k}.")
        return out
    if isinstance(real, list) and isinstance(stored, list):
        out = []
        for item in real:
            if item in stored:
                continue
            if stored:
                out += _differences(item, _closest(item, stored), f"{where}[].")
            else:
                out.append(f"new kind of item in {where.rstrip('.')} ({_text(item)})")
        return out
    if real == stored:
        return []
    name = where.rstrip(".") or "the value"
    return [f"type of {name} is {_text(real)}, the fixture has {_text(stored)}"]


def _text(s) -> str:
    return s if isinstance(s, str) else json.dumps(s, sort_keys=True)


def unknown(real: dict[str, list], stored: dict[str, list]) -> list[str]:
    """One sentence for each shape in `real` that `stored` lacks for that part."""
    lines = []
    for part, shapes in real.items():
        if part not in stored:
            lines.append(f"{part}: no fixture has this part. Add the saved file as a fixture.")
            continue
        for s in shapes:
            if s in stored[part]:
                continue
            found = _differences(s, _closest(s, stored[part]), "")
            if found:
                lines.append(
                    f"{part}: {'; '.join(found)}. "
                    "Add the saved files as a new version folder (tests/fixtures/README.md)."
                )
    return lines


def _run(home: Path, command: str, *args: str) -> None:
    env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}
    done = subprocess.run(
        [command, *args], env=env, cwd=home, capture_output=True, text=True, timeout=180
    )
    assert done.returncode == 0, f"{args}: {done.stdout}\n{done.stderr}"


STDIO = {"type": "stdio", "command": "npx", "args": ["-y", "notes-mcp"]}
HTTP = {
    "type": "http",
    "url": "https://mcp.example.com/mcp",
    "headers": {"Authorization": "Bearer SENTINEL_SECRET_TOKEN"},
}


def _claude_code(home: Path, claude: str, checkout: Path) -> None:
    _run(home, claude, "mcp", "add-json", "-s", "user", "notes", json.dumps(STDIO))
    _run(home, claude, "mcp", "add-json", "-s", "user", "remote", json.dumps(HTTP))
    _run(home, claude, "plugin", "marketplace", "add", str(checkout))
    _run(home, claude, "plugin", "install", "kitden@kitden", "--scope", "user")


def _codex(home: Path, codex: str, checkout: Path) -> None:
    (home / ".codex").mkdir(exist_ok=True)
    _run(home, codex, "mcp", "add", "notes", "--", "npx", "-y", "notes-mcp")
    url = "https://mcp.example.com/mcp"
    _run(home, codex, "mcp", "add", "remote", "--url", url, "--bearer-token-env-var", "TOKEN")
    _run(home, codex, "plugin", "marketplace", "add", str(checkout), "--json")
    _run(home, codex, "plugin", "add", "kitden@kitden", "--json")


# The client's own commands that make it write its files: (home, the client's command, the
# checkout).
RECIPES: dict[str, Callable[[Path, str, Path], None]] = {
    "claude_code": _claude_code,
    "codex": _codex,
}


def newest_fixture(client: str) -> Path:
    """The fixture folder of the client's highest version."""
    folder = FIXTURES / client
    version = highest_version(p.name for p in folder.iterdir() if p.is_dir())
    assert version, f"no fixture folder for {client}"
    return folder / version


def save(home: Path, client: str, to: Path) -> None:
    """Copy the watched files to `to/<client>/`, with the home's path as {HOME}."""
    # On macOS the temp folder has two names, /var/… and /private/var/…: the longer goes first.
    homes = sorted({str(home), str(home.resolve())}, key=len, reverse=True)
    for name in dict.fromkeys(file for file, _ in WATCHED[client]):
        source = home / name
        if not source.is_file():
            continue
        text = source.read_text()
        for path in homes:
            text = text.replace(path, "{HOME}")
        target = to / client / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
