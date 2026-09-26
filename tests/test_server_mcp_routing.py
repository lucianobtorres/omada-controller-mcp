"""Tests for MCPRoutingMiddleware and SSE/HTTP routing in server.py."""

from __future__ import annotations

from typing import Any

from starlette.testclient import TestClient

from omada_mcp.server import MCPRoutingMiddleware, build_server_app


def test_mcp_routing_middleware_rewrites_post_sse() -> None:
    """Test that POST /sse is rewritten to /messages without raising 405 Method Not Allowed."""
    app = build_server_app(transport="sse")
    client = TestClient(app)

    # POST /sse should be rewritten to /messages (returns 400 because no session_id is provided, not 405)
    response = client.post("/sse", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
    assert response.status_code == 400
    assert "session_id is required" in response.text


def test_mcp_routing_middleware_rewrites_post_root_and_mcp() -> None:
    """Test that POST / or /mcp is also rewritten to /messages for SSE compatibility."""
    app = build_server_app(transport="sse")
    client = TestClient(app)

    response_root = client.post("/", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
    assert response_root.status_code == 400

    response_mcp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})
    assert response_mcp.status_code == 400
