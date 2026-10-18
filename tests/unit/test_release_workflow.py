"""The checks-and-release workflow (feature 003: FR-001, contracts/release.md)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/release.yml"


def test_checks_run_on_pushes_pull_requests_and_tags():
    text = WORKFLOW.read_text()
    assert "pull_request:" in text
    assert 'tags: ["v*"]' in text
    assert "runs-on: macos-latest" in text
    for step in ("uv run ruff check .", "uv run pytest -q", "uv build"):
        assert step in text


def test_release_only_on_a_tag_after_a_green_build():
    text = WORKFLOW.read_text()
    release = text.split("  release:")[1]
    assert "needs: build" in release
    assert "startsWith(github.ref, 'refs/tags/')" in release
    assert "contents: write" in release
    assert "gh release create" in release and "--verify-tag" in release
    assert "GH_TOKEN: ${{ github.token }}" in release


def test_no_stored_secret_and_least_privilege():
    text = WORKFLOW.read_text()
    assert "secrets." not in text
    assert text.count("contents: write") == 1
    assert "id-token" not in text  # PyPI publishing comes later
