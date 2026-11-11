"""The latest Kitden version: asked once a day, never an error."""

import http.client
import json
import os
import stat
from datetime import UTC, datetime, timedelta

from kitden.gateways import data_dir
from kitden.update.check import PYPI_URL, TAP_URL, cached_latest, latest_version, newer

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)


def _pypi(version: str) -> bytes:
    return json.dumps({"info": {"version": version}}).encode()


def _down(url):
    raise OSError("offline")


def test_pypi_stable_version():
    assert latest_version("uv", lambda url: _pypi("0.7.3")) == "0.7.3"


def test_each_method_asks_its_own_address():
    seen = []
    latest_version("uv", lambda url: seen.append(url) or _pypi("0.7.3"))
    latest_version("brew", lambda url: seen.append(url) or b"")
    assert seen == [PYPI_URL, TAP_URL]


def test_prerelease_is_ignored():
    assert latest_version("uv", lambda url: _pypi("0.8.0rc1")) is None


def test_brew_reads_the_tap_formula():
    rb = b'url "https://files.pythonhosted.org/packages/xx/kitden-0.7.2.tar.gz"'
    assert latest_version("brew", lambda url: rb) == "0.7.2"


def test_offline_gives_none():
    assert latest_version("uv", _down) is None


def test_a_dropped_connection_gives_none(tmp_path):
    def cut(url):
        raise http.client.IncompleteRead(b"")

    def garbled(url):
        raise http.client.BadStatusLine("x")

    for fetch in (cut, garbled):
        assert latest_version("uv", fetch) is None
        assert cached_latest(tmp_path, "uv", NOW, fetch) is None


def test_odd_answers_give_none():
    assert latest_version("uv", lambda url: b"not json") is None
    assert latest_version("uv", lambda url: b'{"info": {}}') is None
    assert latest_version("uv", lambda url: b"[]") is None
    assert latest_version("brew", lambda url: b"no url here") is None
    assert latest_version("pip", lambda url: _pypi("0.7.3")) is None


def test_newer():
    assert newer("0.7.2", "0.7.10")
    assert not newer("0.7.3", "0.7.3")
    assert not newer("0.7.3", "0.7.2")
    assert not newer("0.7.3", None)
    assert not newer("0.7.3.dev1", "0.7.4")  # a version Kitden cannot read is never offered


def test_checks_at_most_once_a_day(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return _pypi("0.7.3")

    assert cached_latest(tmp_path, "uv", NOW, fetch) == "0.7.3"
    assert cached_latest(tmp_path, "uv", NOW + timedelta(hours=23), fetch) == "0.7.3"
    assert len(calls) == 1
    assert cached_latest(tmp_path, "uv", NOW + timedelta(hours=25), fetch) == "0.7.3"
    assert len(calls) == 2


def test_a_new_method_asks_again(tmp_path):
    calls = []
    cached_latest(tmp_path, "uv", NOW, lambda url: calls.append(url) or _pypi("0.7.3"))
    cached_latest(tmp_path, "brew", NOW, lambda url: calls.append(url) or b"kitden-0.7.2.tar.gz")
    assert len(calls) == 2


def test_offline_is_remembered_for_a_day(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        raise OSError("offline")

    assert cached_latest(tmp_path, "uv", NOW, fetch) is None
    assert cached_latest(tmp_path, "uv", NOW + timedelta(hours=1), fetch) is None
    assert len(calls) == 1
    assert cached_latest(tmp_path, "uv", NOW + timedelta(hours=25), fetch) is None
    assert len(calls) == 2


def test_the_record_is_private(tmp_path):
    cached_latest(tmp_path, "uv", NOW, lambda url: _pypi("0.7.3"))
    path = data_dir(tmp_path) / "update.json"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert json.loads(path.read_text())["latest"] == "0.7.3"
    assert [p.name for p in path.parent.iterdir()] == ["update.json"]  # no temp file left


def test_a_broken_record_counts_as_never_checked(tmp_path):
    path = data_dir(tmp_path) / "update.json"
    path.parent.mkdir(parents=True)
    for text in ("{broken", "[]", '{"checked": 5, "method": "uv", "latest": "0.7.3"}', ""):
        path.write_text(text)
        assert cached_latest(tmp_path, "uv", NOW, lambda url: _pypi("0.7.4")) == "0.7.4"


def test_a_failed_save_does_not_raise(tmp_path):
    folder = data_dir(tmp_path)
    folder.parent.mkdir(parents=True)
    folder.write_text("a file where the folder should be")
    assert cached_latest(tmp_path, "uv", NOW, lambda url: _pypi("0.7.3")) == "0.7.3"
