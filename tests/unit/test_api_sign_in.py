"""Browser sign-in through the page (Part 3b): the preview offers it, the page runs it, Apply
keeps the tokens in the Keychain only. Against the local fake OAuth server, never a real one."""

import json
from contextlib import contextmanager
from urllib.parse import urlsplit

import pytest
from starlette.testclient import TestClient

from kitden.changes.actions import SIGN_IN_LATER
from kitden.gateways import data_dir
from kitden.local_gateway.keychain import references_in
from kitden.local_gateway.settings import load_settings
from kitden.web.app import create_app
from tests.unit.fake_oauth import FakeOAuth, browser
from tests.unit.test_local_gateway_move import (
    KITDEN,
    ORIGIN,
    POST,
    FakeClaude,
    add_claude,
    batch_move,
    build_inventory,
    gateway_file,
    keychain_items,
)
from tests.unit.test_local_gateway_move import home as home  # noqa: F401 - the fixture


class Opened(list):
    """The stand-in for opening the browser: it keeps each address."""

    def __call__(self, url):
        self.append(url)


@contextmanager
def page_for(home, opened):
    app = create_app(
        lambda: build_inventory(home),
        token="tok",
        port=47800,
        home=home,
        run=FakeClaude(home),
        setup_command=lambda: KITDEN,
        open_browser=opened,
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        yield page


@pytest.fixture
def fake():
    server = FakeOAuth()
    yield server
    server.stop()


def come_back(page, opened):
    """The browser signs in and comes back to Kitden's page."""
    location = urlsplit(browser(opened[-1]))
    return page.get(f"{location.path}?{location.query}")


def sign_in(page, opened, id):
    started = page.post("/api/sign-in/start", json={"id": id}, headers=POST)
    assert started.status_code == 200, started.text
    back = come_back(page, opened)
    assert back.status_code == 200 and "Signed in." in back.text
    waited = page.post("/api/sign-in/wait", json={"id": id}, headers=POST)
    assert waited.json() == {"state": "done"}


def test_preview_offers_sign_in(home, fake):
    add_claude(home, "signer", {"type": "http", "url": fake.url})
    with page_for(home, Opened()) as page:
        answer = batch_move(page, home, "signer")
    assert answer.status_code == 422
    needs = answer.json()["needs"]
    assert needs["kind"] == "sign-in" and needs["sign_in"]
    assert needs["reason"] == "signer needs sign-in."
    assert fake.url not in answer.text


def test_sign_in_joins_the_preview_and_applies(home, fake, fake_keychain):
    add_claude(home, "signer", {"type": "http", "url": fake.url})
    opened = Opened()
    with page_for(home, opened) as page:
        id = batch_move(page, home, "signer").json()["needs"]["sign_in"]
        sign_in(page, opened, id)
        answer = batch_move(page, home, "signer", {"sign_in": id})
        assert answer.status_code == 200, answer.text
        [token] = fake.issued
        assert token not in answer.text
        change_id = answer.json()["id"]
        applied = page.post(f"/api/changes/{change_id}/apply", headers=POST)
        assert applied.json()["state"] == "verified", applied.json()
        held = load_settings(home)["servers"]["signer"]
        assert held == {"url": fake.url, "sign_in": {"keychain": "signer/sign-in"}}
        stored = json.loads(keychain_items(fake_keychain)["kitden signer/sign-in"])
        assert stored["tokens"]["access_token"] == token
        assert token not in gateway_file(home).read_text()
        folder = data_dir(home) / "changes" / change_id
        assert all(token not in p.read_text() for p in folder.rglob("*.json"))
        log = data_dir(home) / "changes.log"
        assert not log.exists() or token not in log.read_text()
        undone = page.post(f"/api/changes/{change_id}/undo", headers=POST)
        assert undone.status_code == 200, undone.text
        assert keychain_items(fake_keychain) == {}


def test_unknown_sign_in_id_waits_again(home, fake):
    add_claude(home, "signer", {"type": "http", "url": fake.url})
    with page_for(home, Opened()) as page:
        answer = batch_move(page, home, "signer", {"sign_in": "gone"})
    assert answer.status_code == 422
    body = answer.json()
    assert body["needs"]["kind"] == "sign-in"
    assert body["detail"] == "Sign in again: that sign-in is no longer here."


def test_refused_sign_in(home, fake):
    add_claude(home, "signer", {"type": "http", "url": fake.url})
    opened = Opened()
    with page_for(home, opened) as page:
        id = batch_move(page, home, "signer").json()["needs"]["sign_in"]
        sign_in(page, opened, id)
        fake.issued.clear()
        answer = batch_move(page, home, "signer", {"sign_in": id})
    assert answer.status_code == 422
    assert answer.json()["detail"] == "signer did not accept this sign-in."


def test_cannot_sign_in_offers_the_token_field(home):
    fake = FakeOAuth(no_registration=True)
    try:
        add_claude(home, "signer", {"type": "http", "url": fake.url})
        opened = Opened()
        with page_for(home, opened) as page:
            needs = batch_move(page, home, "signer").json()["needs"]
            started = page.post("/api/sign-in/start", json={"id": needs["sign_in"]}, headers=POST)
        assert started.status_code == 422
        assert started.json() == {"detail": SIGN_IN_LATER.format(name="signer"), "cannot": True}
        assert needs["fields"][0]["name"] == "Authorization"
        assert opened == []
    finally:
        fake.stop()


def test_cancel_and_unknown_ids(home, fake):
    add_claude(home, "signer", {"type": "http", "url": fake.url})
    opened = Opened()
    with page_for(home, opened) as page:
        id = batch_move(page, home, "signer").json()["needs"]["sign_in"]
        page.post("/api/sign-in/start", json={"id": id}, headers=POST)
        assert page.post("/api/sign-in/cancel", json={"id": id}, headers=POST).status_code == 200
        waited = page.post("/api/sign-in/wait", json={"id": id}, headers=POST)
        assert waited.json() == {"state": "cancelled", "detail": "Sign-in was cancelled."}
        for verb in ("start", "wait", "cancel"):
            gone = page.post(f"/api/sign-in/{verb}", json={"id": "nope"}, headers=POST)
            assert gone.status_code == 404


def test_callback_page_needs_no_cookie(home):
    with page_for(home, Opened()) as page:
        app = page.app
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as stranger:
        back = stranger.get("/sign-in/done?state=unknown&code=x")
        assert back.status_code == 200
        assert (
            "Sign-in did not finish. You can close this tab and try again in Kitden." in back.text
        )
        assert back.headers["cache-control"] == "no-store"
        started = stranger.post("/api/sign-in/start", json={"id": "x"}, headers=POST)
        assert started.status_code == 401


def test_demo_refuses_sign_in(tmp_path):
    from kitden.demo import demo_build
    from kitden.demo.sample import build_demo_home

    home = build_demo_home(tmp_path, "medium")
    app = create_app(demo_build(home), token="tok", port=47800, home=home, demo=True)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as page:
        page.get("/?token=tok")
        answer = page.post("/api/sign-in/start", json={"id": "x"}, headers=POST)
    assert answer.status_code == 422


def test_references_in_counts_sign_in():
    entry = {"url": "https://x", "sign_in": {"keychain": "x/sign-in"}, "headers": {"A": "b"}}
    assert references_in(entry) == [{"keychain": "x/sign-in"}]


def test_removing_a_held_sign_in_server_keeps_its_item_for_undo(home, fake, fake_keychain):
    """As with any secret of a removed server: the item stays, so Undo brings the server back."""
    add_claude(home, "signer", {"type": "http", "url": fake.url})
    opened = Opened()
    with page_for(home, opened) as page:
        id = batch_move(page, home, "signer").json()["needs"]["sign_in"]
        sign_in(page, opened, id)
        change_id = batch_move(page, home, "signer", {"sign_in": id}).json()["id"]
        page.post(f"/api/changes/{change_id}/apply", headers=POST)
        body = {"action": "gateway.remove", "targets": [], "params": {"server": "signer"}}
        removed = page.post("/api/changes/preview", json=body, headers=POST)
        assert removed.status_code == 200, removed.text
        assert "Its secrets stay in your Keychain under kitden." in removed.text
        applied = page.post(f"/api/changes/{removed.json()['id']}/apply", headers=POST)
        assert applied.json()["state"] == "verified", applied.json()
        assert "kitden signer/sign-in" in keychain_items(fake_keychain)
