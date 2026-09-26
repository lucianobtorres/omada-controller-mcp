# Arquitetura e Estrutura do Omada Controller MCP

## 1. Visão Geral e Identidade Core
O **omada-controller-mcp** é um servidor MCP (Model Context Protocol) de alto desempenho construído em Python com **FastMCP**. Seu objetivo é expor a API OpenAPI de um TP-Link Omada SDN Controller local (ou remoto via Tailscale) para assistentes de IA com consumo eficiente de contexto.

Diferente de expor milhares de rotas estáticas na janela de contexto da LLM, o servidor utiliza um **Catálogo Dinâmico de Operações** que indexa a especificação OpenAPI oficial do controller em tempo de execução e fornece meta-ferramentas (`search_operations`, `get_operation_schema`, `call_operation`).

---

## 2. Estrutura do Projeto

```text
omada-controller-mcp/
├── .agents/                    # Regras e skills especializadas do assistente
│   ├── rules/                  # Regras ativas (Arquitetura, Segurança, Diretrizes)
│   └── skills/                 # Habilidades técnicas (uv, clean-arch, debugging)
├── openapi/                    # Especificações da API
│   └── controller-spec.json    # Snapshot OpenAPI para fallback off-line
├── src/
│   ├── omada_auth/             # Gestão de Sessão & Autenticação
│   │   ├── __init__.py
│   │   └── auth.py             # OmadaSession, token refresh, tratamento IPv4/SSL
│   ├── omada_client/           # Cliente HTTP & Tipos da API Omada
│   │   ├── api/                # Endpoints gerados por categoria
│   │   ├── client.py           # Client e AuthenticatedClient httpx
│   │   ├── errors.py           # Exceções customizadas
│   │   └── types.py            # Types e Data Containers
│   └── omada_mcp/              # Servidor MCP & Catálogo Dinâmico
│       ├── __init__.py
│       ├── catalog.py          # Parsers OpenAPI, indexação, busca e construção de rotas
│       └── server.py           # Servidor FastMCP, middlewares, auth e registro de ferramentas
├── tests/                      # Suíte de testes unitários e de integração
├── pyproject.toml              # Configurações do projeto e dependências (uv)
└── test_connection.py          # Script de validação rápida de conexão e autenticação
```

---

## 3. Fluxo de Execução e Catálogo Dinâmico

```text
[Cliente MCP / LLM]
       │
       ├── 1. list_sites() / list_devices() ─────────► [OmadaSession] ──► [Omada Controller]
       │
       ├── 2. search_operations("client") ──────────► [Catalog Index] (Busca em memória)
       │
       ├── 3. get_operation_schema(op_id) ──────────► [Catalog Specs] (Schema sob demanda)
       │
       └── 4. call_operation(op_id, params, body) ──► [OmadaSession] ──► [Omada Controller]
```

1. **Autenticação:** `OmadaSession` obtém o `omadacId` e gera o `AccessToken` via `/openapi/authorize/token`.
2. **Carregamento da Spec:** Em tempo de inicialização, `catalog.py` consome `/v3/api-docs/00%20All` diretamente do controller. Se o controller estiver inacessível, utiliza o fallback local `openapi/controller-spec.json`.
3. **Despacho Dinâmico:** `call_operation` substitui automaticamente o `{omadacId}`, codifica parâmetros de rota com segurança e encaminha a requisição HTTP via `httpx`.
