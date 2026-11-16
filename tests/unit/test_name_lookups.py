"""Tests never look a name up in the real DNS and never connect outside this computer
(`name_lookups` in tests/conftest.py), so no answer depends on the runner's network."""

import asyncio
import contextlib
import http.client
import ipaddress
import socket
import urllib.request

import pytest

from tests.conftest import PUBLIC_ADDRESS, PUBLIC_ADDRESS_V6, guarded_lookups


def _addresses(host, family=0):
    return {info[4][0] for info in socket.getaddrinfo(host, 443, family, socket.SOCK_STREAM)}


def test_a_name_gets_the_public_answer_never_the_real_one():
    # A name the real DNS knows, and one it never knows: both get the fixed answer.
    assert _addresses("github.com") == {PUBLIC_ADDRESS}
    assert _addresses("nothing-here.invalid") == {PUBLIC_ADDRESS}
    assert _addresses(b"GitHub.com.") == {PUBLIC_ADDRESS}
    assert socket.gethostbyname("github.com") == PUBLIC_ADDRESS
    # Asked for IPv6 only, the name still gets a public answer, not "does not resolve".
    assert _addresses("github.com", socket.AF_INET6) == {PUBLIC_ADDRESS_V6}
    assert ipaddress.ip_address(PUBLIC_ADDRESS_V6).is_global
    assert ipaddress.ip_address(PUBLIC_ADDRESS).is_global
    assert socket.gethostbyname_ex("github.com") == ("github.com", [], [PUBLIC_ADDRESS])
    # The event loop asks the same lookup, so httpx, anyio and asyncio get it too.
    assert asyncio.run(_loop_lookup("github.com")) == {PUBLIC_ADDRESS}


async def _loop_lookup(host):
    found = await asyncio.get_running_loop().getaddrinfo(host, 443)
    return {info[4][0] for info in found}


def test_a_test_sets_the_answer_it_needs(name_lookups):
    name_lookups["inside.example"] = "10.0.0.5"
    name_lookups["v6.example"] = "fd00::1"
    name_lookups["gone.example"] = None
    assert _addresses("inside.example") == {"10.0.0.5"}
    assert _addresses("Inside.Example.") == {"10.0.0.5"}
    assert _addresses("v6.example") == {"fd00::1"}
    with pytest.raises(socket.gaierror, match="does not resolve"):
        socket.getaddrinfo("gone.example", 443)
    with pytest.raises(socket.gaierror):
        socket.gethostbyname("gone.example")


def test_addresses_and_localhost_resolve_as_usual():
    assert _addresses("127.1") == {"127.0.0.1"}
    assert _addresses("2130706433") == {"127.0.0.1"}
    assert _addresses("10.1.2.3") == {"10.1.2.3"}
    assert _addresses("::1") == {"::1"}
    assert _addresses(None) <= {"127.0.0.1", "::1"}
    assert _addresses("localhost") <= {"127.0.0.1", "::1"}


@pytest.mark.parametrize(
    "connect",
    [
        lambda: socket.create_connection(("github.com", 443), timeout=5),
        lambda: socket.create_connection((PUBLIC_ADDRESS, 443), timeout=5),
        lambda: socket.create_connection(("10.0.0.5", 443), timeout=5),
        lambda: _plain_connect(("github.com", 443)),
        lambda: urllib.request.urlopen("https://github.com", timeout=5),
        lambda: http.client.HTTPSConnection("github.com", timeout=5).connect(),
        lambda: asyncio.run(asyncio.open_connection("github.com", 443)),
    ],
    ids=["by name", "by address", "private address", "plain socket", "urllib", "http", "asyncio"],
)
def test_a_connection_outside_this_computer_is_refused(connect, name_lookups):
    with pytest.raises(OSError, match="does not connect outside this computer"):
        connect()
    assert name_lookups.refused
    # Here the refusal is what the test checks; in any other test it fails the test (below).
    name_lookups.refused.clear()


def _plain_connect(address):
    with socket.socket() as sock:
        sock.connect(address)


def test_a_refused_connection_fails_the_test_even_when_the_code_swallows_the_error(monkeypatch):
    # What the fixture runs for a test that is not a contract or browser test.
    steps = guarded_lookups(monkeypatch)
    answers = next(steps)
    # Code that takes any network error as "could not reach" swallows the refusal...
    with contextlib.suppress(OSError):
        socket.create_connection(("github.com", 443), timeout=5)
    # ...and the test still fails when it ends.
    with pytest.raises(pytest.fail.Exception, match="tried to connect outside this computer"):
        next(steps)
    assert answers.refused == [(PUBLIC_ADDRESS, 443)]


def test_connect_ex_is_refused_too(name_lookups):
    with socket.socket() as sock:
        assert sock.connect_ex((PUBLIC_ADDRESS, 443)) != 0
    assert name_lookups.refused == [(PUBLIC_ADDRESS, 443)]
    name_lookups.refused.clear()


def test_a_connection_on_this_computer_still_works():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        with socket.create_connection(("localhost", port), timeout=5):
            pass
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            pass
