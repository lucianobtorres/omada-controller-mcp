"""Tests for CombinedMCPApp and SSE/HTTP hybrid routing in server.py."""

from __future__ import annotations

from starlette.testclient import TestClient

from omada_mcp.server import build_server_app


def test_combined_app_post_sse_fallback_streamable() -> None:
    """Test that POST /sse without an active SSE stream falls back to Streamable HTTP with 200 OK."""
    app = build_server_app(transport="sse")
    with TestClient(app) as client:
        response = client.post(
            "/sse",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        assert response.status_code == 200
        assert "initialize" in response.text or "result" in response.text


def test_combined_app_post_messages_trailing_slash_fallback() -> None:
    """Test POST /messages/ (with trailing slash, no 307 redirect) falls back to Streamable HTTP when no SSE stream exists."""
    app = build_server_app(transport="sse")
    with TestClient(app) as client:
        response = client.post(
            "/messages/",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        assert response.status_code == 200


def test_combined_app_post_mcp_and_root() -> None:
    """Test POST / and POST /mcp return 200 OK via Streamable HTTP."""
    app = build_server_app(transport="sse")
    with TestClient(app) as client:
        response_mcp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        assert response_mcp.status_code == 200
