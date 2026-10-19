"""The MetaMCP client against the fake gateway (feature 006, T003)."""

import pytest

from kitden.gateway_api import GatewayError, MetaMcpClient, endpoint_name, gateway_name
from kitden.model import Gateway
from tests.unit.fake_metamcp import FakeMetaMcp

ENV = {"METAMCP_PW": "right-password"}
SECRET = "SENTINEL_SECRET_HEADER"


@pytest.fixture
def fake():
    fake = FakeMetaMcp().start()
    yield fake
    fake.stop()


def gateway_for(fake, **extra):
    return Gateway(
        url=fake.mcp_url,
        login_email="me@example.com",
        login_password_env_var="METAMCP_PW",
        **extra,
    )


def test_held_lists_the_servers_behind_the_endpoint(fake):
    fake.hold("docs", "http://127.0.0.1:8765/mcp")
    fake.hold("other", "http://127.0.0.1:8766/sse", "SSE")
    with MetaMcpClient(gateway_for(fake), ENV) as client:
        held = client.held()
    assert [(s["name"], s["type"], s["url"]) for s in held] == [
        ("docs", "STREAMABLE_HTTP", "http://127.0.0.1:8765/mcp"),
        ("other", "SSE", "http://127.0.0.1:8766/sse"),
    ]
    assert all("headers" not in s for s in held)
    assert fake.sessions == set()  # signed out at the end


def test_add_then_remove(fake):
    server = {"type": "STREAMABLE_HTTP", "url": "https://mcp.neon.tech/mcp"}
    with MetaMcpClient(gateway_for(fake), ENV) as client:
        uuid = client.add("neon", {**server, "headers": {"Authorization": SECRET}})
        assert [s["name"] for s in client.held()] == ["neon"]
        assert fake.servers[uuid]["headers"] == {"Authorization": SECRET}
        assert client.remove(uuid) is True
        assert client.held() == []
        assert client.remove(uuid) is False  # already gone
    assert fake.servers == {}


def test_wrong_password_is_refused_without_showing_it(fake):
    with pytest.raises(GatewayError) as error:
        MetaMcpClient(gateway_for(fake), {"METAMCP_PW": "wrong-one"}).sign_in()
    assert "refused the sign-in" in str(error.value)
    assert "wrong-one" not in str(error.value)


def test_missing_password_variable_says_which_one(fake):
    with pytest.raises(GatewayError, match="Set METAMCP_PW"):
        MetaMcpClient(gateway_for(fake), {}).sign_in()


def test_a_gateway_without_sign_in_details_cannot_be_managed(fake):
    with pytest.raises(GatewayError, match="sign-in email"):
        MetaMcpClient(Gateway(url=fake.mcp_url), ENV)


def test_unreachable_gateway():
    fake = FakeMetaMcp().start()
    gateway = gateway_for(fake)
    fake.stop()
    with pytest.raises(GatewayError, match="Could not reach"):
        MetaMcpClient(gateway, ENV).sign_in()


def test_an_unknown_answer_shape_changes_nothing(fake):
    fake.odd_shape = True
    with MetaMcpClient(gateway_for(fake), ENV) as client, pytest.raises(GatewayError):
        client.held()
    fake.odd_shape = False
    with MetaMcpClient(gateway_for(fake), ENV) as client, pytest.raises(GatewayError):
        fake.odd_shape = True
        client.add("x", {"type": "STREAMABLE_HTTP", "url": "http://x/mcp"})
    assert fake.servers == {}


def test_add_removes_the_server_again_when_the_namespace_update_fails(fake):
    fake.fail_on = "frontend.namespaces.update"
    with MetaMcpClient(gateway_for(fake), ENV) as client, pytest.raises(GatewayError, match="500"):
        client.add("x", {"type": "STREAMABLE_HTTP", "url": "http://x/mcp"})
    assert fake.servers == {} and fake.in_namespace == []


def test_error_text_never_carries_a_response_body(fake):
    fake.hold("docs", "http://127.0.0.1:8765/mcp")
    fake.servers[fake.in_namespace[0]]["headers"] = {"Authorization": SECRET}
    fake.fail_on = "frontend.mcpServers.create"
    with MetaMcpClient(gateway_for(fake), ENV) as client, pytest.raises(GatewayError) as error:
        client.add("x", {"type": "STREAMABLE_HTTP", "url": "http://x/mcp"})
    assert SECRET not in str(error.value)


def test_endpoint_and_server_names():
    assert endpoint_name("http://127.0.0.1:12008/metamcp/local/mcp") == "local"
    with pytest.raises(GatewayError):
        endpoint_name("http://127.0.0.1:12008/mcp")
    assert gateway_name("agent-docs") == "agent-docs"
    assert gateway_name("My Server.v2") == "My-Server-v2"
    assert gateway_name("a__b") == "a_b"
    assert gateway_name("...") == "server"
