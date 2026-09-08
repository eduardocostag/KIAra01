# Kiara Web API — teste independente de contrato

**Data:** 2026-09-05  
**Status:** **PASS parcial / NO-GO para API completa**

## Escopo e resultado

O baseline `packages/contracts/openapi.yaml` foi comparado com a aplicação FastAPI e
validado por `tests/web_api/test_contract_alignment.py`. O subconjunto implementado
passou nos seguintes controles:

- toda rota/método implementado pertence ao contrato canônico;
- auth ausente retorna 401 no envelope com `request_id`;
- demo requer habilitação explícita em development/test e é proibido em production;
- CORS aceita só a origem configurada e os métodos/cabeçalhos contratuais;
- correlação inválida é substituída por UUID seguro, sem reflexão;
- listagem e detalhe são derivados do tenant verificado;
- recurso de outro tenant retorna 404 genérico, sem revelar dados;
- health, identidade, paginação e ETag foram alinhados ao OpenAPI.

## Bugs comprovados e corrigidos

1. O erro usava `correlation_id`, enquanto o schema exige `request_id`.
2. Readiness retornava `ready`, fora do enum contratual `ok`.
3. `/v1/me` expunha `organization_id` e `demo`, divergindo de `CurrentUser`.
4. A inbox usava envelopes próprios e vazava `organization_id` interno.
5. A fixture não atendia `ThreadSummary`/`ThreadDetail`.
6. O CORS não permitia métodos e cabeçalhos publicados para mutações.

O campo `demo` foi removido deliberadamente de `/v1/me`: o endpoint agora segue o
contrato, enquanto o modo demo segue coberto na configuração e no adaptador. Não há
fallback silencioso em produção.

## Alinhamento de operações

| Operação contratada | Implementação |
|---|---:|
| `GET /health/live` | Sim |
| `GET /health/ready` | Sim |
| `GET /v1/me` | Sim |
| `GET /v1/inbox/threads` | Sim |
| `GET /v1/inbox/threads/{thread_id}` | Sim |
| `POST /v1/inbox/threads/{thread_id}/drafts` | **Não** |
| `POST /v1/drafts/{draft_id}/approve` | **Não** |
| `POST /v1/threads/{thread_id}/qualify` | **Não** |
| `GET /v1/pipeline` | **Não** |
| `PATCH /v1/pipeline/{entry_id}` | **Não** |

O inventário automatizado impede rotas implementadas fora do contrato, sem mascarar as
cinco operações ainda ausentes. Elas mantêm o status NO-GO para API completa.

## Evidência executável

```text
python -m pytest -q tests/web_api
26 passed, 1 warning in 0.95s

python -m ruff check tests/web_api/test_contract_alignment.py tests/web_api/test_api.py services/api/kiara_api/main.py services/api/kiara_api/adapters/demo.py
All checks passed!

git diff --check -- tests/web_api services/api/kiara_api/main.py services/api/kiara_api/adapters/demo.py
sem saída (aprovado)
```

O warning é uma depreciação interna do `fastapi.testclient`. Não houve teste de carga,
PostgreSQL real, IdP real nem tráfego Meta real; portanto não há evidência de SLA p95,
capacidade 10x ou prontidão de produção.

## Próximos gates

1. Implementar as cinco operações ausentes com idempotência e ETag.
2. Obter nome/slug do workspace de metadados confiáveis de membership.
3. Validar PostgreSQL com RLS, OIDC/JWKS real e CORS no domínio final.
4. Adicionar rate limiting e teste de carga antes do lançamento.
