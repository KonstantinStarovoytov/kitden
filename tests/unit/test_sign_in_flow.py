"""The browser sign-in flow (Part 3b), run against a local fake OAuth server."""

import asyncio
import json

import pytest

from kitden import sign_in
from kitden.changes.actions import SIGN_IN_LATER
from kitden.sign_in import SignIns
from tests.unit.fake_oauth import FakeOAuth, back_query, browser

pytestmark = pytest.mark.anyio

REDIRECT = "http://127.0.0.1:47800/sign-in/done"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fake():
    server = FakeOAuth()
    yield server
    server.stop()


def oauth():
    from kitden.local_gateway import oauth as module

    return module


class Browser:
    """Records the addresses Kitden opens; `back()` gives where the last one sends the person."""

    def __init__(self):
        self.opened = []

    def __call__(self, url):
        self.opened.append(url)

    def back(self):
        return back_query(browser(self.opened[-1]))


async def test_sign_in_finishes(fake):
    signins, opened = SignIns(), Browser()
    record = signins.get(signins.offer(fake.url, "neon"))
    await oauth().start(record, REDIRECT, opened)
    assert "code_challenge_method=S256" in opened.opened[0]
    assert "resource=" in opened.opened[0]
    query = await asyncio.to_thread(opened.back)
    assert oauth().finish(signins, query) is True
    assert await oauth().wait(record) == {"state": "done"}
    done = signins.signed(record.id, fake.url)
    assert done.access_token in fake.issued
    stored = json.loads(done.secret)
    assert stored["tokens"]["access_token"] == done.access_token
    assert stored["expires_at"] is not None
    assert stored["client"]["client_id"].startswith("client-")


async def test_offer_gives_one_id_per_address(fake):
    signins = SignIns()
    assert signins.offer(fake.url, "neon") == signins.offer(fake.url, "neon")
    assert signins.offer(fake.url, "neon") != signins.offer(fake.base + "/other", "neon")
    assert signins.signed(signins.offer(fake.url, "neon"), fake.url) is None


async def test_no_registration_cannot_sign_in():
    fake = FakeOAuth(no_registration=True)
    try:
        signins, opened = SignIns(), Browser()
        record = signins.get(signins.offer(fake.url, "neon"))
        with pytest.raises(oauth().CannotSignIn) as refused:
            await oauth().start(record, REDIRECT, opened)
        assert str(refused.value) == SIGN_IN_LATER.format(name="neon")
        assert opened.opened == []
    finally:
        fake.stop()


async def test_cancel_ends_the_wait(fake):
    signins, opened = SignIns(), Browser()
    record = signins.get(signins.offer(fake.url, "neon"))
    await oauth().start(record, REDIRECT, opened)
    oauth().cancel(record)
    assert await oauth().wait(record) == {"state": "cancelled", "detail": "Sign-in was cancelled."}


async def test_denied_or_unknown_callback():
    fake = FakeOAuth(deny=True)
    try:
        signins, opened = SignIns(), Browser()
        record = signins.get(signins.offer(fake.url, "neon"))
        await oauth().start(record, REDIRECT, opened)
        assert oauth().finish(signins, {"state": "nope", "code": "x"}) is False
        query = await asyncio.to_thread(opened.back)
        assert "error" in query
        assert oauth().finish(signins, query) is True
        answer = await oauth().wait(record)
        assert answer == {"state": "failed", "detail": "neon did not finish sign-in."}
    finally:
        fake.stop()


async def test_two_flows_get_their_own_callbacks(fake):
    other = FakeOAuth()
    try:
        signins = SignIns()
        first, second = Browser(), Browser()
        one = signins.get(signins.offer(fake.url, "one"))
        two = signins.get(signins.offer(other.url, "two"))
        await oauth().start(one, REDIRECT, first)
        await oauth().start(two, REDIRECT, second)
        assert oauth().finish(signins, await asyncio.to_thread(second.back))
        assert oauth().finish(signins, await asyncio.to_thread(first.back))
        assert await oauth().wait(one) == {"state": "done"}
        assert await oauth().wait(two) == {"state": "done"}
        assert signins.signed(one.id, fake.url).access_token in fake.issued
        assert signins.signed(two.id, other.url).access_token in other.issued
    finally:
        other.stop()


async def test_times_out(fake, monkeypatch):
    monkeypatch.setattr(sign_in, "TIMEOUT", 0.2)
    signins, opened = SignIns(), Browser()
    record = signins.get(signins.offer(fake.url, "neon"))
    await oauth().start(record, REDIRECT, opened)
    answer = await oauth().wait(record)
    assert answer == {"state": "failed", "detail": "Sign-in did not finish in 5 minutes."}


async def test_no_secret_in_reasons():
    fake = FakeOAuth(token_error_body='{"error":"x","token":"SENTINEL_SECRET"}')
    try:
        signins, opened = SignIns(), Browser()
        record = signins.get(signins.offer(fake.url, "neon"))
        await oauth().start(record, REDIRECT, opened)
        oauth().finish(signins, await asyncio.to_thread(opened.back))
        answer = await oauth().wait(record)
        assert answer["state"] == "failed"
        assert "SENTINEL" not in json.dumps(answer)
        assert "SENTINEL" not in repr(record)
    finally:
        fake.stop()


async def test_the_sdks_error_text_never_reaches_the_log(capfd):
    """The SDK logs a failed flow with its exception, which may hold a token response."""
    import logging

    fake = FakeOAuth(token_error_body='{"error":"x","token":"SENTINEL_SECRET_LOG"}')
    root = logging.getLogger()
    handler = logging.StreamHandler()  # to stderr, as a terminal would show it
    root.addHandler(handler)
    try:
        signins, opened = SignIns(), Browser()
        record = signins.get(signins.offer(fake.url, "neon"))
        await oauth().start(record, REDIRECT, opened)
        oauth().finish(signins, await asyncio.to_thread(opened.back))
        await oauth().wait(record)
    finally:
        root.removeHandler(handler)
        fake.stop()
    out, err = capfd.readouterr()
    assert "SENTINEL" not in out + err
    assert "OAuth flow error" not in out + err
