"""Flow 3: search a catalog, "Show 5 more", and open a found item's details. The catalog
answers from tests/offline.py: 65 servers for "weather", one page is 60."""

import socket

import pytest

from tests.conftest import PUBLIC_ADDRESS

pytestmark = pytest.mark.browser


def test_the_sample_has_the_network_guard_on(sample):
    """Every outside name resolves to an address nothing reaches, and a test that connects to
    it fails at its end (tests/conftest.py, guarded_lookups)."""
    assert socket.getaddrinfo("pypi.org", 443)[0][4][0] == PUBLIC_ADDRESS
