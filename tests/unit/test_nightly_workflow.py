"""The nightly tests: the systems and Pythons a pull request does not run on."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/nightly.yml"
TEXT = WORKFLOW.read_text() if WORKFLOW.exists() else ""
RELEASE = (ROOT / ".github/workflows/release.yml").read_text()


def _jobs() -> dict[str, str]:
    """Each job's name and text."""
    body = TEXT.split("\njobs:\n")[1]
    parts = re.split(r"^  ([a-z-]+):\n", body, flags=re.MULTILINE)[1:]
    return dict(zip(parts[::2], parts[1::2], strict=True))


def test_it_runs_every_night_and_by_hand_never_on_a_pull_request_and_holds_no_secret():
    assert 'cron: "37 2 * * *"' in TEXT and "workflow_dispatch:" in TEXT
    assert "pull_request" not in TEXT and "secrets." not in TEXT
    assert "\npermissions: {}\n" in TEXT and "persist-credentials: false" in TEXT
    assert TEXT.startswith("# What: ") and "\n# Why: " in TEXT and "\nname: Nightly tests\n" in TEXT


def test_systems_runs_four_systems_and_two_pythons():
    job = _jobs()["systems"]
    assert "os: [macos-latest, macos-15-intel, ubuntu-latest, ubuntu-24.04-arm]" in job
    assert 'python: ["3.13", "3.14"]' in job and "fail-fast: false" in job
    assert "UV_PYTHON: ${{ matrix.python }}" in job
    for step in (
        "uv sync --locked",
        "uv run pytest -q",
        "node --test tests/frontend/*.test.mjs",
        "uv run python scripts/measure-start.py",
        "--set-aside=only",
        "test_real_keyring.py",
    ):
        assert step in job, step


def test_pull_requests_keep_the_fast_set():
    build = RELEASE.split("  build:")[1].split("  publish:")[0]
    assert "os: [macos-latest, ubuntu-latest]" in build and "3.13" not in build


def test_every_action_is_pinned_by_a_full_commit_with_its_tag():
    for line in TEXT.splitlines():
        if "uses:" in line:
            assert re.search(r"@[0-9a-f]{40} # v\d", line), line


def test_the_development_page_names_the_nightly_run():
    text = " ".join((ROOT / "docs/development.md").read_text().split())
    assert "Every night the tests also run on four systems and two Pythons" in text
