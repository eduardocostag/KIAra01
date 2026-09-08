# Evidência E2E local do fluxo comercial web

Data: 2026-09-05  
Responsável: `test-automation-engineer`  
Resultado: **PASS local, produção ainda não comprovada**

## Escopo validado

O teste `tests/web_api/test_commercial_flow_e2e.py` percorre a API ASGI real criada por `create_app`, com adapters em memória exclusivos do teste:

1. identidade verificada em `/v1/me`;
2. listagem e detalhe da Inbox Instagram;
3. criação de rascunho sem envio;
4. rejeição de aprovação sem `If-Match` e com versão obsoleta;
5. aprovação humana vinculada à versão;
6. qualificação do thread;
7. leitura e atualização do Pipeline;
8. replay idempotente de rascunho, aprovação, qualificação e Pipeline;
9. isolamento opaco de leitura e mutação entre dois tenants.

O teste também comprova que a aprovação apenas grava um registro local: a conversa continua contendo somente a mensagem inbound e o app de teste não expõe transporte Instagram/outbound. Nenhuma rede, credencial Meta, webhook externo ou Send API participa da execução.

## Determinismo e dados

- Cada teste recebe uma nova aplicação, repositórios e dados próprios.
- Os tenants são derivados de tokens resolvidos por um verificador local; o cliente nunca envia `organization_id`.
- Não há espera temporal, retry para obter verde, dependência de ordem ou seed compartilhado.
- Seleção de recursos é feita por IDs opacos controlados pela fixture.

## Comandos e resultados

```text
python -m pytest -q tests/web_api/test_commercial_flow_e2e.py
2 passed, 1 warning in 0.37s

python -m pytest -q tests/web_api
40 passed, 1 warning in 1.71s

10 execuções consecutivas do teste focal, sem retry
20/20 casos aprovados; 0 falhas observadas; 0 pass-on-retry
```

O aviso único é `StarletteDeprecationWarning`: a versão instalada do `fastapi.testclient` ainda usa a integração legada com `httpx`. Ele não alterou os resultados, mas deve ser resolvido atualizando a combinação FastAPI/Starlette/httpx em uma mudança de dependências controlada.

## Limites e decisão de release

Este PASS cobre integração HTTP local e regras de segurança dos adapters em memória. Não valida PostgreSQL/RLS real, concorrência multiprocesso, Clerk real, Meta Graph API, entrega de mensagem, deploy, navegador ou carga. Portanto, a jornada assistida local está aprovada por este gate; envio real e produção permanecem **NO-GO** até testes de staging isolados e evidência ponta a ponta com as integrações oficiais.
