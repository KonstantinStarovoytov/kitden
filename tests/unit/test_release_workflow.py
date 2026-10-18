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
    assert "needs: [build, publish]" in release
    assert "startsWith(github.ref, 'refs/tags/')" in release
    assert "contents: write" in release
    assert "gh release create" in release and "--verify-tag" in release
    assert "GH_TOKEN: ${{ github.token }}" in release


def test_no_stored_secret_and_least_privilege():
    text = WORKFLOW.read_text()
    assert "secrets." not in text
    assert text.count("contents: write") == 1
    assert text.count("id-token: write") == 1  # only the publish job may mint an OIDC token


def test_pypi_publish_is_its_own_job_between_build_and_release():
    text = WORKFLOW.read_text()
    publish = text.split("  publish:")[1].split("  release:")[0]
    assert "needs: build" in publish
    assert "startsWith(github.ref, 'refs/tags/')" in publish
    assert "environment: pypi" in publish
    assert "id-token: write" in publish
    assert "uv publish" in publish and "--trusted-publishing always" in publish
    release = text.split("  release:")[1]
    assert "needs: [build, publish]" in release
