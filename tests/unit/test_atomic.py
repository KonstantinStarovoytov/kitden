import os
import stat

import pytest

from agentsetup.changes.atomic import RefusedWriteError, write_atomic


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_replaces_content_and_keeps_the_file_mode(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("old\n")
    target.chmod(0o640)

    write_atomic(target, b"new\n")

    assert target.read_bytes() == b"new\n"
    assert _mode(target) == 0o640


def test_new_file_is_private(tmp_path):
    target = tmp_path / "mcp.json"
    write_atomic(target, b"{}\n")
    assert _mode(target) == 0o600


def test_writes_through_a_symlink_and_keeps_the_link(tmp_path):
    real = tmp_path / "dotfiles" / "config.toml"
    real.parent.mkdir()
    real.write_text("old\n")
    link = tmp_path / "config.toml"
    link.symlink_to(real)

    write_atomic(link, b"new\n")

    assert link.is_symlink()
    assert real.read_bytes() == b"new\n"


def test_refuses_hard_linked_files(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text("{}\n")
    os.link(target, tmp_path / "other-name.json")

    with pytest.raises(RefusedWriteError, match="hard link"):
        write_atomic(target, b"changed\n")
    assert target.read_text() == "{}\n"


def test_leaves_no_temp_files_behind(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("old\n")
    write_atomic(target, b"new\n")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.toml"]
