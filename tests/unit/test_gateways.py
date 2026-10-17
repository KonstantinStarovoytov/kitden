import stat

import pytest

from agentsetup.gateways import SETTINGS, add_gateway, load_gateways
from agentsetup.model import Gateway, GatewayAuth

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
