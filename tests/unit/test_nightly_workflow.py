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
    # `secrets.` as a word, so the file name test_real_secrets.py does not count.
    assert "pull_request" not in TEXT and not re.search(r"\bsecrets\.", TEXT)
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
        "test_real_secrets.py",
        "KITDEN_REAL_KEYCHAIN=1",
    ):
        assert step in job, step
    # The Keychain step runs on macOS only, after the full suite, in a keychain of its own.
    keychain = _step(job, "The real Keychain (macOS)")
    assert "if: runner.os == 'macOS'" in keychain
    assert 'chain="$RUNNER_TEMP/kitden-ci.keychain-db"' in keychain
    assert 'security default-keychain -d user -s "$chain"' in keychain
    # The tests make the same keychain the default of their sandbox HOME, by this name.
    assert 'KITDEN_CI_KEYCHAIN="$chain"' in keychain
    assert job.index("\n      - run: uv run pytest -q\n") < job.index("The real Keychain (macOS)")
    linux = _step(job, "The real keyring, release checks (Ubuntu)")
    assert "if: runner.os == 'Linux'" in linux
    assert "KITDEN_REAL_KEYRING=1 uv run pytest -q tests/unit/test_real_secrets.py" in linux


def test_clients_installs_the_newest_and_runs_the_contract_tests_with_no_account():
    job = _jobs()["clients"]
    assert "os: [macos-latest, ubuntu-latest]" in job and "fail-fast: false" in job
    assert "curl -fsSL https://claude.ai/install.sh | bash" in job
    assert "curl -fsSL https://chatgpt.com/codex/install.sh | sh" in job
    assert "enable-cache: false" in job and "npm install" not in job
    # A failed download or installer stops the job with its own line, and only the commands
    # just installed are run, never another copy on the runner's PATH.
    assert "set -o pipefail" in job
    assert "::error::Claude Code could not be installed" in job
    assert "::error::Codex could not be installed" in job
    assert "$HOME/.local/bin/" in _step(job, "Which versions")
    assert 'KITDEN_NEED_CLIENTS: "1"' in job and 'DISABLE_AUTOUPDATER: "1"' in job
    assert 'uv run pytest -m "contract and not signed_in" -q -rs' in job
    assert "secrets." not in job and "contents: read" in job
    # A red night keeps the files the clients wrote, to add as a new fixture folder.
    assert "KITDEN_WRITTEN: ${{ runner.temp }}/written" in _step(job, "The contract tests")
    upload = _step(job, "Keep the files the clients wrote")
    assert "actions/upload-artifact@" in upload and "if: failure()" in upload
    assert "name: written-files-${{ matrix.os }}" in upload
    assert "path: ${{ runner.temp }}/written" in upload
    assert "if-no-files-found: ignore" in upload and "retention-days: 7" in upload
    # Every saved file is a dotfile or in a dot-folder, which the action leaves out by default.
    assert "include-hidden-files: true" in upload
    # A client that is missing, or a runner with an account, stops the job with one clear line.
    assert "could not be installed" in job and "must run without one" in job
    # The script in kitden-sdlc reads the runs as `clients (<os>)`.
    assert not any(line.startswith("    name:") for line in job.splitlines())


def test_browser_runs_the_page_in_chromium():
    job = _jobs()["browser"]
    assert "runs-on: ubuntu-latest" in job and "contents: read" in job
    assert "playwright==1.64.1" in job and "playwright install --with-deps chromium" in job
    assert "pytest -m browser -q" in job
    # Without Playwright the browser tests skip and the night looks green: stop first.
    assert 'uv run --with playwright==1.64.1 python -c "import playwright"' in job
    assert "timeout-minutes: 5" in _step(job, "Install Chromium")
    # The header's Why speaks for this job too.
    assert "nobody presses every button of the page before a release" in " ".join(TEXT.split())


def test_engines_runs_the_browser_tests_in_chrome_firefox_and_webkit():
    job = _jobs()["engines"]
    assert "leg: [chrome, firefox, webkit]" in job and "fail-fast: false" in job
    assert "runs-on: ${{ matrix.leg == 'webkit' && 'macos-latest' || 'ubuntu-latest' }}" in job
    assert "timeout-minutes: 15" in job and "contents: read" in job
    # The engine comes from the environment (tests/browser/engines.py), never a pytest
    # parameter, so the test ids are the same in every leg.
    assert "KITDEN_BROWSER: ${{ matrix.leg == 'chrome' && 'chromium' || matrix.leg }}" in job
    assert "KITDEN_BROWSER_CHANNEL: ${{ matrix.leg == 'chrome' && 'chrome' || '' }}" in job
    assert "if: matrix.leg == 'chrome'" in _step(job, "Google Chrome")
    assert "google-chrome --version" in _step(job, "Google Chrome")
    firefox, webkit = _step(job, "Install Firefox"), _step(job, "Install WebKit")
    assert "playwright install --with-deps firefox" in firefox and "timeout-minutes: 5" in firefox
    assert "playwright install webkit" in webkit and "--with-deps" not in webkit
    # Without Playwright the tests skip and the night looks green: stop first.
    assert 'uv run --with playwright==1.64.1 python -c "import playwright"' in job
    assert job.index("Playwright imports") < job.index("The browser tests")
    assert "uv run --with playwright==1.64.1 python -m pytest -m browser -q" in job
    # kitden-sdlc reads the runs as `engines (<leg>)`, one part.
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


def test_only_the_intel_mac_gets_twice_the_start_budgets():
    job = _jobs()["systems"]
    lines = job.splitlines()
    run = lines.index("      - run: uv run python scripts/measure-start.py")
    assert lines[run + 1 : run + 3] == [
        "        env:",
        "          KITDEN_START_BUDGET_SCALE: ${{ matrix.os == 'macos-15-intel' && '2' || '1' }}",
    ]
    assert "KITDEN_START_BUDGET_SCALE" not in job.replace(lines[run + 2], "")
    # The pull request and release checks run on no Intel Mac and keep the budgets as they are.
    assert "macos-15-intel" not in RELEASE and "KITDEN_START_BUDGET_SCALE" not in RELEASE
    assert "\n      - run: uv run python scripts/measure-start.py\n" in RELEASE
