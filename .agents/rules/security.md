# Diretrizes de Segurança (Security by Design - Omada MCP)

## 1. Gestão de Segredos & Credenciais
- **Zero Hardcoded Credentials:** Proibido credenciais de teste ou segredos no código-fonte.
- **Hierarquia de Carregamento de Configurações:**
  1. Variáveis de ambiente explícitas (`OMADA_CLIENT_ID`, `OMADA_CLIENT_SECRET`).
  2. Arquivos de segredos Docker/K8s (`OMADA_CLIENT_ID_FILE`, `OMADA_CLIENT_SECRET_FILE`).
  3. Arquivo local `.env` ou fallback `~/.omada.env`.
- **Sanitização de Exceções:** Ao lidar com erros HTTP na renovação de token ou chamadas autenticadas, limpe os objetos de requisição/resposta para evitar que o `client_secret` ou `accessToken` vazem em tracebacks ou arquivos de log.

## 2. Segurança de Rede e Transporte (MCP Endpoint)
- **Bearer Token Mandatório em HTTP:** Para implantações via HTTP/Docker expostas além do `localhost`, o token de autenticação `OMADA_MCP_AUTH_TOKEN` deve ser obrigatoriamente configurado e validado via `_StaticBearerAuth`.
- **Proteção contra DNS Rebinding:** Manter a verificação de `Host` e `Origin` ativada em transportes HTTP/SSE através de `ALLOWED_HOSTS`.
- **Conexões Locais / Tailscale com SSL Autoassinado:** O ambiente local via Tailscale pode utilizar certificados autoassinados (`OMADA_VERIFY_SSL=false`). O middleware de auditoria deve registar todas as chamadas independentemente do estado do SSL.

## 3. Prevenção de Path Traversal em Chamadas Dinâmicas
- **Sanitização de Parâmetros de Rota:** Todo parâmetro de rota em `build_request_path` deve passar por `quote(str(v), safe="")` para garantir que caracteres como `../` ou `/` não consigam escapar do prefixo da rota da API do Omada.

## 4. Auditoria e Controle de Acesso (Allowlist)
- **Audit Logging:** Todas as chamadas realizadas via `call_operation` devem passar pelo middleware de auditoria estruturada (`StructuredLoggingMiddleware`).
- **Política de Menor Privilégio:** Em ambientes de produção/automação, restrinja o acesso a operações mutating (alterações de rede, reinicialização de dispositivos) ativando a Allowlist de leitura.
