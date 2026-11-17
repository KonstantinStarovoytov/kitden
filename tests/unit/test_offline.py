"""The offline stand-ins the browser tests and the README pictures share (tests/offline.py)."""

import json

import pytest

from kitden import discovery
from tests.offline import CATALOG, REGISTRY, STAND_INS, canned_download


def test_every_stand_in_replaces_a_name_that_exists():
    # A stand-in for a name nothing reads stands in for nothing.
    for module, name, _ in STAND_INS:
        assert hasattr(module, name), f"{module.__name__}.{name}"


def test_an_address_not_in_the_tables_is_refused():
    with pytest.raises(OSError):
        canned_download("https://skills.sh/api/search?q=other&limit=30")


def test_weather_has_more_than_one_page_of_active_servers():
    answer = json.loads(canned_download(f"{REGISTRY}?search=weather&version=latest&limit=100"))
    active = [
        record
        for record in answer["servers"]
        if record["_meta"]["io.modelcontextprotocol.registry/official"]["status"] == "active"
    ]
    assert len(active) == 65 > discovery.PAGE


def test_the_add_panels_first_read_has_an_answer():
    assert f"{REGISTRY}?search=&version=latest&limit=100" in CATALOG
