"""docs/clients.md keeps its shape: the client watcher reads it."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _rows():
    lines = (ROOT / "docs/clients.md").read_text().splitlines()
    return [
        [c.strip() for c in line.strip("|").split("|")]
        for line in lines
        if line.startswith("|") and not line.startswith(("| What", "|---"))
    ]


def test_every_row_has_six_cells_and_a_known_kind():
    for row in _rows():
        assert len(row) == 6, row
        assert row[1] in {"path", "key", "command", "limit", "system"}, row
        assert row[4] in {"same", "differs", "macOS only"}, row


def test_every_named_file_exists():
    for row in _rows():
        files = re.findall(r"`([^`]+)`", row[2])
        assert files, row
        for name in files:
            assert (ROOT / name).is_file(), name


def test_every_source_is_an_address_or_a_known_word():
    for row in _rows():
        assert row[5] in {"help", "install", "guess"} or row[5].startswith("https://"), row


def test_all_three_clients_have_rows():
    text = (ROOT / "docs/clients.md").read_text()
    for name in ("## Claude Code", "## Codex", "## Cursor"):
        assert name in text
