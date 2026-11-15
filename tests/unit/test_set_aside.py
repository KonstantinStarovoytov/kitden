"""The list of tests set aside: tests that fail by chance, run only in the nightly last step."""

import re
from pathlib import Path

from tests.conftest import SET_ASIDE, set_aside_ids, split

ROOT = Path(__file__).resolve().parents[2]


def test_ids_are_read_without_comments_and_reasons(tmp_path):
    path = tmp_path / "set-aside.txt"
    path.write_text("# why\n\ntests/unit/test_a.py::test_x  # 2026-11-20 gave up waiting\n")
    assert set_aside_ids(path) == ["tests/unit/test_a.py::test_x"]


def test_each_mode_keeps_its_own_tests():
    ids = ["a.py::x", "a.py::y[1]"]
    assert split(ids, ["a.py::y[1]"], "skip") == (["a.py::x"], ["a.py::y[1]"])
    assert split(ids, ["a.py::y[1]"], "only") == (["a.py::y[1]"], ["a.py::x"])
    assert split(ids, ["a.py::y[1]"], "run") == (ids, [])


LINE = re.compile(r"(tests/\S+\.py)::(\w+)(\[.*\])?  # \d{4}-\d{2}-\d{2} \S.*")


def test_every_listed_test_exists_and_says_since_when_and_why():
    for line in SET_ASIDE.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            found = LINE.fullmatch(line)
            assert found, line
            # The nightly runs this list under the default markers: a contract test would not run.
            assert not found[1].startswith("tests/contract/"), line
            assert f"def {found[2]}(" in (ROOT / found[1]).read_text(), line
