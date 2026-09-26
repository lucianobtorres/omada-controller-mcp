# Protocolo de Sincronização de Contexto e Definição de Pronto (DoD)

Este documento estabelece o fluxo de auditoria e validação para edições no projeto **omada-controller-mcp**.

---

## 🔄 Fluxo de Trabalho e Auditoria de Mudanças

Ao concluir qualquer implementação ou refatoração no servidor MCP, cliente ou autenticação, siga o ciclo de verificação:

```text
[Desenvolvimento Concluído]
           │
           ▼
[Execução de Verificação Automatizada (`uv run python test_connection.py` ou `pytest`)]
           │
           ▼
[Auditoria de Regras em `.agents/rules/`]
           │
    ┌──────┴────────────────────────┐
    ▼                               ▼
[Houve impacto estrutural?]   [Apenas fix pontual?]
    │                               │
    ▼                               ▼
[Atualize .agents/rules/]      [Pronto para fechamento]
```

---

## 🎯 Critérios de Avaliação

| Módulo Impactado | Gatilho de Atualização | Arquivo Alvo |
| :--- | :--- | :--- |
| **Arquitetura & Servidor MCP** | Mudanças em `server.py`, `catalog.py` ou na gestão do FastMCP | [architecture.md](file:///c:/Users/lucia/Documents/Projetos/omada-controller-mcp/.agents/rules/architecture.md) |
| **Autenticação & Cliente HTTP** | Mudanças em `auth.py`, renovação de tokens ou cliente `httpx` | [code_guidelines.md](file:///c:/Users/lucia/Documents/Projetos/omada-controller-mcp/.agents/rules/code_guidelines.md) |
| **Segurança & Redes** | Ajustes em SSL, Bearer Tokens, Allowlist ou sanitização de rotas | [security.md](file:///c:/Users/lucia/Documents/Projetos/omada-controller-mcp/.agents/rules/security.md) |
