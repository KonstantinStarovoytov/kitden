"""The restart-needed strips: which clients still run from before an Apply."""

import json
import subprocess
from datetime import datetime

from starlette.testclient import TestClient

from kitden.gateways import data_dir
from kitden.system import process_starts
from kitden.views.inventory import Inventory
from kitden.views.restarts_view import pending_restarts
from kitden.web.app import create_app

ORIGIN = "http://127.0.0.1:47800"
CURSOR_NOTE = "Restart Cursor for this to take effect."
CODEX_NOTE = "Restart Codex (the app and any open CLI sessions) for this to take effect."
CURSOR_APP = "/Applications/Cursor.app/Contents/MacOS/Cursor"


def at(hour, minute=0):
    """A start time in this computer's own zone, as `ps` says it."""
    return datetime(2026, 11, 11, hour, minute).astimezone()


def applied_at(hour, minute=0):
    return at(hour, minute).isoformat()


def line(change, time, client="cursor", note=CURSOR_NOTE, state="verified"):
    step = {"client": client, "restart_note": note}
    return {"id": change, "time": time, "state": state, "steps": [step]}


def ps(*lines):
    def run(command, **options):
        assert command == ["ps", "-A", "-o", "lstart=,args="]
        assert options["env"]["LC_ALL"] == "C"
        return subprocess.CompletedProcess(command, 0, "\n".join(lines) + "\n", "")

    return run


# Reading `ps` --------------------------------------------------------------------------------


def test_reads_a_macos_line():
    run = ps(f"Tue Nov 11 09:15:02 2026 {CURSOR_APP} --flag")
    assert process_starts(run) == [
        (datetime(2026, 11, 11, 9, 15, 2).astimezone(), f"{CURSOR_APP} --flag")
    ]


def test_reads_a_linux_line_with_a_padded_day():
    run = ps("Tue Nov  3 08:01:59 2026 node /home/me/.local/bin/codex exec")
    assert process_starts(run) == [
        (datetime(2026, 11, 3, 8, 1, 59).astimezone(), "node /home/me/.local/bin/codex exec")
    ]


def test_skips_lines_it_cannot_read():
    run = ps("garbage", "", "Tue Nov 11 09:15:02 2026 codex")
    assert [args for _, args in process_starts(run)] == ["codex"]


def test_a_failed_ps_gives_nothing():
    def failed(command, **options):
        return subprocess.CompletedProcess(command, 1, "", "ps: no")

    def missing(command, **options):
        raise FileNotFoundError("ps")

    def slow(command, **options):
        raise subprocess.TimeoutExpired(command, 10)

    assert process_starts(failed) == []
    assert process_starts(missing) == []
    assert process_starts(slow) == []


# Which strips show ---------------------------------------------------------------------------


def starts(**clients):
    names = {"cursor": CURSOR_APP, "codex": "codex"}
    return [(when, names[client]) for client, when in clients.items()]


def test_an_old_process_means_a_strip():
    log = [line("c1", applied_at(10))]
    assert pending_restarts(log, starts(cursor=at(9))) == [
        {"client": "cursor", "note": CURSOR_NOTE, "change": "c1"}
    ]


def test_a_process_started_after_the_apply_means_none():
    log = [line("c1", applied_at(10))]
    assert pending_restarts(log, starts(cursor=at(11))) == []


def test_no_process_of_the_client_means_none():
    log = [line("c1", applied_at(10))]
    assert pending_restarts(log, starts(codex=at(9))) == []
    assert pending_restarts(log, []) == []


def test_other_clients_do_not_count_for_each_other():
    log = [line("c1", applied_at(10))]
    both = [*starts(codex=at(9)), *starts(cursor=at(11))]
    assert pending_restarts(log, both) == []


def test_two_changes_for_a_client_give_one_strip_with_the_newest():
    log = [  # newest first
        line("c2", applied_at(10, 30), note="Newer note."),
        line("c1", applied_at(10), note="Older note."),
    ]
    assert pending_restarts(log, starts(cursor=at(9))) == [
        {"client": "cursor", "note": "Newer note.", "change": "c2"}
    ]


def test_each_client_has_its_own_strip():
    log = [
        line("c2", applied_at(10, 30), client="codex", note=CODEX_NOTE),
        line("c1", applied_at(10)),
    ]
    both = [*starts(cursor=at(9)), *starts(codex=at(9))]
    assert pending_restarts(log, both) == [
        {"client": "codex", "note": CODEX_NOTE, "change": "c2"},
        {"client": "cursor", "note": CURSOR_NOTE, "change": "c1"},
    ]


def test_a_step_without_a_note_gives_none():
    log = [line("c1", applied_at(10), note=None), line("c0", applied_at(9, 50), note="")]
    assert pending_restarts(log, starts(cursor=at(9))) == []


def test_only_applied_changes_count():
    for state in ("previewed", "stale", "cancelled", "restored", "undone"):
        log = [line("c1", applied_at(10), state=state)]
        assert pending_restarts(log, starts(cursor=at(9))) == [], state


def test_an_undone_change_cancels_its_strip():
    log = [
        line("c1", applied_at(10, 20), state="undone"),  # the undo, logged later
        line("c1", applied_at(10), state="verified"),
    ]
    assert pending_restarts(log, starts(cursor=at(9))) == []


def test_an_undone_change_shows_the_older_change_again():
    log = [
        line("c2", applied_at(10, 40), state="undone"),
        line("c2", applied_at(10, 30), note="Newer note."),
        line("c1", applied_at(10), note="Older note."),
    ]
    assert pending_restarts(log, starts(cursor=at(9))) == [
        {"client": "cursor", "note": "Older note.", "change": "c1"}
    ]


def test_the_apply_time_is_the_first_line_of_the_change():
    log = [
        line("c1", applied_at(12), state="undo_blocked"),  # a blocked undo, logged later
        line("c1", applied_at(10), state="verified"),
    ]
    assert pending_restarts(log, starts(cursor=at(11))) == []
    assert len(pending_restarts(log, starts(cursor=at(9)))) == 1


def test_a_time_it_cannot_read_gives_none():
    assert pending_restarts([line("c1", "not a time")], starts(cursor=at(9))) == []
    assert pending_restarts([line("c1", None)], starts(cursor=at(9))) == []


def test_which_processes_belong_to_a_client():
    def one(args, client="claude_code"):
        log = [line("c1", applied_at(10), client=client, note="Restart.")]
        return bool(pending_restarts(log, [(at(9), args)]))

    assert one("/Users/me/.local/bin/claude --resume")
    assert one("node /opt/homebrew/bin/claude")
    assert one("/Applications/Claude.app/Contents/MacOS/Claude")
    assert one("node /x/node_modules/@anthropic-ai/claude-code/cli.js")
    assert one(CURSOR_APP, client="cursor")
    assert one("/usr/share/cursor/cursor --type=zygote", client="cursor")
    assert one("/Applications/ChatGPT.app/Resources/codex-cli/bin/codex app-server", client="codex")
    assert not one("/bin/zsh -c claude-notes")
    assert not one("vim claude.txt")
    assert not one("/usr/bin/cursor-agent-helper", client="cursor")


# The route -----------------------------------------------------------------------------------


def page(tmp_path, log, run, **options):
    home = tmp_path / "home"
    folder = data_dir(home)
    folder.mkdir(parents=True)
    (folder / "changes.log").write_text(
        "".join(json.dumps(entry) + "\n" for entry in reversed(log))
    )
    app = create_app(
        lambda **o: Inventory(),
        token="tok",
        port=47800,
        home=home,
        processes=lambda: process_starts(run),
        **options,
    )
    return TestClient(app, base_url=ORIGIN, follow_redirects=False)


def test_the_route_gives_the_strips(tmp_path):
    run = ps(f"Tue Nov 11 09:15:02 2026 {CURSOR_APP}")
    with page(tmp_path, [line("c1", applied_at(10))], run) as client:
        client.get("/?token=tok")
        assert client.get("/api/restarts").json() == [
            {"client": "cursor", "note": CURSOR_NOTE, "change": "c1"}
        ]


def test_the_route_gives_none_when_ps_fails(tmp_path):
    def failed(command, **options):
        return subprocess.CompletedProcess(command, 1, "", "")

    with page(tmp_path, [line("c1", applied_at(10))], failed) as client:
        client.get("/?token=tok")
        answer = client.get("/api/restarts")
        assert answer.status_code == 200
        assert answer.json() == []


def test_a_page_without_a_folder_gives_none():
    app = create_app(lambda **o: Inventory(), token="tok", port=47800)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        client.get("/?token=tok")
        assert client.get("/api/restarts").json() == []


def test_the_sample_page_never_reads_processes(tmp_path):
    def never():
        raise AssertionError("read the processes")

    home = tmp_path / "home"
    home.mkdir()
    app = create_app(
        lambda **o: Inventory(), token="tok", port=47800, home=home, demo=True, processes=never
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        client.get("/?token=tok")
        assert client.get("/api/restarts").json() == []
