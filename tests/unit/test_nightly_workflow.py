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
    # The full suite as its own step; two other steps only start with these words.
    assert "\n      - run: uv run pytest -q\n" in job
    # Without this check a lost UV_PYTHON would make the 3.13 runs copies of the 3.14 ones.
    assert 'test "$got" = "$WANTED"' in job
    assert "continue-on-error: true" in job
    # The script in kitden-sdlc reads the runs as `systems (<os>, <python>)`.
    assert not any(line.startswith("    name:") for line in job.splitlines())
    for step in (
        "uv sync --locked",
        "uv run pytest -q",
        "node --test tests/frontend/*.test.mjs",
        "uv run python scripts/measure-start.py",
        "--set-aside=only",
        "test_real_keyring.py",
    ):
        assert step in job, step


def test_clients_installs_the_newest_and_runs_the_contract_tests_with_no_account():
    job = _jobs()["clients"]
    assert "os: [macos-latest, ubuntu-latest]" in job and "fail-fast: false" in job
    assert "curl -fsSL https://claude.ai/install.sh | bash" in job
    assert "curl -fsSL https://chatgpt.com/codex/install.sh | sh" in job
    assert "enable-cache: false" in job and "npm install" not in job
    assert 'KITDEN_NEED_CLIENTS: "1"' in job and 'DISABLE_AUTOUPDATER: "1"' in job
    assert 'uv run pytest -m "contract and not signed_in" -q -rs' in job
    assert "secrets." not in job and "contents: read" in job
    # A client that is missing, or a runner with an account, stops the job with one clear line.
    assert "could not be installed" in job and "must run without one" in job
    # The script in kitden-sdlc reads the runs as `clients (<os>)`.
    assert not any(line.startswith("    name:") for line in job.splitlines())


def test_pull_requests_keep_the_fast_set():
    build = RELEASE.split("  build:")[1].split("  publish:")[0]
    assert "os: [macos-latest, ubuntu-latest]" in build
    assert "matrix.python" not in build and "UV_PYTHON" not in build


def _step(text: str, name: str) -> str:
    """The step with this name, with the comment lines just above it."""
    lines = text.splitlines()
    start = end = lines.index(f"      - name: {name}") + 1
    while lines[start - 2].startswith("      #"):
        start -= 1
    while end < len(lines) and not lines[end].startswith(("      - ", "      #")):
        end += 1
    return "\n".join(lines[start - 1 : end]).rstrip()


def test_the_keyring_steps_are_the_same_as_in_the_pull_request_checks():
    for name in ("A keyring on the session bus (Ubuntu)", "The real keyring (Ubuntu)"):
        assert _step(TEXT, name) == _step(RELEASE, name), name


def test_every_action_is_pinned_by_a_full_commit_with_its_tag():
    for line in TEXT.splitlines():
        if "uses:" in line:
            assert re.search(r"@[0-9a-f]{40} # v\d", line), line


def test_the_development_page_names_the_nightly_run():
    text = " ".join((ROOT / "docs/development.md").read_text().split())
    assert "Every night the tests also run on four systems and two Pythons" in text
    assert "the contract tests also run against the newest Claude Code and Codex" in text
    assert '`-m "contract and not signed_in"`' in text
