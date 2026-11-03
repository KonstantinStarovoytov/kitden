"""The Access block of a held server: its secrets by name, only their start and end shown, and
one change kind to replace or remove one (or sign out). Sandbox home and fake Keychain only."""

import json
import time

import pytest

from kitden.local_gateway.views import access_rows, masked
from tests.unit.test_api_sign_in import Opened, held_signer, page_for, sign_in  # noqa: F401
from tests.unit.test_local_gateway_move import (
    POST,
    FakeRemote,
    gateway_file,
    keychain_items,
    stop,
)
from tests.unit.test_local_gateway_move import home as home  # noqa: F401 - the fixture


def write_held(home, servers):
    path = gateway_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"servers": servers, "rules": {}}))


def keep(items_file, account, value):
    data = json.loads(items_file.read_text()) if items_file.exists() else {}
    data[f"kitden {account}"] = value
    items_file.write_text(json.dumps(data))


def test_masked_shows_only_the_start_and_the_end():
    assert masked("Bearer sk-abcdefghijklmnop1234") == "Bearer sk-a…1234"
    assert masked("abcdefghijkl") == "abcd…ijkl"
    assert masked("short") == "••••"
    assert masked("") == "••••"


def test_access_rows_name_each_secret_and_hide_the_rest(fake_keychain):
    keep(fake_keychain, "neon/Authorization", "Bearer SENTINEL_SECRET_1234567890")
    entry = {
        "url": "https://x/mcp",
        "headers": {"Authorization": {"keychain": "neon/Authorization"}, "X-Mode": "fast"},
    }
    rows = access_rows("neon", entry)
    assert rows == [
        {
            "field": "headers",
            "name": "Authorization",
            "masked": "Bearer SENT…7890",
            "stored": "keychain",
        }
    ]
    assert "SENTINEL_SECRET_1234567890" not in json.dumps(rows)


def test_access_rows_of_a_local_server_and_a_plain_secret(fake_keychain):
    entry = {"command": "uvx", "env": {"API_KEY": "SENTINEL_PLAIN_abcdefgh", "DEBUG": "1"}}
    rows = access_rows("tool", entry)
    assert rows == [
        {"field": "env", "name": "API_KEY", "masked": "SENT…efgh", "stored": "settings"}
    ]


def test_access_rows_of_a_sign_in(fake_keychain):
    ends = time.time() + 3000
    value = {
        "tokens": {"access_token": "access-0123456789abcdef", "refresh_token": "r"},
        "expires_at": ends,
        "client": {},
    }
    keep(fake_keychain, "neon/sign-in", json.dumps(value))
    rows = access_rows("neon", {"url": "https://x/mcp", "sign_in": {"keychain": "neon/sign-in"}})
    assert rows == [
        {
            "field": "sign_in",
            "name": "Sign-in",
            "masked": "acce…cdef",
            "stored": "keychain",
            "ends": ends,
            "refresh": True,
        }
    ]


def test_a_missing_keychain_item_says_so(fake_keychain):
    rows = access_rows(
        "neon", {"url": "u", "headers": {"Authorization": {"keychain": "neon/Authorization"}}}
    )
    assert rows == [
        {"field": "headers", "name": "Authorization", "masked": None, "stored": "missing"}
    ]


def test_the_details_answer_carries_the_access_rows(home, fake_keychain):
    keep(fake_keychain, "neon/Authorization", "Bearer SENTINEL_SECRET_1234567890")
    write_held(
        home,
        {
            "neon": {
                "url": "https://x/mcp",
                "headers": {"Authorization": {"keychain": "neon/Authorization"}},
            }
        },
    )
    with page_for(home, Opened()) as page:
        answer = page.get("/api/gateway/tools?server=neon")
    assert answer.json()["access"][0]["masked"] == "Bearer SENT…7890"
    assert "SENTINEL_SECRET_1234567890" not in answer.text


def access(page, server, field, name, value=None):
    params = {"server": server, "field": field, "name": name, "value": value}
    return page.post(
        "/api/changes/preview",
        json={"action": "gateway.access", "targets": [], "params": params},
        headers=POST,
    )


def test_replace_a_token_checks_it_and_keeps_it_in_the_keychain(home, fake_keychain):
    remote = FakeRemote(401, token="SENTINEL_NEW")
    try:
        keep(fake_keychain, "neon/Authorization", "Bearer old")
        write_held(
            home,
            {
                "neon": {
                    "url": remote.url,
                    "headers": {"Authorization": {"keychain": "neon/Authorization"}},
                }
            },
        )
        with page_for(home, Opened()) as page:
            bad = access(page, "neon", "headers", "Authorization", "Bearer SENTINEL_WRONG")
            assert bad.status_code == 422
            assert bad.json()["detail"] == "neon did not accept this token."
            good = access(page, "neon", "headers", "Authorization", "Bearer SENTINEL_NEW")
            assert good.status_code == 200, good.text
            assert "SENTINEL_NEW" not in good.text
            applied = page.post(f"/api/changes/{good.json()['id']}/apply", headers=POST)
            assert applied.json()["state"] == "verified", applied.json()
        assert keychain_items(fake_keychain)["kitden neon/Authorization"] == "Bearer SENTINEL_NEW"
        assert "SENTINEL" not in gateway_file(home).read_text()
    finally:
        stop(remote)


def test_remove_a_token_and_undo_brings_it_back(home, fake_keychain):
    keep(fake_keychain, "neon/Authorization", "Bearer kept")
    entry = {
        "url": "https://x/mcp",
        "headers": {"Authorization": {"keychain": "neon/Authorization"}},
    }
    write_held(home, {"neon": entry})
    with page_for(home, Opened()) as page:
        answer = access(page, "neon", "headers", "Authorization")
        assert answer.status_code == 200, answer.text
        change = answer.json()["id"]
        assert page.post(f"/api/changes/{change}/apply", headers=POST).json()["state"] == "verified"
        assert json.loads(gateway_file(home).read_text())["servers"]["neon"] == {
            "url": "https://x/mcp"
        }
        # The item stays, so Undo brings the server back as it was.
        assert keychain_items(fake_keychain)["kitden neon/Authorization"] == "Bearer kept"
        assert page.post(f"/api/changes/{change}/undo", headers=POST).status_code == 200
        assert json.loads(gateway_file(home).read_text())["servers"]["neon"] == entry


def test_sign_out(home, fake_keychain):
    entry = {"url": "https://x/mcp", "sign_in": {"keychain": "neon/sign-in"}}
    write_held(home, {"neon": entry})
    with page_for(home, Opened()) as page:
        answer = access(page, "neon", "sign_in", "Sign-in")
        assert answer.status_code == 200, answer.text
        page.post(f"/api/changes/{answer.json()['id']}/apply", headers=POST)
    assert json.loads(gateway_file(home).read_text())["servers"]["neon"] == {"url": "https://x/mcp"}


def test_a_local_value_is_replaced_without_a_check(home, fake_keychain):
    write_held(home, {"tool": {"command": "uvx", "env": {"API_KEY": {"keychain": "tool/API_KEY"}}}})
    with page_for(home, Opened()) as page:
        answer = access(page, "tool", "env", "API_KEY", "SENTINEL_LOCAL")
        assert answer.status_code == 200, answer.text
        page.post(f"/api/changes/{answer.json()['id']}/apply", headers=POST)
    assert keychain_items(fake_keychain)["kitden tool/API_KEY"] == "SENTINEL_LOCAL"


@pytest.mark.parametrize(
    ("field", "name", "value", "words"),
    [
        ("headers", "Nope", None, "neon has no Nope."),
        ("sign_in", "Sign-in", "x", "Sign in again to change a sign-in."),
        ("args", "x", None, "Choose a value to change."),
        ("headers", "Authorization", "a\\nb", "Enter a valid access value again."),
    ],
)
def test_wrong_asks_are_refused(home, fake_keychain, field, name, value, words):
    write_held(home, {"neon": {"url": "https://x/mcp", "headers": {"Authorization": "Bearer x"}}})
    with page_for(home, Opened()) as page:
        answer = access(page, "neon", field, name, value.replace("\\n", "\n") if value else value)
    assert answer.status_code == 422
    assert answer.json()["detail"] == words


@pytest.mark.parametrize(
    ("name", "value"),
    [("Authorization", "Bearer SENTINEL_ADDED_TOKEN"), ("X-API-Key", "SENTINEL_ADDED_KEY")],
)
def test_add_access_to_a_server_that_had_none(home, fake_keychain, name, value):
    remote = FakeRemote(200)  # it answers without a token, so the token cannot be checked now
    try:
        write_held(home, {"docs": {"url": remote.url}})
        with page_for(home, Opened()) as page:
            answer = access(page, "docs", "headers", name, value)
            assert answer.status_code == 200, answer.text
            assert "SENTINEL" not in answer.text
            [step] = answer.json()["steps"]
            assert step["check_note"] == "docs answers without it, so its first call checks it."
            applied = page.post(f"/api/changes/{answer.json()['id']}/apply", headers=POST)
            assert applied.json()["state"] == "verified", applied.json()
        assert keychain_items(fake_keychain)[f"kitden docs/{name}"] == value
        entry = json.loads(gateway_file(home).read_text())["servers"]["docs"]
        assert entry == {"url": remote.url, "headers": {name: {"keychain": f"docs/{name}"}}}
    finally:
        stop(remote)


def test_a_checked_token_has_no_note(home, fake_keychain):
    remote = FakeRemote(401, token="SENTINEL_GOOD")
    try:
        write_held(home, {"docs": {"url": remote.url}})
        with page_for(home, Opened()) as page:
            answer = access(page, "docs", "headers", "Authorization", "Bearer SENTINEL_GOOD")
        assert answer.status_code == 200, answer.text
        assert answer.json()["steps"][0]["check_note"] is None
    finally:
        stop(remote)


def test_add_a_variable_to_a_local_server(home, fake_keychain):
    write_held(home, {"tool": {"command": "uvx"}})
    with page_for(home, Opened()) as page:
        answer = access(page, "tool", "env", "API_KEY", "SENTINEL_LOCAL_NEW")
        assert answer.status_code == 200, answer.text
        page.post(f"/api/changes/{answer.json()['id']}/apply", headers=POST)
    entry = json.loads(gateway_file(home).read_text())["servers"]["tool"]
    assert entry == {"command": "uvx", "env": {"API_KEY": {"keychain": "tool/API_KEY"}}}


@pytest.mark.parametrize(
    ("server", "field", "name", "words"),
    [
        ("neon", "headers", "Bad Name", "Use a header name of letters, digits and '-' only."),
        ("neon", "headers", "Host", "Kitden sets the Host header itself."),
        ("neon", "headers", "content-type", "Kitden sets the content-type header itself."),
        ("neon", "env", "API_KEY", "neon is a remote server: it takes a header, not a variable."),
        ("tool", "headers", "X-Key", "tool is a local server: it takes a variable, not a header."),
        ("tool", "env", "1KEY", "Use a variable name of letters, digits and '_' only."),
    ],
)
def test_a_wrong_new_name_is_refused(home, fake_keychain, server, field, name, words):
    write_held(home, {"neon": {"url": "https://x/mcp"}, "tool": {"command": "uvx"}})
    with page_for(home, Opened()) as page:
        answer = access(page, server, field, name, "value")
    assert answer.status_code == 422
    assert answer.json()["detail"] == words


def test_a_server_that_turned_down_a_call_needs_a_token_until_access_changes(home, fake_keychain):
    from kitden.local_gateway.settings import load_refused, mark_refused

    remote = FakeRemote(200)
    try:
        write_held(home, {"docs": {"url": remote.url}})
        mark_refused(home, "docs", True)
        with page_for(home, Opened()) as page:

            def needs():
                view = page.get("/api/gateway-view").json()
                [kitden] = [g for g in view["gateways"] if g["kind"] == "kitden"]
                [server] = [s for s in kitden["servers"] if s["name"] == "docs"]
                return server.get("needs")

            assert needs() == "token"
            answer = access(page, "docs", "headers", "Authorization", "Bearer SENTINEL_T")
            page.post(f"/api/changes/{answer.json()['id']}/apply", headers=POST)
            assert needs() is None
        assert load_refused(home) == {}
    finally:
        stop(remote)


def test_a_remote_without_a_sign_in_may_start_one(home, fake_keychain):
    write_held(home, {"docs": {"url": "https://x/mcp"}, "tool": {"command": "uvx"}})
    with page_for(home, Opened()) as page:
        remote = page.post("/api/sign-in/offer", json={"server": "docs"}, headers=POST)
        local = page.post("/api/sign-in/offer", json={"server": "tool"}, headers=POST)
    assert remote.status_code == 200 and remote.json()["id"]
    assert local.status_code == 404


def test_a_header_name_in_other_letters_replaces_the_one_held(home, fake_keychain):
    remote = FakeRemote(401, token="new")
    try:
        keep(fake_keychain, "neon/Authorization", "Bearer old")
        held = {"Authorization": {"keychain": "neon/Authorization"}}
        write_held(home, {"neon": {"url": remote.url, "headers": held}})
        with page_for(home, Opened()) as page:
            answer = access(page, "neon", "headers", "authorization", "Bearer new")
            assert answer.status_code == 200, answer.text
            page.post(f"/api/changes/{answer.json()['id']}/apply", headers=POST)
    finally:
        stop(remote)
    entry = json.loads(gateway_file(home).read_text())["servers"]["neon"]
    assert entry["headers"] == held
    assert keychain_items(fake_keychain)["kitden neon/Authorization"] == "Bearer new"


def test_a_removed_server_loses_its_needs_token_note(home, fake_keychain):
    from kitden.local_gateway.settings import load_refused, mark_refused

    write_held(home, {"docs": {"url": "https://x/mcp"}})
    mark_refused(home, "docs", True)
    with page_for(home, Opened()) as page:
        write_held(home, {})
        # Any verified Apply drops the notes of servers the gateway no longer holds.
        write_held(home, {"tool": {"command": "uvx"}})
        answer = access(page, "tool", "env", "API_KEY", "SENTINEL_X")
        page.post(f"/api/changes/{answer.json()['id']}/apply", headers=POST)
    assert load_refused(home) == {}


def test_two_new_values_for_one_server_in_one_preview_are_refused_plainly(home, fake_keychain):
    write_held(home, {"tool": {"command": "uvx"}})

    def row(id, name, value):
        params = {"server": "tool", "field": "env", "name": name, "value": value}
        return {"id": id, "kind": "gateway.access", "targets": [], "params": params, "title": id}

    with page_for(home, Opened()) as page:
        answer = page.post(
            "/api/batch/preview",
            json={"requests": [row("a", "API_KEY", "SENTINEL_A"), row("b", "OTHER", "SENTINEL_B")]},
            headers=POST,
        )
    # Each builds the whole entry, so the second waits until the first is applied.
    assert answer.status_code == 422
    assert "changes the same setting" in answer.json()["detail"]
    assert "SENTINEL" not in answer.text
