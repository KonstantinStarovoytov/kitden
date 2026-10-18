"""The working version's data folder is copied once (feature 002, FR-003, FR-004, research R7)."""

import json
import shutil
import stat

from kitden.changes.backup import ChangeStore
from kitden.changes.engine import Engine
from kitden.changes.json_splice import ABSENT
from kitden.gateways import OLD_DATA_DIR, data_dir, ensure_data_folder, load_gateways
from kitden.model import FileEdit, Scope, Step

SETTINGS = {"gateways": [{"url": "http://127.0.0.1:12008/mcp", "auth": "none"}]}
CONFIG = '[mcp_servers.neon]\nurl = "https://mcp.neon.tech/mcp"\n'


def _old_folder_with_a_change(home):
    """An old data folder with one gateway and one applied change, like the working version."""
    old = home / OLD_DATA_DIR
    old.mkdir(parents=True)
    old.chmod(0o700)
    (old / "settings.json").write_text(json.dumps(SETTINGS))
    (old / "settings.json").chmod(0o600)
    config = home / ".codex/config.toml"
    config.parent.mkdir()
    config.write_text(CONFIG)
    engine = Engine(ChangeStore(old), run=None)
    edit = FileEdit(str(config), "toml", ("mcp_servers", "neon"), ABSENT)
    change = engine.preview("mcp.remove_direct", [Step("codex", Scope.USER, "neon", edit)])
    engine.apply(change.id)
    return old, config, change.id


def test_only_the_old_folder_is_copied_once_and_left_as_it_is(tmp_path):
    old, _, change_id = _old_folder_with_a_change(tmp_path)
    before = {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    note = ensure_data_folder(tmp_path)
    new = data_dir(tmp_path)
    assert "Copied" in note
    assert load_gateways(tmp_path)[0].url == "http://127.0.0.1:12008/mcp"
    assert stat.S_IMODE(new.stat().st_mode) == 0o700
    assert stat.S_IMODE((new / "settings.json").stat().st_mode) == 0o600
    record = json.loads((new / "changes" / change_id / "change.json").read_text())
    assert record["steps"][0]["edit"]["backup_path"].startswith(str(new))
    after = {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    assert after == before
    assert ensure_data_folder(tmp_path) is not None  # both now exist: only a note, no copy


def test_after_the_copy_both_folders_use_the_new_one_and_say_so(tmp_path):
    old, _, _ = _old_folder_with_a_change(tmp_path)
    ensure_data_folder(tmp_path)
    (data_dir(tmp_path) / "settings.json").write_text('{"gateways": []}')
    note = ensure_data_folder(tmp_path)
    assert "not used" in note and "delete" not in note
    assert load_gateways(tmp_path) == []  # the new folder wins
    assert json.loads((old / "settings.json").read_text()) == SETTINGS


def test_nothing_to_do_without_an_old_folder(tmp_path):
    assert ensure_data_folder(tmp_path) is None
    assert not data_dir(tmp_path).exists()


def test_a_failed_copy_leaves_no_partial_folder(tmp_path, monkeypatch):
    old, _, _ = _old_folder_with_a_change(tmp_path)

    def broken(src, dst, **kwargs):
        dst.mkdir(parents=True)
        (dst / "half").write_text("x")
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copytree", broken)
    note = ensure_data_folder(tmp_path)
    assert "Could not copy" in note and "disk full" in note
    assert not data_dir(tmp_path).exists()
    assert not any(".copying" in p.name for p in data_dir(tmp_path).parent.iterdir())
    assert (old / "settings.json").is_file()


def test_undo_of_an_old_change_works_after_the_old_folder_is_deleted(tmp_path):
    old, config, change_id = _old_folder_with_a_change(tmp_path)
    ensure_data_folder(tmp_path)
    shutil.rmtree(old)
    engine = Engine(ChangeStore(data_dir(tmp_path)), run=None)
    engine.undo(change_id)
    assert str(engine.changes[change_id].state) == "undone"
    assert config.read_text() == CONFIG


# Final review fixes ------------------------------------------------------------------------


def test_a_failed_copy_is_retried_after_the_page_made_the_folder(tmp_path, monkeypatch):
    _old_folder_with_a_change(tmp_path)
    real = shutil.copytree

    def broken(src, dst, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copytree", broken)
    assert "Could not copy" in ensure_data_folder(tmp_path)
    data_dir(tmp_path).mkdir(parents=True)  # the page lock and log live here
    (data_dir(tmp_path) / "page.lock").write_text("")
    monkeypatch.setattr(shutil, "copytree", real)
    note = ensure_data_folder(tmp_path)
    assert "Copied" in note and "delete" not in note
    assert load_gateways(tmp_path)[0].url == "http://127.0.0.1:12008/mcp"


def test_two_commands_copying_at_once_both_end_complete(tmp_path, monkeypatch):
    old, _, change_id = _old_folder_with_a_change(tmp_path)
    real = shutil.copytree
    notes, second_started = [], []

    def interleaved(src, dst, *args, **kwargs):
        result = real(src, dst, *args, **kwargs)
        if not second_started:  # a second command starts while the first one is copying
            second_started.append(True)
            notes.append(ensure_data_folder(tmp_path))
        return result

    monkeypatch.setattr(shutil, "copytree", interleaved)
    notes.append(ensure_data_folder(tmp_path))
    assert all("Could not copy" not in n for n in notes), notes
    assert (data_dir(tmp_path) / "changes" / change_id / "change.json").is_file()
    assert load_gateways(tmp_path)[0].url == "http://127.0.0.1:12008/mcp"


def test_a_broken_change_record_does_not_stop_the_copy(tmp_path):
    old, _, change_id = _old_folder_with_a_change(tmp_path)
    broken = old / "changes" / "20260101T000000Z-broken"
    broken.mkdir()
    (broken / "change.json").write_bytes(b"\xff\xfe not text")
    note = ensure_data_folder(tmp_path)
    assert "Copied" in note
    record = json.loads((data_dir(tmp_path) / "changes" / change_id / "change.json").read_text())
    assert record["steps"][0]["edit"]["backup_path"].startswith(str(data_dir(tmp_path)))
