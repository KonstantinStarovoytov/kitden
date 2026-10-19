"""Finding a client's command: PATH first, then the places its app or installer puts it."""

import shutil

import kitden.clients.versions as versions
from kitden.changes.client_cli import find_command


def test_codex_inside_the_chatgpt_app_is_found_when_it_is_not_on_path(tmp_path, monkeypatch):
    bundled = tmp_path / "ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("#!/bin/sh\n")
    bundled.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setitem(versions._COMMANDS, "codex", ("codex", (str(bundled),)))
    assert find_command("codex", tmp_path / "home") == str(bundled)


def test_an_unknown_command_is_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert find_command("nothing", tmp_path) is None
