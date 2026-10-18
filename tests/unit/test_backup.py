import json
import stat
from datetime import UTC, datetime, timedelta

from kitden.changes.backup import ChangeStore

SECRET_LINE = b'token = "SENTINEL_SECRET_BACKUP"\n'


def _mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_backups_are_private_and_the_manifest_has_no_secrets(tmp_path):
    store = ChangeStore(tmp_path / "data")
    saved = store.backup("20261017T100000Z-abc123", {"/x/config.toml": SECRET_LINE})
    folder = tmp_path / "data/changes/20261017T100000Z-abc123"
    assert _mode(tmp_path / "data") == _mode(tmp_path / "data/changes") == _mode(folder) == 0o700
    copy = saved["/x/config.toml"]
    assert copy.read_bytes() == SECRET_LINE
    assert _mode(copy) == 0o600
    manifest = (folder / "manifest.json").read_text()
    assert "SENTINEL" not in manifest
    assert json.loads(manifest)["files"][0]["path"] == "/x/config.toml"


def test_a_missing_file_is_recorded_as_missing(tmp_path):
    store = ChangeStore(tmp_path / "data")
    saved = store.backup("20261017T100000Z-abc123", {"/x/new.json": None})
    assert saved["/x/new.json"] is None
    manifest = json.loads(
        (tmp_path / "data/changes/20261017T100000Z-abc123/manifest.json").read_text()
    )
    assert manifest["files"][0]["existed"] is False


def test_log_hides_secrets_and_lists_newest_first(tmp_path):
    store = ChangeStore(tmp_path / "data")
    store.log({"id": "1", "error": "bad token ghp_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6"})
    store.log({"id": "2", "state": "verified"})
    assert [e["id"] for e in store.entries()] == ["2", "1"]
    assert "ghp_" not in (tmp_path / "data/changes.log").read_text()
    assert _mode(tmp_path / "data/changes.log") == 0o600


def _ids(start: datetime, count: int) -> list[str]:
    return [
        (start + timedelta(minutes=i)).strftime("%Y%m%dT%H%M%SZ") + "-aaaaaa" for i in range(count)
    ]


def test_prune_keeps_the_newest_100_and_everything_from_the_last_30_days(tmp_path):
    store = ChangeStore(tmp_path / "data")
    now = datetime(2026, 10, 17, tzinfo=UTC)
    old = _ids(now - timedelta(days=60), 105)
    recent = _ids(now - timedelta(days=1), 3)
    for change_id in old + recent:
        store.backup(change_id, {"/x/a.json": b"{}"})
    store.prune(now)
    kept = sorted(p.name for p in (tmp_path / "data/changes").iterdir())
    assert kept == sorted(old[8:] + recent)  # the newest 100, all older than 30 days but 3


def test_prune_never_removes_recent_changes(tmp_path):
    store = ChangeStore(tmp_path / "data")
    now = datetime(2026, 10, 17, tzinfo=UTC)
    recent = _ids(now - timedelta(days=2), 120)
    for change_id in recent:
        store.backup(change_id, {"/x/a.json": b"{}"})
    store.prune(now)
    assert len(list((tmp_path / "data/changes").iterdir())) == 120
