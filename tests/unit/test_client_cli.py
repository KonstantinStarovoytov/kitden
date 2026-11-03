"""Finding a client's command: PATH first, then the places its app or installer puts it."""

import shutil

import kitden.system
from kitden.changes.client_cli import find_command


def test_codex_inside_the_chatgpt_app_is_found_when_it_is_not_on_path(
    tmp_path, monkeypatch, system
):
    system("mac")
    bundled = tmp_path / "ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("#!/bin/sh\n")
    bundled.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setitem(kitden.system.MAC_APP_COMMANDS, "codex", (str(bundled),))
    assert find_command("codex", tmp_path / "home") == str(bundled)


def test_an_unknown_command_is_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert find_command("nothing", tmp_path) is None


def test_a_command_that_times_out_is_stopped_with_its_children(tmp_path, monkeypatch):
    # A client command can start a helper that keeps the output pipes open; when the command
    # times out, the whole group goes, so nothing keeps holding them.
    import os
    import time

    from kitden.changes import client_cli

    monkeypatch.setattr(client_cli, "TIMEOUT_SECONDS", 1.0)
    pid_file = tmp_path / "child.pid"
    script = f"sleep 60 & echo $! > {pid_file}; sleep 60"
    started = time.monotonic()
    result = client_cli.CommandRunner(tmp_path)(["sh", "-c", script], None)
    assert result.returncode != 0
    assert time.monotonic() - started < 10
    child = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        os.kill(child, 9)
        raise AssertionError("the child of a timed-out command was left running")


def test_a_command_never_reads_the_page_input(tmp_path):
    # A command that asks a question must not wait on, or eat, what the page reads.
    import os

    from kitden.changes import client_cli

    read_end, write_end = os.pipe()
    os.write(write_end, b"yes\n")
    os.close(write_end)
    saved = os.dup(0)
    os.dup2(read_end, 0)
    try:
        result = client_cli.CommandRunner(tmp_path)(["sh", "-c", "read line && echo got"], None)
    finally:
        os.dup2(saved, 0)
        os.close(saved)
        os.close(read_end)
    assert "got" not in result.output
