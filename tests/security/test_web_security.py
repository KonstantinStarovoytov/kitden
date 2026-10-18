import pytest
from starlette.testclient import TestClient

from kitden.views.inventory import Inventory
from kitden.web.app import create_app

PORT = 47800
ORIGIN = f"http://127.0.0.1:{PORT}"
TOKEN = "t" * 43


@pytest.fixture
def client():
    app = create_app(lambda: Inventory(), token=TOKEN, port=PORT)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as c:
        yield c


def _login(client):
    response = client.get(f"/?token={TOKEN}")
    assert response.status_code == 303
    return response


def test_start_link_sets_a_strict_session_cookie_and_cleans_the_url(client):
    response = _login(client)
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie


def test_wrong_token_is_rejected(client):
    assert client.get("/?token=wrong").status_code == 401


def test_api_needs_the_session_cookie(client):
    assert client.get("/api/clients").status_code == 401
    _login(client)
    assert client.get("/api/clients").status_code == 200


def test_foreign_host_is_rejected_even_with_a_cookie(client):
    _login(client)
    response = client.get("/api/clients", headers={"Host": "evil.example:47800"})
    assert response.status_code == 403


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Tool-Request": "1"},  # no Origin
        {"Origin": "http://evil.example", "X-Tool-Request": "1"},
        {"Origin": "null", "X-Tool-Request": "1"},
        {"Origin": ORIGIN},  # no custom header
        {"Origin": ORIGIN, "X-Tool-Request": "1", "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_state_changing_requests_need_same_origin_and_the_custom_header(client, headers):
    _login(client)
    assert client.post("/api/rescan", headers=headers).status_code == 403


def test_a_proper_post_passes_the_security_layer(client):
    _login(client)
    response = client.post(
        "/api/rescan",
        headers={"Origin": ORIGIN, "X-Tool-Request": "1", "Sec-Fetch-Site": "same-origin"},
    )
    assert response.status_code == 200


def test_event_stream_needs_the_cookie_and_rejects_foreign_origins(client):
    assert client.get("/api/events").status_code == 401
    _login(client)
    response = client.get("/api/events", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403


def test_no_cors_headers_and_a_strict_csp(client):
    _login(client)
    response = client.get("/api/clients", headers={"Origin": "http://evil.example"})
    assert not [h for h in response.headers if h.lower().startswith("access-control-")]
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
