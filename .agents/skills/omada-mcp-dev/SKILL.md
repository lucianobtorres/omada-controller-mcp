---
name: omada-mcp-dev
description: Habilidade especializada para desenvolvimento, expansão e teste do servidor MCP do Omada Controller e catálogo OpenAPI dinâmico.
---

# Omada MCP Server Development

Guia para desenvolvimento, teste e adição de recursos no servidor MCP do TP-Link Omada Controller.

## Quando usar esta skill:
- Ao adicionar novas ferramentas MCP (`@mcp.tool`) em `src/omada_mcp/server.py`.
- Ao modificar o parser do catálogo OpenAPI em `src/omada_mcp/catalog.py`.
- Ao implementar filtros de segurança (Allowlist, Read-Only mode).
- Ao realizar testes manuais ou automatizados da API do Omada Controller.
- Ao preparar compilações de containers Docker ou regenerar o SDK.

## Comandos Principais:
- **Testar autenticação e listagem rápida:**
  ```powershell
  uv run python test_connection.py
  ```
- **Executar suíte de testes unitários:**
  ```powershell
  uv run pytest
  ```
- **Executar servidor MCP localmente (stdio):**
  ```powershell
  uv run python -m omada_mcp
  ```
- **Depurar com FastMCP CLI:**
  ```powershell
  uv run fastmcp dev src/omada_mcp/server.py
  ```
- **Preparar ambiente virtual para Docker (Obrigatório antes de `docker build`):**
  ```powershell
  ./scripts/build_venv_for_docker.sh
  ```
- **Regenerar cliente Python OpenAPI (`src/omada_client/`):**
  ```powershell
  ./scripts/regenerate.sh
  ```
