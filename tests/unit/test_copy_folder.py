"""Copying a skill folder as a change: preview, apply, verify, undo."""

import os
import stat

import pytest

from kitden.changes.backup import ChangeStore
from kitden.changes.client_cli import CommandResult
from kitden.changes.copy_folder import CopyRefusedError, digest, list_files
from kitden.changes.engine import ChangeRefusedError, Engine
from kitden.model import COPY_FOLDER, ChangeState, FolderCopy, Scope, Step


def _no_run(command, cwd):
    return CommandResult(1, "no command runs for a copy")


def make_skill(root, name="tidy", extra=None):
    folder = root / name
    (folder / "scripts").mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: tidy\ndescription: Tidy up.\n---\n# Tidy\n")
    script = folder / "scripts/run.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(0o755)
    for rel, text in (extra or {}).items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text)
    return folder


def make_engine(tmp_path):
    return Engine(ChangeStore(tmp_path / "data"), run=_no_run)


def copy_step(source, target, readers=("claude_code",)):
    return Step(
        client="claude_code",
        scope=Scope.USER,
        name="tidy",
        mechanism=COPY_FOLDER,
        copy=FolderCopy(source=str(source), target=str(target), readers=list(readers)),
    )


@pytest.fixture
def places(tmp_path):
    source = make_skill(tmp_path / "marketplace/plugin/skills")
    target = tmp_path / "home/.claude/skills/tidy"
    return source, target


def test_list_files_refuses_links_and_digest_tells_copies_apart(tmp_path):
    folder = make_skill(tmp_path)
    assert list_files(folder) == ["SKILL.md", "scripts/run.sh"]
    before = digest(folder)
    (folder / "SKILL.md").write_text("changed")
    assert digest(folder) != before
    os.symlink(tmp_path, folder / "escape")
    with pytest.raises(CopyRefusedError, match="link"):
        list_files(folder)


def test_a_finder_file_is_not_part_of_a_skill(tmp_path):
    # Finder leaves .DS_Store in folders it opened; two copies stay the same skill.
    plain = make_skill(tmp_path / "a")
    opened = make_skill(tmp_path / "b")
    (opened / ".DS_Store").write_bytes(b"\0\0\0\1Bud1")
    (opened / "scripts/.DS_Store").write_bytes(b"\0\0\0\1Bud1")
    assert list_files(opened) == ["SKILL.md", "scripts/run.sh"]
    assert digest(opened) == digest(plain)


def test_a_copy_leaves_the_finder_file_out(tmp_path, places):
    source, target = places
    (source / ".DS_Store").write_bytes(b"\0\0\0\1Bud1")
    engine = make_engine(tmp_path)
    change = engine.preview("skill.install", [copy_step(source, target)])
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED, change.error
    assert not (target / ".DS_Store").exists()
    # Finder opens the copy too: undo still takes it back.
    (target / ".DS_Store").write_bytes(b"\0\0\0\1Bud1")
    engine.undo(change.id)
    assert not target.exists()


def test_preview_lists_the_files_and_writes_nothing(tmp_path, places):
    source, target = places
    engine = make_engine(tmp_path)
    change = engine.preview("skill.install", [copy_step(source, target)])
    assert change.state is ChangeState.PREVIEWED
    copy = change.steps[0].copy
    assert copy.masked_diff.splitlines() == ["+SKILL.md", "+scripts/run.sh"]
    assert copy.content_hash == digest(source)
    assert not target.parent.exists()


def test_preview_refuses_a_target_that_exists_and_a_source_with_a_link(tmp_path, places):
    source, target = places
    target.mkdir(parents=True)
    with pytest.raises(ChangeRefusedError, match="already exists"):
        make_engine(tmp_path).preview("skill.install", [copy_step(source, target)])
    target.rmdir()
    os.symlink(tmp_path, source / "out")
    with pytest.raises(ChangeRefusedError, match="link"):
        make_engine(tmp_path).preview("skill.install", [copy_step(source, target)])


def test_apply_copies_the_files_with_their_modes_and_undo_removes_the_copy(tmp_path, places):
    source, target = places
    engine = make_engine(tmp_path)
    change = engine.preview("skill.install", [copy_step(source, target)])
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED, change.error
    assert (target / "SKILL.md").read_text().startswith("---\nname: tidy")
    assert stat.S_IMODE((target / "scripts/run.sh").stat().st_mode) == 0o755
    assert digest(target) == digest(source)
    entry = engine.store.entries()[0]
    assert entry["steps"][0]["path"] == str(target)
    assert entry["steps"][0]["reaches"] == ["claude_code"]

    # A new engine reads the record back and can still undo.
    again = Engine(ChangeStore(tmp_path / "data"), run=_no_run)
    again.undo(change.id)
    assert again.changes[change.id].state is ChangeState.UNDONE
    assert not target.exists()
    assert target.parent.is_dir()  # the client's skills folder stays
    assert source.is_dir()


def test_undo_refuses_a_copy_that_changed(tmp_path, places):
    source, target = places
    engine = make_engine(tmp_path)
    change = engine.preview("skill.install", [copy_step(source, target)])
    engine.apply(change.id)
    (target / "SKILL.md").write_text("my own edits\n")
    engine.undo(change.id)
    assert change.state is ChangeState.UNDO_BLOCKED
    assert "changed after the change was applied" in change.error
    assert (target / "SKILL.md").read_text() == "my own edits\n"


def test_a_source_or_target_that_changed_after_preview_stops_apply(tmp_path, places):
    source, target = places
    engine = make_engine(tmp_path)
    change = engine.preview("skill.install", [copy_step(source, target)])
    (source / "SKILL.md").write_text("edited after preview")
    engine.apply(change.id)
    assert change.state is ChangeState.STALE
    assert "changed since preview" in change.error
    assert not target.exists()

    change = engine.preview("skill.install", [copy_step(source, target)])
    target.mkdir(parents=True)
    engine.apply(change.id)
    assert change.state is ChangeState.STALE
    assert "appeared since preview" in change.error


def test_two_copies_in_one_change_and_a_failed_copy_removes_what_was_copied(tmp_path, places):
    source, target = places
    second = tmp_path / "home/.agents/skills/tidy"
    engine = make_engine(tmp_path)
    change = engine.preview(
        "skill.install", [copy_step(source, target), copy_step(source, second, ["codex"])]
    )
    engine.apply(change.id)
    assert change.state is ChangeState.VERIFIED
    assert target.is_dir() and second.is_dir()
    engine.undo(change.id)
    assert not target.exists() and not second.exists()

    # The second target's parent is a file, so the copy fails; the first copy is taken back.
    second.parent.rmdir()
    second.parent.write_text("in the way")
    change = engine.preview(
        "skill.install", [copy_step(source, target), copy_step(source, second, ["codex"])]
    )
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert not target.exists()


def test_a_copy_that_fails_partway_leaves_no_half_copy(tmp_path, places, monkeypatch):
    import kitden.changes.copy_folder as copying

    source, target = places
    real = copying.shutil.copyfile

    def full_disk(src, dst):
        if str(dst).endswith("run.sh"):
            raise OSError("No space left on device")
        return real(src, dst)

    monkeypatch.setattr(copying.shutil, "copyfile", full_disk)
    engine = make_engine(tmp_path)
    change = engine.preview("skill.install", [copy_step(source, target)])
    engine.apply(change.id)
    assert change.state is ChangeState.RESTORED
    assert "No space left" in change.error
    assert not target.exists()
