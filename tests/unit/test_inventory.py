import time
from pathlib import Path

from kitden.clients import version_cache
from kitden.clients.base import ClientAdapter, Scan
from kitden.clients.codex import CodexAdapter
from kitden.model import (
    ClientStatus,
    Item,
    ItemKind,
    Project,
    Scope,
    Source,
    SourceKind,
)
from kitden.views.inventory import build_inventory, default_adapters
from tests.conftest import fake_client_command, make_home, write_cursor_fixture_state


def _item(client, name):
    source = Source(kind=SourceKind.FILE, path=f"/{client}.json", owner_client=client)
    return Item(client=client, kind=ItemKind.SKILL, name=name, source=source, scope=Scope.USER)


class FakeAdapter(ClientAdapter):
    """A stand-in client: returns a fixed scan, or fails, without touching files."""

    config_root = ".fake"

    def __init__(self, client_id, scan=None, found=True, fail=False):
        super().__init__(Path("/nonexistent"), read_version=lambda: "1.0" if found else None)
        self.id = client_id
        self.display_name = client_id
        self._scan = scan or Scan()
        self._fail = fail

    def scan(self):
        if self._fail:
            raise RuntimeError("format changed")
        return self._scan


def test_projects_known_by_several_clients_are_merged():
    a = FakeAdapter("claude_code", Scan(projects=[Project("/work/x", True, ("claude_code",))]))
    b = FakeAdapter("codex", Scan(projects=[Project("/work/x", True, ("codex",))]))
    inventory = build_inventory(adapters=[a, b])
    assert [(p.path, p.known_by) for p in inventory.projects] == [
        ("/work/x", ("claude_code", "codex"))
    ]


def test_a_failing_adapter_is_reported_and_others_still_scan():
    good = FakeAdapter("codex", Scan(items=[_item("codex", "docker-expert")]))
    bad = FakeAdapter("cursor", fail=True)
    inventory = build_inventory(adapters=[good, bad])
    assert [i.name for i in inventory.items] == ["docker-expert"]
    statuses = {c.id: c.status for c in inventory.clients}
    assert statuses == {"codex": ClientStatus.FOUND, "cursor": ClientStatus.UNREADABLE}
    assert [p.owner_client for p in inventory.problems] == ["cursor"]


def test_missing_clients_are_listed_but_not_scanned():
    missing = FakeAdapter("cursor", Scan(items=[_item("cursor", "x")]), found=False)
    inventory = build_inventory(adapters=[missing])
    assert [c.status for c in inventory.clients] == [ClientStatus.NOT_FOUND]
    assert inventory.items == []


def test_clients_carry_the_link_of_their_installed_app():
    from tests.conftest import FIXTURES

    a = FakeAdapter("claude_code", Scan())
    b = FakeAdapter("codex", Scan())
    inventory = build_inventory(adapters=[a, b], apps=[FIXTURES / "apps"])
    assert {c.id: c.app_url for c in inventory.clients} == {
        "claude_code": "claude://",
        "codex": "codex://",
    }
    assert all(c.app_url is None for c in build_inventory(adapters=[a, b]).clients)


class SlowAdapter(FakeAdapter):
    def scan(self):
        time.sleep(0.3)
        return super().scan()


def test_clients_are_read_side_by_side_and_each_says_when_it_is_done():
    adapters = [
        SlowAdapter(c, Scan(items=[_item(c, "x")])) for c in ("claude_code", "codex", "cursor")
    ]
    done = []
    started = time.monotonic()
    inventory = build_inventory(adapters=adapters, on_step=done.append)
    assert time.monotonic() - started < 0.6  # not 0.9: the three reads overlap
    assert sorted(done) == ["claude_code", "codex", "cursor"]
    assert [c.id for c in inventory.clients] == ["claude_code", "codex", "cursor"]
    assert [i.client for i in inventory.items] == ["claude_code", "codex", "cursor"]


def test_a_quick_build_asks_codex_for_a_quick_scan(tmp_path):
    codex = next(a for a in default_adapters(tmp_path, quick=True) if a.id == "codex")
    assert isinstance(codex, CodexAdapter) and codex.quick is True
    codex = next(a for a in default_adapters(tmp_path) if a.id == "codex")
    assert codex.quick is False


def test_an_inventory_says_when_a_client_still_waits_for_a_slow_answer():
    waiting = FakeAdapter("codex")
    waiting.skipped = True
    assert build_inventory(adapters=[FakeAdapter("claude_code"), waiting]).partial is True
    assert build_inventory(adapters=[FakeAdapter("claude_code")]).partial is False


def test_the_first_scan_runs_no_version_command(tmp_path, monkeypatch):
    home = make_home(tmp_path, "claude_code/2.1.283", "codex/0.159.2", "cursor/3.21.16")
    write_cursor_fixture_state(home)
    ran = tmp_path / "ran"
    hang = fake_client_command(tmp_path, "client", f"echo ran >> '{ran}'; exec sleep 3")
    monkeypatch.setattr(version_cache, "version_command", lambda client: [str(hang), "--version"])
    started = time.monotonic()
    inventory = build_inventory(home)
    assert time.monotonic() - started < 1
    assert not ran.exists()
    clients = {c.id: c for c in inventory.clients}
    assert clients["claude_code"].version is None
    assert not clients["claude_code"].version_supported
    assert str(clients["claude_code"].status) == "found"


def test_the_scan_shows_the_cached_version(tmp_path, monkeypatch):
    home = make_home(tmp_path, "codex/0.159.2")
    codex = fake_client_command(tmp_path, "codex", "echo codex-cli 0.159.2")
    commands = {"codex": [str(codex), "--version"]}
    monkeypatch.setattr(version_cache, "version_command", commands.get)
    version_cache.refresh_versions(home, ["codex"])
    clients = {c.id: c for c in build_inventory(home).clients}
    assert (clients["codex"].version, clients["codex"].version_supported) == ("0.159.2", True)


def test_a_missing_client_stays_not_found_with_the_cache(tmp_path):
    inventory = build_inventory(make_home(tmp_path, "codex/0.159.2"))
    assert {c.id: str(c.status) for c in inventory.clients}["cursor"] == "not_found"
