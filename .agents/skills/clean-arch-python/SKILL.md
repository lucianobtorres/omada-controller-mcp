---
name: clean-arch-python
description: Clean Architecture e boas práticas SOLID aplicadas a projetos Python com uv, FastMCP e clientes HTTP de API.
---

# Clean Architecture & SOLID em Python com UV

## Princípios de Camadas (Omada Controller MCP)
1. **Domain & Models (`omada_client/models`, `omada_client/types.py`):** Dataclasses imutáveis e schemas Pydantic V2 sem dependências diretas de entrada/saída.
2. **Auth & Session (`omada_auth/auth.py`):** Gerenciamento de credenciais, renovação de AccessToken e comunicação direta com a API do Omada.
3. **Catalog & Operations (`omada_mcp/catalog.py`):** Indexação e parsing da especificação OpenAPI em memória, busca de schemas e geração de rotas seguras.
4. **Server & Presentation (`omada_mcp/server.py`):** Servidor FastMCP expondo meta-ferramentas (`search_operations`, `get_operation_schema`, `call_operation`) e atalhos diretos.

## Regras Estritas
- Manter separação limpa entre a camada de comunicação HTTP (`omada_client`/`omada_auth`) e a interface do servidor MCP (`omada_mcp`).
- Tipagem estrita com type annotations completas em 100% das assinaturas de funções.
- Tratar todas as falhas de rede/HTTP de forma defensiva sem expor credenciais brutas em logs ou tracebacks.