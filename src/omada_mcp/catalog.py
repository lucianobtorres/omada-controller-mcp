"""Operation catalog built from the Omada controller's own OpenAPI spec.

Loaded live from the controller at startup (or refreshed on demand) so the
catalog tracks whichever endpoints actually exist on *that* controller's
firmware. No per-endpoint code to fall out of sync as Omada API versions
add, remove, or deprecate operations - falls back to a bundled snapshot
(``openapi/controller-spec.json``) only if the controller can't be reached.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

_DEV_SPEC_PATH = Path(__file__).resolve().parent.parent.parent / "openapi" / "controller-spec.json"
_METHODS = ("get", "post", "put", "delete", "patch")
_OMADAC_ID_PARAM = "omadacId"
_ALLOWED_KEYWORDS = (
    "device",
    "client",
    "vlan",
    "network",
    "lan-network",
    "lan-networks",
    "acl",
    "topology",
    "site",
    "profile",
    "group",
    "time-range",
    "osg-acl",
)


def is_operation_allowed(
    method: str,
    path: str,
    operation_id: str = "",
    summary: str = "",
    read_only: bool = True,
) -> bool:
    """Validate if an operation satisfies security guardrails.

    When read_only is True (default):
    - Only GET requests are allowed.
    - Path/operation_id/summary must match allowed domains: devices, clients, networks/vlans, ACLs, topology, sites.
    """
    if read_only and method.upper() != "GET":
        return False

    text_to_check = f"{path} {operation_id} {summary}".lower()
    return any(kw in text_to_check for kw in _ALLOWED_KEYWORDS)


@dataclass(frozen=True)
class Operation:
    operation_id: str
    method: str
    path: str  # full template, e.g. /openapi/v1/{omadacId}/sites/{siteId}/clients
    summary: str
    deprecated: bool
    parameters: list[dict[str, Any]]  # path/query params, omadacId excluded (auto-filled)
    request_body_schema: dict[str, Any] | None


@dataclass
class Catalog:
    operations: dict[str, Operation]
    source: str  # "live" or "bundled:<path>"
    version: str | None


def _fetch_live_spec(base_url: str, verify_ssl: bool) -> dict[str, Any] | None:
    try:
        resp = httpx.get(f"{base_url}/v3/api-docs/00%20All", verify=verify_ssl, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError):
        # ValueError: reachable but non-JSON body (e.g. a misconfigured
        # OMADA_BASE_URL hitting an HTML page) - fall back same as unreachable.
        return None


def _bundled_spec_path() -> Path | None:
    """Locate the bundled spec snapshot.

    __file__-relative only resolves correctly for an editable/dev install
    (this repo's own src-layout); a non-editable install (e.g. the Docker
    image, per uv's recommended multi-stage build) puts this file under
    .venv/lib/.../site-packages instead, so also check cwd and an explicit
    override - whichever the deployment actually puts the file at.
    """
    candidates = [
        p
        for p in (
            os.environ.get("OMADA_MCP_SPEC_PATH"),
            "openapi/controller-spec.json",
            str(_DEV_SPEC_PATH),
        )
        if p
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def _load_bundled_spec() -> dict[str, Any] | None:
    path = _bundled_spec_path()
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_spec(base_url: str, verify_ssl: bool) -> tuple[dict[str, Any], str]:
    """Prefer the controller's own live spec; fall back to the bundled snapshot."""
    live = _fetch_live_spec(base_url, verify_ssl)
    if live is not None:
        return live, "live"
    bundled_path = _bundled_spec_path()
    bundled = _load_bundled_spec()
    if bundled is not None:
        print(
            f"warning: could not reach {base_url} for a live spec; "
            f"using bundled snapshot {bundled_path}",
            file=sys.stderr,
        )
        return bundled, f"bundled:{bundled_path}"
    raise RuntimeError(
        f"no OpenAPI spec available: controller at {base_url} unreachable "
        f"and no bundled snapshot found (set OMADA_MCP_SPEC_PATH, or run from the repo root)"
    )


def _resolve_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    node: Any = spec
    try:
        for part in ref.lstrip("#/").split("/"):
            node = node[part]
    except (KeyError, TypeError):
        return {"$ref": ref, "note": "unresolvable reference, not expanded"}
    return node


def _resolve_schema(
    spec: dict[str, Any], schema: Any, depth: int = 4, _seen: frozenset[str] = frozenset()
) -> Any:
    """Dereference $ref for a self-contained schema, with cycle/depth guards."""
    if depth <= 0 or not isinstance(schema, dict):
        return schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref in _seen:
            return {"$ref": ref, "note": "circular or too-deep reference, not expanded further"}
        return _resolve_schema(spec, _resolve_ref(spec, ref), depth - 1, _seen | {ref})
    resolved = dict(schema)
    # Map-typed schemas (dict-valued additionalProperties) aren't walked -
    # none exist in the bundled spec today, add if a future firmware uses one.
    if "properties" in resolved:
        resolved["properties"] = {
            k: _resolve_schema(spec, v, depth - 1, _seen) for k, v in resolved["properties"].items()
        }
    if "items" in resolved:
        resolved["items"] = _resolve_schema(spec, resolved["items"], depth - 1, _seen)
    for key in ("allOf", "oneOf", "anyOf"):
        if key in resolved:
            resolved[key] = [_resolve_schema(spec, s, depth - 1, _seen) for s in resolved[key]]
    return resolved


def build_catalog(
    spec: dict[str, Any],
    source: str,
    *,
    include_deprecated: bool = False,
    read_only: bool = False,
) -> Catalog:
    """Index every {omadacId}-scoped operation in the spec by operationId.

    Excludes MSP ({mspId}-scoped) paths and deprecated operations by default.
    Applies OMADA_MCP_READ_ONLY and domain allowlist guardrails when read_only=True.
    """
    operations: dict[str, Operation] = {}
    for path, item in spec.get("paths", {}).items():
        if f"{{{_OMADAC_ID_PARAM}}}" not in path:
            continue
        for method, op in item.items():
            if method not in _METHODS or not isinstance(op, dict):
                continue
            if op.get("deprecated") and not include_deprecated:
                continue
            operation_id = op.get("operationId")
            if not operation_id:
                continue
            summary = op.get("summary", "")
            if read_only and not is_operation_allowed(method, path, operation_id, summary, read_only=True):
                continue
            params = [
                {
                    "name": p["name"],
                    "in": p["in"],
                    "required": p.get("required", False),
                    "schema": _resolve_schema(spec, p.get("schema", {})),
                }
                for p in op.get("parameters", [])
                if p["name"] != _OMADAC_ID_PARAM
            ]
            body_schema = None
            body = (
                op.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema")
            )
            if body:
                body_schema = _resolve_schema(spec, body)
            operations[operation_id] = Operation(
                operation_id=operation_id,
                method=method.upper(),
                path=path,
                summary=op.get("summary", ""),
                deprecated=bool(op.get("deprecated")),
                parameters=params,
                request_body_schema=body_schema,
            )
    version = spec.get("info", {}).get("version")
    return Catalog(operations=operations, source=source, version=version)


def search(catalog: Catalog, query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Case-insensitive substring search over operationId, summary, and path."""
    q = query.lower().strip()
    hits = [
        op
        for op in catalog.operations.values()
        if q in f"{op.operation_id} {op.summary} {op.path}".lower()
    ]
    hits.sort(key=lambda o: (o.operation_id.lower().find(q) != 0, len(o.path), o.operation_id))
    return [
        {"operation_id": o.operation_id, "method": o.method, "path": o.path, "summary": o.summary}
        for o in hits[:limit]
    ]


def build_request_path(op: Operation, omadac_id: str, path_params: dict[str, Any]) -> str:
    """Substitute {omadacId} (auto) and caller-supplied {name} path params into op.path.

    Each value is percent-encoded with no "safe" characters, so a value
    like "../../msp/1/sites" can't escape this operation's own path
    template (a "/" in a path param becomes "%2F", a single opaque path
    segment, not an extra separator).
    """
    values = {_OMADAC_ID_PARAM: omadac_id, **path_params}
    required_path_params = {p["name"] for p in op.parameters if p["in"] == "path"}
    missing = required_path_params - values.keys()
    if missing:
        raise ValueError(f"{op.operation_id} missing required path_params: {sorted(missing)}")
    encoded = {k: quote(str(v), safe="") for k, v in values.items()}
    try:
        return op.path.format(**encoded)
    except KeyError as e:
        raise ValueError(f"{op.operation_id} references unknown path param {e}") from None


def build_call_kwargs(
    query_params: dict[str, Any] | None, body: dict[str, Any] | None
) -> dict[str, Any]:
    """httpx kwargs for a dispatched call.

    body uses an ``is not None`` check (not truthy) so ``body={}`` - a
    real, meaningful "send an empty JSON object" - still gets sent;
    query_params uses a truthy check so an empty/absent query string
    doesn't add a stray ``params=``.
    """
    kwargs: dict[str, Any] = {}
    if query_params:
        kwargs["params"] = query_params
    if body is not None:
        kwargs["json"] = body
    return kwargs
