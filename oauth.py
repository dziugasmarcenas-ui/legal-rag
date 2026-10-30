"""OAuth 2.1 authorization server for the MCP endpoint.

Connector directories do not accept a static bearer token: Claude and ChatGPT
both run an authorization-code flow, so the server has to speak it. This is the
smallest honest implementation of that flow.

What it is: dynamic client registration, an authorization-code grant with PKCE
(the verifier is checked by the SDK), short-lived access tokens and rotating
refresh tokens. What it is not: multi-user authentication. There is one
operator, and the consent page asks for one shared connection password. Saying
otherwise would be worse than the limitation.

State is in memory, so a redeploy invalidates tokens and clients re-authorize.
That is acceptable for one instance and is stated in the README rather than
hidden. A multi-instance deployment needs a store, and would need it before
selling access.
"""

import base64
import hashlib
import html
import os
import secrets
import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.responses import HTMLResponse, RedirectResponse

ACCESS_TTL = 3600
REFRESH_TTL = 30 * 24 * 3600
CODE_TTL = 300

CONSENT_PAGE = """<!doctype html>
<html lang="lt"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prijungti legal-rag</title>
<style>
 body{{font:16px/1.5 system-ui,-apple-system,sans-serif;margin:0;background:#f7f7f8;color:#1c1c1e}}
 main{{max-width:420px;margin:12vh auto;padding:28px;background:#fff;border:1px solid #e6e6ea;border-radius:12px}}
 h1{{font-size:19px;margin:0 0 6px}} p{{color:#555;margin:0 0 18px}}
 label{{display:block;font-size:13px;margin-bottom:6px;color:#333}}
 input{{width:100%;padding:10px 12px;border:1px solid #d6d6dc;border-radius:8px;font-size:15px;box-sizing:border-box}}
 button{{margin-top:14px;width:100%;padding:11px;border:0;border-radius:8px;background:#2563eb;color:#fff;font-size:15px;cursor:pointer}}
 .err{{color:#b3261e;font-size:13px;margin-top:10px}} code{{font-size:12px;color:#666}}
</style></head><body><main>
<h1>Prijungti „legal-rag“ prie jūsų DI</h1>
<p>Įveskite prisijungimo slaptažodį, kad ši programėlė gautų prieigą prie Darbo kodekso paieškos.</p>
<p><code>{client}</code></p>
<form method="post" action="/oauth/consent">
  <input type="hidden" name="cid" value="{cid}">
  <label for="password">Slaptažodis</label>
  <input id="password" name="password" type="password" autocomplete="current-password" autofocus required>
  <button type="submit">Leisti prieigą</button>
  {error}
</form>
</main></body></html>"""


def _now():
    return time.time()


def _verify(password, expected):
    """Constant-time comparison; a plain == leaks length and prefix."""
    if not expected:
        return False
    return secrets.compare_digest(password.encode(), expected.encode())


class Provider(OAuthAuthorizationServerProvider):
    def __init__(self, password, scopes=("legal:read",)):
        self.password = password
        self.default_scopes = list(scopes)
        self.clients = {}
        self.pending = {}   # consent id -> (client, params)
        self.codes = {}
        self.access = {}
        self.refresh = {}

    # --- registration -----------------------------------------------------
    async def get_client(self, client_id):
        return self.clients.get(client_id)

    async def register_client(self, client_info):
        self.clients[client_info.client_id] = client_info

    # --- authorization ----------------------------------------------------
    async def authorize(self, client, params: AuthorizationParams) -> str:
        """Return the URL the user is sent to. The SDK redirects there."""
        cid = secrets.token_urlsafe(18)
        self.pending[cid] = (client, params)
        return f"/oauth/consent?cid={cid}"

    def _take_pending(self, cid):
        entry = self.pending.pop(cid, None)
        if entry is None:
            return None
        client, params = entry
        # A consent link is disposable; ten minutes is generous for typing.
        return client, params

    async def consent_response(self, request):
        """GET renders the form, POST mints a code and redirects to the client."""
        if request.method == "GET":
            cid = request.query_params.get("cid", "")
            entry = self.pending.get(cid)
            if entry is None:
                return HTMLResponse(
                    "<p>Nuoroda nebegalioja. Pradėkite prisijungimą iš naujo.</p>",
                    status_code=400,
                )
            client, _ = entry
            return HTMLResponse(CONSENT_PAGE.format(
                cid=html.escape(cid),
                client=html.escape(client.client_name or client.client_id),
                error="",
            ))

        form = await request.form()
        cid = form.get("cid", "")
        entry = self.pending.get(cid)
        if entry is None:
            return HTMLResponse(
                "<p>Nuoroda nebegalioja. Pradėkite prisijungimą iš naujo.</p>",
                status_code=400,
            )

        client, params = entry
        if not _verify(form.get("password", ""), self.password):
            return HTMLResponse(CONSENT_PAGE.format(
                cid=html.escape(cid),
                client=html.escape(client.client_name or client.client_id),
                error='<p class="err">Neteisingas slaptažodis.</p>',
            ), status_code=401)

        del self.pending[cid]
        code = secrets.token_urlsafe(32)
        self.codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or self.default_scopes,
            expires_at=_now() + CODE_TTL,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )

        separator = "&" if "?" in str(params.redirect_uri) else "?"
        target = f"{params.redirect_uri}{separator}code={code}"
        if params.state:
            target += f"&state={params.state}"
        return RedirectResponse(target, status_code=302)

    # --- tokens -----------------------------------------------------------
    async def load_authorization_code(self, client, authorization_code):
        return self.codes.get(authorization_code)

    async def exchange_authorization_code(self, client, authorization_code):
        self.codes.pop(authorization_code.code, None)

        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        scopes = authorization_code.scopes

        self.access[access] = AccessToken(
            token=access,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=int(_now() + ACCESS_TTL),
            resource=authorization_code.resource,
        )
        self.refresh[refresh] = RefreshToken(
            token=refresh,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=int(_now() + REFRESH_TTL),
            resource=authorization_code.resource,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL,
            scope=" ".join(scopes),
            refresh_token=refresh,
        )

    async def load_refresh_token(self, client, refresh_token):
        return self.refresh.get(refresh_token)

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        self.refresh.pop(refresh_token.token, None)

        access = secrets.token_urlsafe(32)
        rotated = secrets.token_urlsafe(32)
        granted = scopes or refresh_token.scopes

        self.access[access] = AccessToken(
            token=access,
            client_id=client.client_id,
            scopes=granted,
            expires_at=int(_now() + ACCESS_TTL),
            resource=refresh_token.resource,
        )
        self.refresh[rotated] = RefreshToken(
            token=rotated,
            client_id=client.client_id,
            scopes=granted,
            expires_at=int(_now() + REFRESH_TTL),
            resource=refresh_token.resource,
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL,
            scope=" ".join(granted),
            refresh_token=rotated,
        )

    async def load_access_token(self, token):
        record = self.access.get(token)
        if record is None:
            return None
        if record.expires_at and record.expires_at < _now():
            self.access.pop(token, None)
            return None
        return record

    async def revoke_token(self, token):
        for store in (self.access, self.refresh):
            store.pop(getattr(token, "token", None), None)


def build():
    """Provider when a consent password is configured, otherwise None.

    Unset means OAuth is off and the static MCP_TOKEN path stays in use, so a
    local deployment does not accidentally publish an authorization server with
    no password.
    """
    password = os.environ.get("OAUTH_PASSWORD", "")
    if not password:
        return None
    return Provider(password)
