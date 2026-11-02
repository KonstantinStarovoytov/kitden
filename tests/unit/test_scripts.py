"""The scripts under scripts/ name only what the package still has: no test runs them, so a
renamed or removed name would only show when someone runs one."""

import ast
import importlib
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _missing(script: Path) -> list[str]:
    """`from kitden… import name` that the module lacks, and `module.name` on an imported
    kitden module that lacks it."""
    tree = ast.parse(script.read_text())
    modules: dict[str, ModuleType] = {}
    missing = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("kitden"):
            module = importlib.import_module(node.module)
            for alias in node.names:
                found = getattr(module, alias.name, None)
                if found is None:
                    try:
                        found = importlib.import_module(f"{node.module}.{alias.name}")
                    except ImportError:
                        missing.append(f"{node.module}.{alias.name}")
                        continue
                if isinstance(found, ModuleType):
                    modules[alias.asname or alias.name] = found
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            module = modules.get(node.value.id)
            if module is not None and not hasattr(module, node.attr):
                missing.append(f"{module.__name__}.{node.attr}")
    return [f"{script.name}: {name}" for name in missing]


def test_every_kitden_name_a_script_uses_exists():
    assert [m for s in sorted((ROOT / "scripts").glob("*.py")) for m in _missing(s)] == []
