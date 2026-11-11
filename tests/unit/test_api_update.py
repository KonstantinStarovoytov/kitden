"""Updating Kitden from the page: GET and POST /api/update, and the page hand-over."""

import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import anyio.to_thread
from starlette.testclient import TestClient

from kitden import __version__
from kitden.gateways import data_dir
from kitden.update.install import Install
from kitden.update.run import Outcome
from kitden.views.inventory import Inventory
from kitden.web.app import create_app
from tests.unit.test_demo_mode import demo_page

ORIGIN = "http://127.0.0.1:47800"
POST = {"Origin": ORIGIN, "X-Tool-Request": "1"}
UV = Install("uv", Path("/fake/tools/kitden/bin/kitden"), ("/fake/uv", "tool", "upgrade", "kitden"))
BREW = Install(
    "brew", Path("/fake/brew/opt/kitden/bin/kitden"), ("/fake/brew/bin/brew", "upgrade", "kitden")
)
NEWER = "99.0.0"


def pypi(version=NEWER):
    return lambda url: json.dumps({"info": {"version": version}}).encode()


def offline(url):
    raise OSError("offline")


def no_start(launcher, value):
    raise AssertionError("started a new page")


@contextmanager
def update_page(tmp_path, **options):
    home = tmp_path / "home"
    home.mkdir()
    options = {"install": UV, "fetch": pypi(), "start_page": no_start, **options}
    app = create_app(lambda **o: Inventory(), token="tok", port=47800, home=home, **options)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        page.home = home
        page.app = app
        yield page


def until(ready, seconds=5.0):
    end = time.monotonic() + seconds
    while not ready():
        assert time.monotonic() < end, "gave up waiting"
        time.sleep(0.02)


def view(page):
    answer = page.get("/api/update")
    assert answer.status_code == 200
    return answer.json()


def test_without_an_install_there_is_no_button_but_the_command(tmp_path):
    with update_page(tmp_path, install=None) as page:
        until(lambda: view(page)["latest"] == NEWER)
        assert view(page) == {
            "version": __version__,
            "latest": NEWER,
            "can_update": False,
            "command": "uv tool install --python 3.13 kitden",
            "notes_url": f"https://github.com/KonstantinStarovoytov/kitden/releases/tag/v{NEWER}",
            "state": "idle",
            "step": None,
            "tail": [],
        }
        assert page.post("/api/update", headers=POST).status_code == 409


def test_a_homebrew_install_can_update_and_names_brew(tmp_path):
    with update_page(tmp_path, install=BREW, fetch=lambda url: b"kitden-99.0.0.tar.gz") as page:
        until(lambda: view(page)["latest"] == NEWER)
        answer = view(page)
        assert answer["can_update"] is True
        assert answer["command"] == "brew upgrade kitden"


def test_nothing_newer_has_no_notes(tmp_path):
    with update_page(tmp_path, fetch=pypi(__version__)) as page:
        until(lambda: view(page)["latest"] == __version__)
        assert view(page)["notes_url"] is None


def test_the_check_runs_in_the_background_once(tmp_path):
    gate = threading.Event()
    asked = []

    def slow(url):
        asked.append(url)
        gate.wait(5)
        return pypi()(url)

    with update_page(tmp_path, fetch=slow) as page:
        started = time.monotonic()
        assert view(page)["latest"] is None  # answers at once with what is known
        assert view(page)["latest"] is None
        assert time.monotonic() - started < 2
        gate.set()
        until(lambda: view(page)["latest"] == NEWER)
        view(page)
    assert len(asked) == 1


def test_a_demo_never_checks_and_cannot_update(tmp_path):
    asked = []

    def fetch(url):
        asked.append(url)
        raise OSError("offline")

    async def upgrade(install, on_step, before):
        raise AssertionError("ran an installer")

    with demo_page(
        tmp_path / "demo", install=UV, fetch=fetch, upgrade=upgrade, start_page=no_start
    ) as page:
        answer = view(page)
        assert (answer["latest"], answer["can_update"], answer["notes_url"]) == (None, False, None)
        assert page.post("/api/update", headers=POST).status_code == 409
        time.sleep(0.2)
        assert view(page)["latest"] is None
    assert asked == []


def test_an_update_shows_real_steps_and_hands_the_page_over(tmp_path):
    gates = [threading.Event(), threading.Event()]
    started = []

    async def upgrade(install, on_step, before):
        assert (install, before) == (UV, __version__)
        await anyio.to_thread.run_sync(gates[0].wait, 5)
        on_step(1)
        await anyio.to_thread.run_sync(gates[1].wait, 5)
        return Outcome("updated", NEWER, ["Updated kitden"])

    def start_page(launcher, value):
        started.append((launcher, value))

    with update_page(tmp_path, upgrade=upgrade, start_page=start_page) as page:
        session = page.cookies.get("kitden_session_47800")
        assert page.post("/api/update", headers=POST).status_code == 202
        assert (view(page)["state"], view(page)["step"]) == ("running", 0)
        assert page.post("/api/update", headers=POST).status_code == 409
        assert page.app.state.activity.busy()
        gates[0].set()
        until(lambda: view(page)["step"] == 1)
        assert not page.app.state.activity.handed_over()
        gates[1].set()
        until(lambda: view(page)["state"] == "done")
        assert view(page)["step"] == 2
        assert started == [(UV.launcher, f"47800:tok:{session}")]
        assert page.app.state.activity.handed_over()
        marker = json.loads((data_dir(page.home) / "updated.json").read_text())
        assert (marker["version"], marker["launcher"]) == (NEWER, str(UV.launcher))
        assert page.post("/api/update", headers=POST).status_code == 409


def test_already_up_to_date_starts_nothing(tmp_path):
    async def upgrade(install, on_step, before):
        return Outcome("same", __version__, ["Nothing to upgrade"])

    with update_page(tmp_path, upgrade=upgrade) as page:
        assert page.post("/api/update", headers=POST).status_code == 202
        until(lambda: view(page)["state"] == "same")
        assert view(page)["tail"] == ["Nothing to upgrade"]
        assert not page.app.state.activity.handed_over()
        assert not page.app.state.activity.busy()
        assert not (data_dir(page.home) / "updated.json").exists()


def test_a_failed_update_keeps_the_page_and_can_be_tried_again(tmp_path):
    runs = []

    async def upgrade(install, on_step, before):
        runs.append(before)
        return Outcome("failed", None, ["error: no network"])

    with update_page(tmp_path, upgrade=upgrade) as page:
        assert page.post("/api/update", headers=POST).status_code == 202
        until(lambda: view(page)["state"] == "failed")
        assert view(page)["tail"] == ["error: no network"]
        assert not page.app.state.activity.handed_over()
        assert page.post("/api/update", headers=POST).status_code == 202
        until(lambda: len(runs) == 2)


def test_a_new_page_that_cannot_start_is_a_failure(tmp_path):
    async def upgrade(install, on_step, before):
        return Outcome("updated", NEWER, ["Updated kitden"])

    def start_page(launcher, value):
        raise FileNotFoundError(f"No such file: {launcher}")

    with update_page(tmp_path, upgrade=upgrade, start_page=start_page) as page:
        assert page.post("/api/update", headers=POST).status_code == 202
        until(lambda: view(page)["state"] == "failed")
        assert view(page)["tail"][-1] == f"No such file: {UV.launcher}"
        assert not page.app.state.activity.handed_over()


def test_the_update_answers_before_the_first_scan(tmp_path):
    """The browser asks the new page for its version while that page still scans."""
    gate = threading.Event()

    def slow_build(**options):
        gate.wait(5)
        return Inventory()

    home = tmp_path / "home"
    home.mkdir()
    app = create_app(
        slow_build, token="tok", port=47800, home=home, first_scan_later=True, fetch=offline
    )
    try:
        with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
            page.get("/?token=tok")
            asked = time.monotonic()
            assert page.get("/api/update").json()["version"] == __version__
            assert time.monotonic() - asked < 2
            gate.set()
    finally:
        gate.set()
