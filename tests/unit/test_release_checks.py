"""docs/development.md, "Check before a release": what became of the 24 checks, and the shape
kitden-sdlc's release prep reads (scripts/release_apply.py, `hand_checks`)."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
DEVELOPMENT = (ROOT / "docs/development.md").read_text()
SECTION = DEVELOPMENT.split("\n## Check before a release\n")[1].split("\n## ")[0]
ROWS = re.findall(
    r"^\| (\d+) \| .+? \| (test|signed-in client|by hand) \| (.+?) \|$", SECTION, re.M
)
AREAS = ("the Kitden gateway", "puts back items", "secrets")  # words release prep knows


def test_the_table_has_each_of_the_24_checks_once():
    assert [int(number) for number, _, _ in ROWS] == list(range(1, 25))


def test_at_most_five_checks_stay_by_hand_for_good():
    by_hand = SECTION[SECTION.index("Before a release that") :]
    lines = re.findall(r"^\d+\. .*?(?=^\d+\. |\n\n|\Z)", by_hand, re.M | re.S)
    waiting = [line for line in lines if "(until the tester runs it)" in line]
    assert 1 <= len(lines) - len(waiting) <= 5
    # Each check that waits for a signed-in client is still listed, so nobody forgets it.
    assert len(waiting) == sum(fate == "signed-in client" for _, fate, _ in ROWS)


def test_every_test_the_table_names_exists():
    named = re.findall(r"`(tests/[\w/]+\.py)::(\w+)`", SECTION)
    assert len(named) >= 19
    for path, name in named:
        assert f"def {name}(" in (ROOT / path).read_text(), (path, name)


def test_the_section_keeps_the_shape_release_prep_reads():
    first = SECTION.index("Before a release that")
    assert SECTION.index("| # |") < first
    for group in SECTION[first:].split("Before a release that")[1:]:
        assert any(area in group.split(".")[0] for area in AREAS), group[:80]


def test_not_run_yet_is_gone():
    assert "Not run yet" not in DEVELOPMENT
