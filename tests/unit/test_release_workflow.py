"""The checks-and-release workflow (feature 003: FR-001, contracts/release.md)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/release.yml"


def test_checks_run_on_pushes_pull_requests_and_tags():
    text = WORKFLOW.read_text()
    assert "pull_request:" in text
    assert 'tags: ["v*"]' in text
    # Every check runs on macOS and on Ubuntu (Linux spec, part 4).
    assert "os: [macos-latest, ubuntu-latest]" in text and "runs-on: ${{ matrix.os }}" in text
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


def _jobs() -> dict[str, str]:
    """Each job's name and text."""
    body = WORKFLOW.read_text().split("\njobs:\n")[1]
    parts = re.split(r"^  ([a-z-]+):\n", body, flags=re.MULTILINE)[1:]
    return dict(zip(parts[::2], parts[1::2], strict=True))


def test_one_secret_only_where_the_release_app_signs_in_and_least_privilege():
    """PyPI needs no stored token. The release app's key is used only to tag and, in
    kitden-sdlc's publish workflow, by the jobs of the `release` environment."""
    text = WORKFLOW.read_text()
    assert set(re.findall(r"secrets\.\w+", text)) == {"secrets.RELEASE_APP_PRIVATE_KEY"}
    jobs = _jobs()
    assert {name for name, job in jobs.items() if "secrets." in job} == {"autotag", "stores"}
    assert "environment: release" in jobs["autotag"]
    # Only the GitHub release job writes with the job's own token.
    writes = {name for name, job in jobs.items() if re.search(r"^ +contents: write", job, re.M)}
    assert writes == {"release"}
    # Only PyPI's publish job and the MCP Registry (in the stores job) mint an OIDC token.
    assert {name for name, job in jobs.items() if "id-token: write" in job} == {
        "publish",
        "stores",
    }


def test_the_release_check_runs_on_every_pull_request_push_and_tag():
    """kitden-sdlc's release check compares the files with listing.toml before the build."""
    steps = _build_steps()
    clear, checkout, check = (
        next(i for i, s in enumerate(steps) if marker in s)
        for marker in (
            "rm -rf .kitden-sdlc",
            "repository: KonstantinStarovoytov/kitden-sdlc",
            "release_check.py",
        )
    )
    assert clear < checkout < check < next(i for i, s in enumerate(steps) if "uv build" in s)
    assert "persist-credentials: false" in steps[checkout]
    assert '--tag "$GITHUB_REF_NAME"' in steps[check]
    for i in (clear, checkout, check):
        assert "if: runner.os == 'macOS'\n" in steps[i]
    assert (ROOT / "listing.toml").is_file()


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


def _build_steps() -> list[str]:
    build = WORKFLOW.read_text().split("  build:")[1].split("  publish:")[0]
    return build.split("\n      - ")[1:]


def test_the_release_text_is_the_notes_file():
    release = WORKFLOW.read_text().split("  release:")[1]
    assert '--notes-file "docs/releases/$GITHUB_REF_NAME.md"' in release
    assert "--generate-notes" not in release


def test_a_tag_without_notes_stops_before_pypi():
    """The build job checks the notes file; publish needs build, so nothing reaches PyPI first."""
    steps = [s for s in _build_steps() if 'docs/releases/$GITHUB_REF_NAME.md"' in s]
    assert len(steps) == 1
    assert "if: runner.os == 'macOS' && startsWith(github.ref, 'refs/tags/')" in steps[0]
    assert 'test -s "docs/releases/$GITHUB_REF_NAME.md"' in steps[0]
    assert "exit 1" in steps[0]
    publish = WORKFLOW.read_text().split("  publish:")[1].split("  release:")[0]
    assert "needs: build" in publish


def test_the_build_runs_every_check_the_project_has():
    """The page's tests, a coverage floor, the start-time budget and a dependency audit run on
    every push, as the Python tests do; the tools are pinned."""
    steps = _build_steps()
    text = "\n".join(steps)
    assert "actions/setup-node@" in text and 'node-version: "25"' in text
    assert "node --test tests/frontend/*.test.mjs" in text
    assert "uv run pytest -q --cov=kitden --cov-fail-under=" in text
    assert "uv run python scripts/measure-start.py" in text
    assert "pip-audit==" in text
    # Pinned to a commit, as the other actions are.
    node = next(s for s in steps if "actions/setup-node@" in s)
    assert len(node.split("@")[1].split()[0]) == 40


def test_only_the_macos_job_builds_and_uploads_the_package():
    """publish and release take one dist artifact, so the Ubuntu job builds nothing."""
    steps = _build_steps()
    for marker in ("uv build", "scripts/check-dist.sh dist", "actions/upload-artifact@"):
        (step,) = [s for s in steps if marker in s]
        assert "if: runner.os == 'macOS'" in step


def test_ubuntu_runs_one_real_keyring_round_trip():
    (step,) = [s for s in _build_steps() if "test_real_keyring.py" in s]
    assert "if: runner.os == 'Linux'" in step
    assert "KITDEN_REAL_KEYRING=1" in step and "gnome-keyring-daemon --unlock" in step


def test_autotag_clears_the_kitden_sdlc_folder_and_may_write_workflows():
    """As the build job does, the folder is removed before kitden-sdlc is checked out. The
    release app's token may write workflows: GitHub refuses an app's new tag whose commits
    change .github/workflows otherwise."""
    steps = _jobs()["autotag"].split("\n      - ")[1:]
    clear, checkout, sign_in = (
        next(i for i, s in enumerate(steps) if marker in s)
        for marker in (
            "rm -rf .kitden-sdlc",
            "repository: KonstantinStarovoytov/kitden-sdlc",
            "actions/create-github-app-token@",
        )
    )
    assert clear < checkout < sign_in
    assert "permission-contents: write" in steps[sign_in]
    assert "permission-workflows: write" in steps[sign_in]
