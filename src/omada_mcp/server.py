"""MCP server exposing a TP-Link Omada controller's Open API.

Design: 2000+ non-deprecated, non-MSP operations exist across Omada API
versions and firmware releases (call server_info for this controller's exact
count). Registering one MCP tool per operation would
put thousands of tool schemas in every request's context before the agent
asks anything - the opposite of token efficient. Instead this server exposes
a small, fixed set of meta-tools (search / inspect / call) backed by an
operation catalog built from the controller's own live OpenAPI spec:

- search_operations   find candidate operations by keyword
- get_operation_schema fetch one operation's parameters/body schema on demand
- call_operation       invoke any cataloged operation by id
- refresh_catalog      re-fetch the live spec (pick up a firmware upgrade
                        without restarting the container)
- server_info          which spec is loaded (live vs bundled, version, count)

Two curated convenience tools (list_sites, list_devices) cover the two most
common first questions without a search round-trip. Everything else - the
full Omada API surface, whatever this controller's firmware actually
supports - is reachable through call_operation.

Trust model: call_operation can reach every cataloged operation, including
destructive ones (reboot, config changes), using this server's own
client-credentials session - it doesn't ask the caller to re-authenticate
per call. Anyone who can reach this server's transport can drive the whole
Omada API. Over stdio that's just "whoever can run this process." Over HTTP
(the Docker deployment) that's "whoever can reach the port" - see
OMADA_MCP_AUTH_TOKEN below and the README's trust-model section.

Zero-trust posture for an untrusted LAN: don't trust the network, verify
every request, log everything. Bearer token auth (above) plus, on the HTTP
transport: Host/Origin header validation against DNS-rebinding attacks,
rate limiting, and structured audit logging of every tool call - see
_build_middleware and main() below. Transport encryption itself is not this
server's job: put a reverse proxy (Caddy, nginx) or an overlay network
(Tailscale, WireGuard) in front of it rather than hand-rolling TLS here -
see the README's trust-model section.
"""

from __future__ import annotations

import hmac
import logging
import os
import sys
from typing import Any

import fastmcp
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

from omada_auth.auth import OmadaSession
from omada_mcp import catalog as cat

BASE_URL = os.environ.get("OMADA_BASE_URL", "https://your-controller.local:8043")
VERIFY_SSL = os.environ.get("OMADA_VERIFY_SSL", "false").lower() == "true"
AUTH_TOKEN = os.environ.get("OMADA_MCP_AUTH_TOKEN")
READ_ONLY = os.environ.get("OMADA_MCP_READ_ONLY", "true").lower() in ("true", "1", "yes")
RATE_LIMIT_PER_SECOND = float(os.environ.get("OMADA_MCP_RATE_LIMIT", "20"))
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("OMADA_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()
]


class _StaticBearerAuth(TokenVerifier):
    """Single shared-secret bearer token, for a home-LAN deployment.

    Not OAuth - just a constant-time comparison against one token from
    OMADA_MCP_AUTH_TOKEN. Enough to stop "anyone on the LAN segment" from
    driving the whole Omada API with no credential of their own; not
    intended to substitute for network segmentation.
    """

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._token):
            return None
        return AccessToken(token=token, client_id="omada-mcp-lan", scopes=[])


if AUTH_TOKEN:
    _auth = _StaticBearerAuth(AUTH_TOKEN)
else:
    _auth = None
    print(
        "warning: OMADA_MCP_AUTH_TOKEN not set - the MCP HTTP endpoint is unauthenticated; "
        "anyone who can reach it can drive the full Omada API. Fine for stdio/loopback-only use, "
        "set OMADA_MCP_AUTH_TOKEN before exposing this beyond localhost.",
        file=sys.stderr,
    )

_audit_logger = logging.getLogger("omada_mcp.audit")
_middleware: list[Middleware] = [
    RateLimitingMiddleware(max_requests_per_second=RATE_LIMIT_PER_SECOND, global_limit=False),
    StructuredLoggingMiddleware(logger=_audit_logger, include_payloads=True),
]

mcp = FastMCP(
    name="omada",
    instructions=(
        "Query and manage a TP-Link Omada SDN controller on the local LAN. "
        "Start with list_sites/list_devices/list_clients/get_topology for common questions, or "
        "search_operations to find any other operation this controller "
        "supports, then get_operation_schema before calling an unfamiliar one."
    ),
    auth=_auth,
    middleware=_middleware,
)

session: OmadaSession
_catalog: cat.Catalog


def _startup() -> None:
    """Build the session and operation catalog.

    Deliberately not module-level: importing this module (for tests, a
    REPL, `fastmcp dev` inspection) shouldn't require live credentials and
    a reachable controller. Only actually running the server does.
    """
    global session, _catalog, BASE_URL, VERIFY_SSL, READ_ONLY
    BASE_URL = os.environ.get("OMADA_BASE_URL", BASE_URL)
    VERIFY_SSL = os.environ.get("OMADA_VERIFY_SSL", "false").lower() == "true"
    READ_ONLY = os.environ.get("OMADA_MCP_READ_ONLY", "true").lower() in ("true", "1", "yes")

    session = OmadaSession(base_url=BASE_URL, verify_ssl=VERIFY_SSL)
    spec, source = cat.load_spec(session.base_url, session.verify_ssl)
    _catalog = cat.build_catalog(spec, source, read_only=READ_ONLY)


@mcp.tool
def server_info() -> dict[str, Any]:
    """Report which Omada API spec this server is running against."""
    return {
        "controller_base_url": session.base_url,
        "spec_source": _catalog.source,
        "api_version": _catalog.version,
        "operation_count": len(_catalog.operations),
        "read_only": READ_ONLY,
    }


@mcp.tool
def refresh_catalog() -> dict[str, Any]:
    """Re-fetch the controller's live OpenAPI spec and rebuild the operation catalog.

    Call this after a controller firmware upgrade to pick up new/changed/
    removed endpoints without restarting this server.
    """
    global _catalog
    spec, source = cat.load_spec(session.base_url, session.verify_ssl)
    _catalog = cat.build_catalog(spec, source, read_only=READ_ONLY)
    return server_info()


@mcp.tool
def search_operations(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search this controller's Omada API operations by keyword.

    Matches against operation id, summary, and path, e.g. "client", "reboot",
    "wlan ssid". Returns operation_id, method, path, and summary for each
    match - call get_operation_schema on one before calling it if its
    parameters aren't obvious from the summary.
    """
    return cat.search(_catalog, query, limit=limit)


@mcp.tool
def get_operation_schema(operation_id: str) -> dict[str, Any]:
    """Get one operation's method, path, parameters, and request body schema."""
    op = _catalog.operations.get(operation_id)
    if op is None:
        raise ValueError(
            f"unknown operation_id {operation_id!r}; use search_operations to find one"
        )
    return {
        "operation_id": op.operation_id,
        "method": op.method,
        "path": op.path,
        "summary": op.summary,
        "parameters": op.parameters,
        "request_body_schema": op.request_body_schema,
    }


@mcp.tool
def call_operation(
    operation_id: str,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    """Call any cataloged Omada API operation by its operation_id.

    omadacId is filled in automatically. Other path parameters (e.g.
    siteId, apMac) go in path_params; query-string parameters in
    query_params; a JSON request body (for POST/PUT operations that take
    one) in body. Use get_operation_schema first if unsure what an
    operation needs.
    """
    op = _catalog.operations.get(operation_id)
    if op is None:
        raise ValueError(
            f"unknown or disabled operation_id {operation_id!r}; use search_operations to find available ones"
        )
    if READ_ONLY and op.method != "GET":
        raise ValueError(
            f"operation_id {operation_id!r} ({op.method}) blocked: OMADA_MCP_READ_ONLY is active."
        )
    if not cat.is_operation_allowed(op.method, op.path, op.operation_id, op.summary, read_only=READ_ONLY):
        raise ValueError(
            f"operation_id {operation_id!r} is disabled under security allowlist policy."
        )
    path = cat.build_request_path(op, session.omadac_id, path_params or {})
    return session.request(op.method, path, **cat.build_call_kwargs(query_params, body))


def _get_default_site_id() -> str:
    env_site_id = os.environ.get("OMADA_SITE_ID")
    if env_site_id:
        return env_site_id
    try:
        sites_res = session.request(
            "GET",
            f"/openapi/v1/{session.omadac_id}/sites",
            params={"page": 1, "pageSize": 10},
        )
        sites: list[dict[str, Any]] = []
        if isinstance(sites_res, list):
            sites = sites_res
        elif isinstance(sites_res, dict):
            sites = sites_res.get("data", []) or sites_res.get("result", [])
        if sites and isinstance(sites[0], dict) and "id" in sites[0]:
            return str(sites[0]["id"])
    except Exception:
        pass
    return ""


@mcp.tool
def list_sites(page: int = 1, page_size: int = 100) -> Any:
    """List sites this controller manages."""
    return session.request(
        "GET",
        f"/openapi/v1/{session.omadac_id}/sites",
        params={"page": page, "pageSize": page_size},
    )


@mcp.tool
def list_devices(site_id: str | None = None, page: int = 1, page_size: int = 50) -> Any:
    """List managed devices (access points, switches, gateways) for a specific site or default site."""
    s_id = site_id or _get_default_site_id()
    if not s_id:
        raise ValueError("site_id is required to list devices. Set OMADA_SITE_ID in .env or pass site_id.")
    path = f"/openapi/v1/{session.omadac_id}/sites/{s_id}/devices"
    return session.request("GET", path, params={"page": page, "pageSize": page_size})


@mcp.tool
def get_lan_networks(site_id: str | None = None, page: int = 1, page_size: int = 50) -> Any:
    """Get LAN network configurations (subnets, gateways, DNS servers) for a specific site or default site."""
    s_id = site_id or _get_default_site_id()
    if not s_id:
        raise ValueError("site_id is required to get LAN networks. Set OMADA_SITE_ID in .env or pass site_id.")
    path = f"/openapi/v1/{session.omadac_id}/sites/{s_id}/lan-networks"
    return session.request("GET", path, params={"page": page, "pageSize": page_size})


@mcp.tool
def list_clients(site_id: str | None = None, page: int = 1, page_size: int = 50) -> Any:
    """List connected clients for a specific site or default site."""
    s_id = site_id or _get_default_site_id()
    if not s_id:
        raise ValueError("site_id is required to list clients. Set OMADA_SITE_ID in .env or pass site_id.")
    path = f"/openapi/v1/{session.omadac_id}/sites/{s_id}/clients"
    return session.request("GET", path, params={"page": page, "pageSize": page_size})


@mcp.tool
def get_topology(site_id: str | None = None) -> Any:
    """Get network topology data for a specific site or default site."""
    s_id = site_id or _get_default_site_id()
    if not s_id:
        raise ValueError("site_id is required to get topology. Set OMADA_SITE_ID in .env or pass site_id.")
    path = f"/openapi/v1/{session.omadac_id}/sites/{s_id}/topology"
    return session.request("GET", path)


@mcp.tool
def list_ip_groups(site_id: str | None = None, page: int = 1, page_size: int = 50) -> Any:
    """List IP group profiles for a specific site or default site."""
    s_id = site_id or _get_default_site_id()
    if not s_id:
        raise ValueError("site_id is required to list IP groups. Set OMADA_SITE_ID in .env or pass site_id.")
    path = f"/openapi/v1/{session.omadac_id}/sites/{s_id}/profiles/groups"
    return session.request("GET", path, params={"page": page, "pageSize": page_size})


@mcp.tool
def list_gateway_acls(site_id: str | None = None, page: int = 1, page_size: int = 50) -> Any:
    """List gateway ACL rules for a specific site or default site."""
    s_id = site_id or _get_default_site_id()
    if not s_id:
        raise ValueError("site_id is required to list gateway ACLs. Set OMADA_SITE_ID in .env or pass site_id.")
    path = f"/openapi/v1/{session.omadac_id}/sites/{s_id}/acls/osg-acls"
    return session.request("GET", path, params={"page": page, "pageSize": page_size})


@mcp.tool
def list_time_range_profiles(site_id: str | None = None, page: int = 1, page_size: int = 50) -> Any:
    """List time range profiles for a specific site or default site."""
    s_id = site_id or _get_default_site_id()
    if not s_id:
        raise ValueError("site_id is required to list time range profiles. Set OMADA_SITE_ID in .env or pass site_id.")
    path = f"/openapi/v1/{session.omadac_id}/sites/{s_id}/time-range-profiles"
    return session.request("GET", path, params={"page": page, "pageSize": page_size})


class MCPRoutingMiddleware:
    """ASGI Middleware to resolve MCP client routing quirks:

    1. Intercepts POST requests sent to /sse, /mcp, or / and rewrites their path to /messages
       so Starlette routes them to the SSE message handler (handle_post_message).
    2. If POST /messages is missing session_id in query_string, auto-resolves session_id
       from active SSE sessions if an active session exists.
    """

    def __init__(self, app: Any, sse_transport: Any = None) -> None:
        self.app = app
        self.sse_transport = sse_transport

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            method = scope.get("method", "GET")
            path = scope.get("path", "")

            # If client sends POST to /sse, /mcp, or /, rewrite to /messages
            if method == "POST" and path in ("/sse", "/mcp", "/"):
                scope["path"] = "/messages"
                scope["raw_path"] = b"/messages"

            # If client posts to /messages without session_id in query string
            if method == "POST" and scope.get("path") == "/messages":
                query_string = scope.get("query_string", b"").decode("utf-8")
                if "session_id=" not in query_string and self.sse_transport is not None:
                    writers = getattr(self.sse_transport, "_read_stream_writers", {})
                    if writers:
                        # Auto-resolve session_id to active session
                        active_session_id = next(iter(writers.keys())).hex
                        new_query = f"session_id={active_session_id}"
                        if query_string:
                            new_query = f"{query_string}&{new_query}"
                        scope["query_string"] = new_query.encode("utf-8")

        await self.app(scope, receive, send)


def build_server_app(transport: str = "sse") -> Any:
    """Construct the FastMCP HTTP/SSE ASGI application wrapped with MCPRoutingMiddleware."""
    app = mcp.http_app(
        transport=transport,
        host_origin_protection="auto",
        allowed_hosts=ALLOWED_HOSTS or None,
    )

    sse_transport = None
    for r in getattr(app, "routes", []):
        if getattr(r, "path", None) == "/messages" and hasattr(r, "app") and hasattr(r.app, "__self__"):
            sse_transport = r.app.__self__
            break

    return MCPRoutingMiddleware(app, sse_transport=sse_transport)


def main() -> None:
    _startup()
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    transport = fastmcp.settings.transport
    if transport in ("http", "streamable-http", "sse"):
        import uvicorn

        host = fastmcp.settings.host
        port = fastmcp.settings.port
        app = build_server_app(transport=transport)
        logging.info(f"Starting Omada MCP server with transport {transport!r} on http://{host}:{port}/")
        uvicorn.run(app, host=host, port=port, log_level=fastmcp.settings.log_level.lower())
    else:
        mcp.run()


if __name__ == "__main__":
    main()
