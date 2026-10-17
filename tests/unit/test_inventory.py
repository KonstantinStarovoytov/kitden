from pathlib import Path

from agentsetup.clients.base import ClientAdapter, Scan
from agentsetup.model import (
    ClientStatus,
    Item,
    ItemKind,
    Project,
    Scope,
    Source,
    SourceKind,
)
from agentsetup.views.inventory import build_inventory


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
