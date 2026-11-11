"""The daily check on the newest dependencies: users get those, not the locked ones."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/latest-deps.yml"


def test_it_runs_the_tests_on_the_newest_versions_every_day():
    text = WORKFLOW.read_text()
    assert "schedule:" in text and "cron:" in text
    assert "workflow_dispatch:" in text
    assert "uv sync --upgrade" in text
    assert "uv run --no-sync pytest -q" in text
    # The locked versions are the pull request checks' job.
    assert "--locked" not in text


def test_it_has_no_secret_and_cannot_write():
    text = WORKFLOW.read_text()
    assert "secrets." not in text
    assert "contents: read" in text and "write" not in text
    assert "persist-credentials: false" in text


def test_the_development_page_names_the_daily_check():
    text = " ".join((ROOT / "docs/development.md").read_text().split())
    assert "Once a day the tests also run on the newest versions of the dependencies" in text
