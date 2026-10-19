import stat

import pytest

from kitden.gateways import SETTINGS, add_gateway, load_gateways
from kitden.model import Gateway, GatewayAuth

URL = "http://127.0.0.1:12008/metamcp/dev/mcp"


def test_gateways_are_saved_privately_and_read_back(tmp_path):
    gateway = Gateway(
        url=URL, ui_url="http://127.0.0.1:12008", auth=GatewayAuth.ENV_KEY, key_env_var="GW_KEY"
    )
    add_gateway(tmp_path, gateway)
    assert load_gateways(tmp_path) == [gateway]
    assert stat.S_IMODE((tmp_path / SETTINGS).stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / SETTINGS).parent.stat().st_mode) == 0o700


def test_the_same_url_replaces_the_old_entry(tmp_path):
    add_gateway(tmp_path, Gateway(url=URL))
    add_gateway(tmp_path, Gateway(url=URL + "/", auth=GatewayAuth.OAUTH))
    assert load_gateways(tmp_path) == [Gateway(url=URL, auth=GatewayAuth.OAUTH)]


def test_no_gateways_yet(tmp_path):
    assert load_gateways(tmp_path) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://user:pass@127.0.0.1:12008/mcp",
        "http://127.0.0.1:12008/mcp?api_key=abc123",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "127.0.0.1:12008/mcp",
    ],
)
def test_bad_or_secret_urls_are_refused(tmp_path, url):
    with pytest.raises(ValueError):
        add_gateway(tmp_path, Gateway(url=url))
    assert load_gateways(tmp_path) == []


def test_interface_link_must_be_a_web_address(tmp_path):
    with pytest.raises(ValueError):
        add_gateway(tmp_path, Gateway(url=URL, ui_url="javascript:alert(1)"))


def test_a_key_value_is_never_accepted(tmp_path):
    with pytest.raises(ValueError):
        Gateway(url=URL, auth=GatewayAuth.ENV_KEY, key_env_var="sk-abc123secretvalue")


def test_sign_in_details_keep_the_email_and_the_variable_name(tmp_path):
    gateway = Gateway(url=URL, login_email="me@example.com", login_password_env_var="METAMCP_PW")
    add_gateway(tmp_path, gateway)
    assert load_gateways(tmp_path) == [gateway]
    assert gateway.managed
    assert not Gateway(url=URL).managed
    assert "METAMCP_PW" in (tmp_path / SETTINGS).read_text()


@pytest.mark.parametrize(
    "fields",
    [
        {"login_email": "me@example.com"},  # no variable
        {"login_password_env_var": "METAMCP_PW"},  # no email
        {"login_email": "me@example.com", "login_password_env_var": "hunter2secret"},
        {"login_email": "not an email", "login_password_env_var": "METAMCP_PW"},
    ],
)
def test_a_password_or_half_a_sign_in_is_refused(fields):
    with pytest.raises(ValueError):
        Gateway(url=URL, **fields)


# Feature 007: an Obot gateway is told from its address and managed with a key variable.

OBOT = "http://127.0.0.1:8080/mcp-connect/abc123"


def test_the_kind_of_gateway_comes_from_its_address():
    assert Gateway(url=URL).kind == "metamcp"
    assert Gateway(url=OBOT).kind == "obot"
    assert Gateway(url="http://127.0.0.1:9000/mcp").kind == "other"


def test_an_obot_gateway_is_managed_with_a_key_variable_even_for_oauth_clients(tmp_path):
    gateway = Gateway(url=OBOT, auth=GatewayAuth.OAUTH, key_env_var="OBOT_KEY")
    add_gateway(tmp_path, gateway)
    assert load_gateways(tmp_path) == [gateway]
    assert gateway.managed and not gateway.movable
    assert not Gateway(url=OBOT, auth=GatewayAuth.OAUTH).managed
    managed_metamcp = Gateway(url=URL, login_email="me@example.com", login_password_env_var="PW")
    assert managed_metamcp.movable
    with pytest.raises(ValueError):
        Gateway(url=OBOT, auth=GatewayAuth.OAUTH, key_env_var="ok1-3-abc-secretvalue")
