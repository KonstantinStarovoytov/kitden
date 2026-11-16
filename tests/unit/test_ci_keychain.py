"""`ci_keychain` of test_real_secrets.py: the real Keychain tests take only the keychain the
nightly made for the run, never a login keychain. That file is skipped without the real store,
so its refusal is proven here. Only paths are checked; no tool is run."""

import tempfile

import pytest

from tests.unit.test_real_secrets import ci_keychain

NAME = "kitden-ci.keychain-db"


@pytest.fixture
def temp(tmp_path, monkeypatch):
    """A temp folder of its own, and no RUNNER_TEMP: the sandbox's tmp_path is under the real
    temp folder, so an "outside" path must be made outside this one."""
    folder = tmp_path / "temp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(folder))
    monkeypatch.delenv("RUNNER_TEMP", raising=False)
    return folder


def named(monkeypatch, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_symlink():
        path.write_text("")
    monkeypatch.setenv("KITDEN_CI_KEYCHAIN", str(path))


def refused(match):
    return pytest.raises(pytest.fail.Exception, match=match)


def test_the_runs_keychain_under_a_temp_folder_is_taken(temp, monkeypatch):
    named(monkeypatch, temp / "run" / NAME)
    assert ci_keychain() == (temp / "run" / NAME).resolve()


def test_a_keychain_outside_a_temp_folder_is_refused(temp, tmp_path, monkeypatch):
    named(monkeypatch, tmp_path / "Library/Keychains" / NAME)
    with refused("under a temp folder"):
        ci_keychain()


def test_a_keychain_with_another_name_is_refused(temp, monkeypatch):
    named(monkeypatch, temp / "login.keychain-db")
    with refused("named kitden-ci.keychain-db"):
        ci_keychain()


def test_a_link_in_the_temp_folder_to_a_keychain_outside_is_refused(temp, tmp_path, monkeypatch):
    outside = tmp_path / "Library/Keychains" / NAME
    named(monkeypatch, outside)
    link = temp / NAME
    link.symlink_to(outside)
    named(monkeypatch, link)
    with refused("under a temp folder"):
        ci_keychain()


def test_runner_temp_counts_as_a_temp_folder(temp, tmp_path, monkeypatch):
    runner = tmp_path / "runner-temp"
    monkeypatch.setenv("RUNNER_TEMP", str(runner))
    named(monkeypatch, runner / NAME)
    assert ci_keychain() == (runner / NAME).resolve()


def test_a_right_name_under_a_temp_folder_that_is_no_file_is_refused(temp, monkeypatch):
    monkeypatch.setenv("KITDEN_CI_KEYCHAIN", str(temp / "run" / NAME))
    with refused("names no file"):
        ci_keychain()


def test_no_keychain_named_is_refused(temp, monkeypatch):
    monkeypatch.delenv("KITDEN_CI_KEYCHAIN", raising=False)
    with refused("KITDEN_CI_KEYCHAIN is not set"):
        ci_keychain()
