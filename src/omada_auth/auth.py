"""Auth shim for the Omada Open API.

The generated SDK's spec has no securitySchemes. Omada uses a custom
``Authorization: AccessToken=<token>`` header, wired here by hand.
"""

from __future__ import annotations

import os
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from omada_client.client import AuthenticatedClient, Client

DEFAULT_ENV_FILE = Path.home() / ".omada.env"
TOKEN_SAFETY_MARGIN_SECONDS = 60


def _force_ipv4(base_url: str) -> str:
    """Resolve base_url's hostname to an IPv4 address.

    mDNS hosts (``*.local``) often also advertise a link-local IPv6 address
    that httpx (no happy-eyeballs fallback, unlike curl) picks first and
    fails to route to. Force AF_INET up front instead.
    """
    parts = urlsplit(base_url)
    try:
        ipv4 = socket.getaddrinfo(parts.hostname, None, socket.AF_INET)[0][4][0]
    except socket.gaierror:
        return base_url
    netloc = f"{ipv4}:{parts.port}" if parts.port else ipv4
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _env_or_file(name: str) -> str:
    """Read NAME from the environment, or from the file at NAME_FILE (Docker/K8s secrets)."""
    value = os.environ.get(name)
    if value:
        return value
    path = os.environ.get(f"{name}_FILE")
    if path:
        return Path(path).read_text().strip()
    return ""


def _load_env_file(path: Path) -> None:
    """Populate os.environ from a KEY=VALUE env file, without overwriting existing vars."""
    if not path.is_file():
        return
    if path.stat().st_mode & 0o077:
        print(
            f"warning: {path} is readable by group/other "
            f"(mode {oct(path.stat().st_mode)[-3:]}); recommend chmod 600",
            file=sys.stderr,
        )
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


@dataclass
class OmadaSession:
    """Holds a live, auto-refreshing Omada Open API session.

    Credentials are read from OMADA_CLIENT_ID / OMADA_CLIENT_SECRET (env, or
    ~/.omada.env as a fallback). repr=False on the secret/token fields only
    suppresses repr()/print() - it does not cover vars(), dataclasses.asdict(),
    or pickling, so don't dump session state through those either.
    """

    base_url: str = "https://your-controller.local:8043"
    # _force_ipv4 (below) rewrites base_url's hostname to a bare IP, which
    # breaks TLS hostname verification against the controller's self-signed
    # cert - verify_ssl=True has no working config here. Default to False to
    # match how this is actually meant to run (see README).
    verify_ssl: bool = False
    client_id: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)
    _omadac_id: str | None = field(default=None, init=False, repr=False)
    _token: str | None = field(default=None, init=False, repr=False)
    _token_expires_at: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_url = _force_ipv4(self.base_url)
        # Explicit env / secret-file injection outranks the personal
        # ~/.omada.env fallback, so a Docker/K8s-mounted secret always wins
        # over a stale dotfile if both happen to be present.
        self.client_id = self.client_id or _env_or_file("OMADA_CLIENT_ID")
        self.client_secret = self.client_secret or _env_or_file("OMADA_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            _load_env_file(DEFAULT_ENV_FILE)
            self.client_id = self.client_id or _env_or_file("OMADA_CLIENT_ID")
            self.client_secret = self.client_secret or _env_or_file("OMADA_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "OMADA_CLIENT_ID / OMADA_CLIENT_SECRET not set "
                "(env, OMADA_CLIENT_ID_FILE/OMADA_CLIENT_SECRET_FILE, or ~/.omada.env)"
            )

    def _raw_client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, verify=self.verify_ssl, timeout=15.0)

    @property
    def omadac_id(self) -> str:
        if self._omadac_id is None:
            try:
                with self._raw_client() as c:
                    resp = c.get("/api/info")
                    resp.raise_for_status()
                    body = resp.json()
            except (httpx.HTTPError, ValueError) as e:
                # ValueError covers resp.json() on a non-JSON (e.g. HTML) body -
                # a reachable-but-misconfigured OMADA_BASE_URL shouldn't crash
                # with a raw traceback.
                raise RuntimeError(f"GET /api/info failed: {type(e).__name__}") from None
            if body.get("errorCode") != 0:
                raise RuntimeError(f"GET /api/info failed: errorCode={body.get('errorCode')}")
            self._omadac_id = body["result"]["omadacId"]
        return self._omadac_id

    def _fetch_token(self) -> None:
        # Any httpx exception here carries the raw request, whose body has
        # client_secret in plaintext (e.g. exc.request.content) - never let
        # one escape this function, so a caller logging the exception can't
        # accidentally print the secret.
        try:
            with self._raw_client() as c:
                resp = c.post(
                    "/openapi/authorize/token",
                    params={"grant_type": "client_credentials"},
                    json={
                        "omadacId": self.omadac_id,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                )
                resp.raise_for_status()
                body = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise RuntimeError(f"token request failed: {type(e).__name__}") from None
        if body.get("errorCode") != 0:
            raise RuntimeError(
                f"token request failed: errorCode={body.get('errorCode')} msg={body.get('msg')}"
            )
        result = body["result"]
        self._token = result["accessToken"]
        self._token_expires_at = (
            time.monotonic() + result["expiresIn"] - TOKEN_SAFETY_MARGIN_SECONDS
        )

    @property
    def token(self) -> str:
        if self._token is None or time.monotonic() >= self._token_expires_at:
            self._fetch_token()
        assert self._token is not None
        return self._token

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Authenticated call to an absolute controller path, e.g.
        ``/openapi/v1/<omadacId>/sites`` (v1 and v2 both fine - the caller
        supplies the full path, already substituted).

        For callers (the MCP server's dynamic operation dispatch, ad hoc
        scripts) that don't need a full generated-SDK operation module.
        Returns the parsed ``result`` field; raises RuntimeError on a
        non-zero ``errorCode`` or a non-2xx response.
        """
        full_url = f"{self.base_url}{path}"
        try:
            with self._raw_client() as c:
                resp = c.request(
                    method,
                    path,
                    headers={"Authorization": f"AccessToken={self.token}"},
                    **kwargs,
                )
                status_code = resp.status_code
                raw_text = resp.text
                resp.raise_for_status()
                body = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            resp_obj = getattr(e, "response", None)
            st = resp_obj.status_code if resp_obj is not None else "N/A"
            txt = resp_obj.text if resp_obj is not None else str(e)
            print(f"\n[DEBUG] URL requisitada: {full_url}")
            print(f"[DEBUG] Status HTTP: {st}")
            print(f"[DEBUG] Resposta bruta do Omada: {txt}\n", file=sys.stderr)
            raise RuntimeError(f"request to {path} failed: {type(e).__name__}") from None

        if body.get("errorCode") != 0:
            print(f"\n[DEBUG] URL requisitada: {full_url}")
            print(f"[DEBUG] Status HTTP: {status_code} (errorCode={body.get('errorCode')})")
            print(f"[DEBUG] Resposta bruta do Omada: {raw_text}\n", file=sys.stderr)
            raise RuntimeError(f"Omada API error {body.get('errorCode')}: {body.get('msg')}")
        return body.get("result")

    def client(self) -> AuthenticatedClient:
        """An AuthenticatedClient for generated API calls.

        Generated operations take ``omadac_id`` as an explicit path
        parameter (every spec path embeds ``{omadacId}``), so base_url stays
        the bare controller URL rather than pre-baking the id into it.
        """
        return AuthenticatedClient(
            base_url=self.base_url,
            token=f"AccessToken={self.token}",
            prefix="",
            verify_ssl=self.verify_ssl,
        )

    def unauthenticated_client(self) -> Client:
        return Client(base_url=self.base_url, verify_ssl=self.verify_ssl)
