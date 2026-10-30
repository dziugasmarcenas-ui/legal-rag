"""OAuth is the front door, so its behaviour is tested, not assumed.

The SDK verifies PKCE and the redirect URI; what is tested here is the part the
SDK delegates: registering clients, minting a code only for the right password,
issuing and rotating tokens, and expiring them.

The full HTTP flow (discovery -> register -> authorize -> consent -> token ->
/mcp) is exercised against a running server as well; these tests cover the
provider so a regression fails without a browser.
"""

import sys
import time
import urllib.parse

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

import oauth
from mcp.shared.auth import OAuthClientInformationFull


def client_info(client_id="client-1", redirect="http://localhost:9999/cb"):
    return OAuthClientInformationFull(
        client_id=client_id,
        client_name="test client",
        redirect_uris=[redirect],
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
    )


def params(redirect="http://localhost:9999/cb", state="xyz"):
    return oauth.AuthorizationParams(
        state=state,
        scopes=["legal:read"],
        code_challenge="challenge",
        redirect_uri=redirect,
        redirect_uri_provided_explicitly=True,
        resource=None,
    )


@pytest.mark.anyio
async def test_a_client_can_register_and_be_found():
    provider = oauth.Provider("pw")
    info = client_info()
    await provider.register_client(info)
    assert await provider.get_client("client-1") is info


def test_no_password_means_no_authorization_server():
    """A public host must not accidentally expose an open consent endpoint."""
    assert oauth.build() is None


def test_consent_page_asks_for_the_password(monkeypatch):
    provider = oauth.Provider("secret")
    app = Starlette(routes=[Route("/oauth/consent", provider.consent_response,
                                  methods=["GET", "POST"])])
    http = TestClient(app)

    import anyio
    url = anyio.run(provider.authorize, client_info(), params())
    cid = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["cid"][0]

    page = http.get(f"/oauth/consent?cid={cid}")
    assert page.status_code == 200
    assert "Slaptažodis" in page.text


def test_a_wrong_password_does_not_mint_a_code():
    provider = oauth.Provider("secret")
    app = Starlette(routes=[Route("/oauth/consent", provider.consent_response,
                                  methods=["GET", "POST"])])
    http = TestClient(app)

    import anyio
    url = anyio.run(provider.authorize, client_info(), params())
    cid = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["cid"][0]

    response = http.post("/oauth/consent", data={"cid": cid, "password": "wrong"},
                         follow_redirects=False)
    assert response.status_code == 401
    assert provider.codes == {}


def test_the_right_password_redirects_with_a_code():
    provider = oauth.Provider("secret")
    app = Starlette(routes=[Route("/oauth/consent", provider.consent_response,
                                  methods=["GET", "POST"])])
    http = TestClient(app)

    import anyio
    url = anyio.run(provider.authorize, client_info(), params())
    cid = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["cid"][0]

    response = http.post("/oauth/consent", data={"cid": cid, "password": "secret"},
                         follow_redirects=False)
    assert response.status_code == 302
    location = urllib.parse.urlparse(response.headers["location"])
    assert location.netloc == "localhost:9999"
    code = urllib.parse.parse_qs(location.query)["code"][0]
    assert code in provider.codes
    assert provider.codes[code].client_id == "client-1"
    assert urllib.parse.parse_qs(location.query)["state"] == ["xyz"]


@pytest.mark.anyio
async def test_a_code_becomes_a_token_pair_and_the_code_is_spent():
    provider = oauth.Provider("secret")
    info = client_info()
    await provider.register_client(info)
    url = await provider.authorize(info, params())
    cid = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["cid"][0]

    import anyio
    # Drive the consent handler directly: the HTTP surface is covered above.
    provider.pending[cid] = (info, params())
    code = oauth.AuthorizationCode(
        code="code-1", scopes=["legal:read"], expires_at=time.time() + 60,
        client_id=info.client_id, code_challenge="challenge",
        redirect_uri="http://localhost:9999/cb",
        redirect_uri_provided_explicitly=True, resource=None,
    )
    provider.codes["code-1"] = code

    token = await provider.exchange_authorization_code(info, code)
    assert token.access_token and token.refresh_token
    assert "code-1" not in provider.codes
    assert (await provider.load_access_token(token.access_token)).client_id == "client-1"


@pytest.mark.anyio
async def test_expired_access_tokens_are_not_returned():
    provider = oauth.Provider("secret")
    provider.access["old"] = oauth.AccessToken(
        token="old", client_id="c", scopes=[], expires_at=int(time.time()) - 1
    )
    assert await provider.load_access_token("old") is None
    assert "old" not in provider.access


@pytest.mark.anyio
async def test_refresh_rotates_the_token():
    provider = oauth.Provider("secret")
    info = client_info()
    await provider.register_client(info)
    record = oauth.RefreshToken(token="r1", client_id="client-1",
                                scopes=["legal:read"], expires_at=None)
    provider.refresh["r1"] = record

    rotated = await provider.exchange_refresh_token(info, record, ["legal:read"])
    assert rotated.refresh_token != "r1"
    assert "r1" not in provider.refresh
    assert rotated.refresh_token in provider.refresh


@pytest.mark.anyio
async def test_revocation_removes_both_kinds_of_token():
    provider = oauth.Provider("secret")
    access = oauth.AccessToken(token="a1", client_id="c", scopes=[], expires_at=None)
    refresh = oauth.RefreshToken(token="r1", client_id="c", scopes=[], expires_at=None)
    provider.access["a1"] = access
    provider.refresh["r1"] = refresh

    await provider.revoke_token(access)
    await provider.revoke_token(refresh)
    assert provider.access == {} and provider.refresh == {}
