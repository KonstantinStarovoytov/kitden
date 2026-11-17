"""The CPU and memory workflow: it measures with a read-only token, and only main's report code
runs next to the token that writes the numbers."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / ".github/workflows/use.yml").read_text()


def _jobs() -> dict[str, str]:
    """Each job's name and text."""
    body = TEXT.split("\njobs:\n")[1]
    parts = re.split(r"^  ([a-z-]+):\n", body, flags=re.MULTILINE)[1:]
    return dict(zip(parts[::2], parts[1::2], strict=True))


def _step(job: str, name: str) -> str:
    """The step with this name, up to the next step."""
    return job.split(f"      - name: {name}\n")[1].split("\n      - ")[0]


def test_it_runs_every_night_and_by_hand_never_on_a_pull_request_and_holds_no_secret():
    assert 'cron: "23 3 * * *"' in TEXT and "workflow_dispatch:" in TEXT
    assert "      versions:\n" in TEXT and "pull_request" not in TEXT
    assert not re.search(r"\bsecrets\.", TEXT)
    assert "\npermissions: {}\n" in TEXT and TEXT.count("persist-credentials: false") == 3
    assert TEXT.startswith("# What: ") and "\n# Why: " in TEXT
    assert "\nname: CPU and memory\n" in TEXT
    assert set(_jobs()) == {"use", "use-store"}


def test_use_measures_with_a_read_only_token_in_fresh_plain_venvs():
    job = _jobs()["use"]
    assert "runs-on: ubuntu-latest" in job and "contents: write" not in job
    assert "    permissions:\n      contents: read\n" in job
    install = _step(job, "Install the versions")
    assert install.count("uv venv --python 3.13") == 4
    assert "uv tool install" not in install and "uv sync" not in install
    # A and B are resolved at the same moment; a release of a backfill at its own day.
    assert install.count('--exclude-newer "$at"') == 4
    assert 'measure-use.py cutoff "$v"' in install
    # main is B of a night, and the last version of a backfill (its chart's last point).
    assert install.count("main@${GITHUB_SHA::7}") == 2
    # The dispatch input reaches the shell only through env, and only as a version.
    assert "VERSIONS: ${{ inputs.versions }}" in job and "${{ inputs.versions }}" not in install
    assert 'case "$v" in *[!0-9.]*|"")' in install
    assert '--with "$PSUTIL"' in _step(job, "Measure") and "PSUTIL: psutil==7.2.2" in job


def test_no_pypi_records_nothing_and_stays_green():
    job = _jobs()["use"]
    pypi = _step(job, "PyPI answers")
    assert "::warning::PyPI could not be reached, so nothing was measured tonight." in pypi
    assert 'echo "ok=false" >> "$GITHUB_OUTPUT"' in pypi and "exit 1" not in pypi
    assert job.count("if: steps.pypi.outputs.ok == 'true'") == 4
    # use-store runs only when there is a file to store: not without PyPI, not after a crash.
    assert "measured: ${{ steps.measure.outcome == 'success' }}" in job


def test_the_numbers_are_uploaded_before_the_limits_are_checked():
    job = _jobs()["use"]
    upload = job.index("actions/upload-artifact@")
    assert job.index("measure-use.py run") < upload < job.index("measure-use.py check")
    assert "if-no-files-found: error" in job


def test_use_store_runs_only_mains_report_code_and_pushes_only_from_main():
    job = _jobs()["use-store"]
    assert "needs: use" in job
    assert (
        "if: ${{ !cancelled() && github.ref == 'refs/heads/main' "
        "&& needs.use.outputs.measured == 'true' }}" in job
    )
    assert "contents: write" in job
    assert "ref: main\n" in job and "ref: use-numbers\n" in job
    # No install of the release or the wheel, no psutil, no build: the standard library only.
    for word in ("uv pip", "uv build", "uv sync", "--with", "kitden=="):
        assert word not in job, word
    assert 'measure-use.py store "$RUNNER_TEMP/use/result.json" out' in job
    assert "HEAD:use-numbers" in job and "GH_TOKEN: ${{ github.token }}" in job


def test_every_action_is_pinned_by_a_full_commit_with_its_tag():
    for line in TEXT.splitlines():
        if "uses:" in line:
            assert re.search(r"@[0-9a-f]{40} # v\d", line), line
