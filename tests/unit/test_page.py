"""One page per home folder: the lock and the page record (feature 002, FR-009, FR-010)."""

import stat
import subprocess
import sys
import time

from kitden import page
from kitden.gateways import data_dir


def test_only_one_page_holds_the_lock(tmp_path):
    first, second = page.PageLock(tmp_path), page.PageLock(tmp_path)
    assert first.acquire()
    try:
        assert not second.acquire()
        assert page.page_running(tmp_path)
    finally:
        first.release()
    assert not page.page_running(tmp_path)


def test_the_lock_is_released_when_the_page_process_dies(tmp_path):
    code = (
        "import sys, time; sys.path.insert(0, 'src'); from kitden import page; "
        f"assert page.PageLock({str(tmp_path)!r}).acquire(); print('locked', flush=True); "
        "time.sleep(60)"
    )
    process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)  # noqa: S603
    try:
        assert process.stdout.readline().strip() == "locked"
        assert page.page_running(tmp_path)
    finally:
        process.kill()
        process.wait(timeout=10)
    assert not page.page_running(tmp_path)


def test_the_record_is_private_and_removed_on_stop(tmp_path):
    page.write_record(tmp_path, port=47811, token="tok", background=True)
    path = data_dir(tmp_path) / "page.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    record = page.read_record(tmp_path)
    assert (record["port"], record["token"], record["background"]) == (47811, "tok", True)
    assert page.start_link(record) == "http://127.0.0.1:47811/?token=tok"
    page.remove_record(tmp_path)
    assert page.read_record(tmp_path) is None


def test_a_record_without_a_running_page_is_stale(tmp_path):
    page.write_record(tmp_path, port=47811, token="tok", background=False)
    assert page.running_page(tmp_path) is None
    assert page.read_record(tmp_path) is None


def test_the_running_page_is_found_through_the_lock(tmp_path):
    lock = page.PageLock(tmp_path)
    assert lock.acquire()
    try:
        page.write_record(tmp_path, port=47811, token="tok", background=False)
        assert page.running_page(tmp_path)["port"] == 47811
    finally:
        lock.release()


def test_waiting_for_a_record_gives_up(tmp_path):
    started = time.monotonic()
    assert page.wait_for_record(tmp_path, seconds=0.3) is None
    assert time.monotonic() - started < 2
