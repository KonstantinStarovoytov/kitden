import pytest

from agentsetup.model import (
    Change,
    ChangeState,
    Finding,
    FindingType,
    Gateway,
    GatewayAuth,
    Item,
    ItemKind,
    ReadStatus,
    Scope,
    Severity,
    Source,
    SourceKind,
    UnknownReason,
)


def _source(path="/home/u/.codex/config.toml"):
    return Source(kind=SourceKind.FILE, path=path, owner_client="codex")


def test_unknown_source_requires_a_reason():
    with pytest.raises(ValueError, match="unknown_reason"):
        Source(
            kind=SourceKind.ACCOUNT,
            path=None,
            owner_client="claude_code",
            read_status=ReadStatus.UNKNOWN,
        )


def test_known_source_must_not_carry_a_reason():
    with pytest.raises(ValueError, match="unknown_reason"):
        Source(
            kind=SourceKind.FILE,
            path="/x",
            owner_client="codex",
            unknown_reason=UnknownReason.PARSE_ERROR,
        )


def test_item_id_is_stable_and_depends_on_name_and_source():
    a = Item(
        client="codex", kind=ItemKind.MCP_SERVER, name="neon", source=_source(), scope=Scope.USER
    )
    same = Item(
        client="codex", kind=ItemKind.MCP_SERVER, name="neon", source=_source(), scope=Scope.USER
    )
    other_name = Item(
        client="codex", kind=ItemKind.MCP_SERVER, name="github", source=_source(), scope=Scope.USER
    )
    other_file = Item(
        client="codex",
        kind=ItemKind.MCP_SERVER,
        name="neon",
        source=_source("/repo/.codex/config.toml"),
        scope=Scope.PROJECT,
    )
    assert a.id == same.id
    assert len({a.id, other_name.id, other_file.id}) == 3


def test_finding_needs_at_least_one_item():
    with pytest.raises(ValueError, match="item"):
        Finding(type=FindingType.CROSS_LOADED, severity=Severity.INFO, items=(), explanation="x")


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ([ChangeState.APPLYING, ChangeState.VERIFIED, ChangeState.UNDONE], True),
        ([ChangeState.APPLYING, ChangeState.RESTORED], True),
        ([ChangeState.STALE], True),
        ([ChangeState.VERIFIED], False),  # cannot skip applying
        ([ChangeState.STALE, ChangeState.APPLYING], False),
        ([ChangeState.CANCELLED, ChangeState.APPLYING], False),
        ([ChangeState.APPLYING, ChangeState.VERIFIED, ChangeState.UNDO_BLOCKED], True),
    ],
)
def test_change_follows_the_state_diagram(path, allowed):
    change = Change(action="gateway.connect")
    assert change.state is ChangeState.PREVIEWED
    if allowed:
        for state in path:
            change.move_to(state)
        assert change.state is path[-1]
    else:
        with pytest.raises(ValueError, match="cannot move"):
            for state in path:
                change.move_to(state)


def test_gateway_url_is_normalized_and_drives_the_id():
    a = Gateway(url="HTTP://LocalHost:8880/mcp-connect/work/")
    b = Gateway(url="http://localhost:8880/mcp-connect/work")
    assert a.url == "http://localhost:8880/mcp-connect/work"
    assert a.id == b.id


def test_gateway_key_must_be_a_variable_name_not_a_secret():
    assert (
        Gateway(
            url="http://localhost:12008/mcp", auth=GatewayAuth.ENV_KEY, key_env_var="METAMCP_KEY"
        ).key_env_var
        == "METAMCP_KEY"
    )
    with pytest.raises(ValueError, match="variable name"):
        Gateway(
            url="http://localhost:12008/mcp",
            auth=GatewayAuth.ENV_KEY,
            key_env_var="sk_mt_9f8e7d6c5b4a",
        )
    with pytest.raises(ValueError, match="variable name"):
        Gateway(url="http://localhost:12008/mcp", auth=GatewayAuth.ENV_KEY)
