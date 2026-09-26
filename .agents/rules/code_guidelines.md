# Diretrizes de Desenvolvimento e Padrões de Código

## 1. Padrões de Código Python (PEP 8 & Strict Typing)
- **Versão:** Python 3.12+ (compatível com Python 3.14).
- **Tipagem Estrita:** Uso obrigatório de Type Annotations em 100% das funções e métodos. Proibido o uso de `any` não tipado.
- **Imports Modernos:** Inclua `from __future__ import annotations` em todos os módulos Python.
- **Gerenciador de Pacotes:** `uv` é o único gerenciador de dependências e ambientes virtuais permitido no projeto (`uv sync`, `uv run`, `uv pip`).

## 2. Programação Defensiva & Proteção de Segredos
- **Vazamento de Credenciais:** Nunca inclua `client_secret` ou `accessToken` em logs ou exceções. Em blocos `try/except` com `httpx`, capture a exceção e relance um `RuntimeError` genérico sem expor a requisição crua.
- **Resolução IPv4 Defensiva:** Como mDNS (`*.local`) no Windows pode tentar IPv6 e falhar em certificados self-signed, a resolução IPv4 forçada em `_force_ipv4` deve ser mantida.
- **Cláusulas de Guarda:** Prefira saídas antecipadas em funções para evitar aninhamento excessivo de blocos `if/else`.

## 3. Padrões para Ferramentas FastMCP (`@mcp.tool`)
- **Docstrings Orientadas a LLM:** Cada ferramenta FastMCP deve possuir uma docstring clara descrevendo quando usá-la, seus parâmetros e valores de retorno.
- **Simplicidade e Performance:** Ferramentas devem ter responsabilidades bem delimitadas. Evite operações bloqueantes na thread principal.
- **Validação de Schema:** Use Pydantic V2 ou `dataclasses` para validar estruturas de dados complexas.

## 4. Código Gerado & Deployment Docker
- **SDK Gerado (`src/omada_client/`):** A pasta `src/omada_client/` é 100% gerada dinamicamente com `openapi-python-client`. **NUNCA edite os arquivos de `src/omada_client/` manualmente.** Para atualizar, edite a especificação `openapi/controller-spec.json` e execute `./scripts/regenerate.sh`.
- **Pré-requisito Docker:** O script `scripts/build_venv_for_docker.sh` deve ser obrigatoriamente executado antes de `docker build` ou `docker compose up --build`. O Dockerfile copia as dependências de `.venv-docker`.
