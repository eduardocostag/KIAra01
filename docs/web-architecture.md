# Arquitetura web incremental — Kiara Lead Intelligence

Status: **proposta para implementação; não representa deploy nem prontidão de produção**  
Responsável: `software-architect`  
Data: 2026-09-04

## Decisão executiva

A Kiara web será um **monólito modular distribuído em três processos implantáveis**, sem microserviços por domínio:

1. `apps/web`: Next.js App Router, interface e BFF mínimo;
2. `services/api`: aplicação Python, API HTTP e recepção de webhooks;
3. `services/worker`: o mesmo pacote Python, executando jobs duráveis.

PostgreSQL será a fonte de verdade multi-tenant. O domínio Python existente (scoring, Hunter, consentimento, opt-out, qualificação e governança) deve ser extraído por casos de uso e reutilizado; PySide e SQLite permanecem na edição desktop durante a migração. A web não acessará SQLite, não importará módulos de UI e não chamará stores diretamente.

O primeiro corte vendável atende uma organização B2C que recebe DMs no Instagram: login → onboarding → conexão oficial da conta → inbox → qualificação → rascunho → aprovação humana → envio → pipeline e auditoria. Cold DM, scraping e envio sem aprovação continuam proibidos.

```text
Navegador
   |
   v
Next.js/Vercel -- OIDC session --> Clerk
   |  HTTPS com token de usuário
   v
Python API (ASGI) -----------------------> PostgreSQL
   |       ^                                  ^
   |       |                                  |
   |       +---- status/SSE ou polling -------+
   v
fila durável/outbox ---> Python worker ---> Meta Instagram API
   ^
   |
Meta webhook (HMAC sobre corpo bruto)
```

## Contextos e dependências

| Contexto | Responsabilidade | Dependências permitidas |
|---|---|---|
| Identity & Tenancy | usuário, organização, membership, papel | provedor OIDC, PostgreSQL |
| Instagram | OAuth, conta conectada, webhook, inbox, envio e reconciliação | Meta, vault, jobs |
| Consumers | identidade B2C, consentimento, supressão, touchpoints | aplicação/domínio apenas |
| Qualification | Hunter, score, temperatura, recomendação explicável | Consumers, provider de modelo por porta |
| Conversations | threads, mensagens, drafts e aprovações | Instagram, Audit |
| Pipeline | estágio, próxima ação, responsável, histórico e undo | Consumers, Audit |
| Jobs | execução durável, retry, lease, cancelamento e DLQ/revisão | PostgreSQL e/ou broker gerenciado |
| Audit & Analytics | trilha imutável, funil, SLIs e uso | outbox; sem coordenar comandos |

Regra de dependência: rotas HTTP e adapters dependem dos casos de uso; casos de uso dependem de portas; domínio não depende de Next.js, FastAPI, ORM, banco, fila ou Meta. Não se replica regra comercial em TypeScript: a UI apenas apresenta estados e solicita comandos.

## Estrutura de diretórios alvo

```text
apps/
  web/
    src/app/
      (public)/
      (auth)/sign-in/
      (workspace)/[organizationSlug]/
        inbox/
        consumers/
        pipeline/
        analytics/
        settings/integrations/
      api/auth/callback/          # somente callback/sessão quando necessário
      error.tsx
      global-error.tsx
    src/components/
    src/features/                 # view models e componentes por contexto
    src/lib/api/                  # cliente tipado gerado de OpenAPI
    src/lib/auth/
    src/styles/
    tests/
services/
  api/
    kiara_api/
      http/routes/v1/
      http/middleware/
      application/               # commands, queries, UoW, autorização
      domain/                    # políticas sem framework
      ports/
      adapters/postgres/
      adapters/meta/
      adapters/identity/
      contracts/
    migrations/
    tests/
  worker/
    kiara_worker/
      handlers/
      scheduler/
      main.py
packages/
  contracts/                     # OpenAPI publicado e artefatos gerados
  ui/                            # tokens/componentes web da Kiara
deploy/
  docker/
  runbooks/
```

O pacote Python compartilhado pode permanecer inicialmente sob `app/`; a estrutura acima é destino, não autorização para mover tudo em um único PR. Cada extração começa por um caso de uso, mantém adapters SQLite existentes e ganha um adapter PostgreSQL.

## Contrato de tenancy e autorização

Clerk é a escolha inicial de identidade por acelerar login, recuperação de conta, MFA e organizações. A dependência deve ficar atrás de `IdentityVerifier` para permitir migração futura para Auth0/Entra. O browser recebe sessão OIDC; a API valida localmente assinatura, `iss`, `aud`, `exp` e JWKS com cache. Nunca confia em `organization_id`, papel ou usuário enviados no body.

Papéis iniciais:

- `owner`: billing futuro, membros, integrações e políticas;
- `admin`: integrações, usuários e operação;
- `operator`: inbox, qualificação, pipeline, drafts e aprovação quando autorizado;
- `viewer`: leitura e analytics.

Toda request autenticada produz `RequestContext(user_id, organization_id, membership_id, role, correlation_id)`. A organização ativa é resolvida pela membership verificada. O repositório aplica simultaneamente:

1. filtro explícito por `organization_id` em todas as chaves e queries;
2. PostgreSQL Row-Level Security como defesa adicional;
3. `SET LOCAL app.organization_id` e `app.user_id` dentro de transação;
4. testes que tentam acesso cruzado entre dois tenants.

Tabelas de negócio têm `organization_id NOT NULL`, índices iniciados por esse campo e unicidade tenant-scoped, por exemplo `UNIQUE (organization_id, instagram_account_id, external_message_id)`. Workers recebem `organization_id` no payload assinado/persistido e abrem o mesmo contexto; uma conexão do pool nunca preserva contexto de request anterior.

## Contrato HTTP v1

Base: `/v1`; JSON UTF-8; datas RFC 3339 UTC; IDs UUID/ULID opacos. O schema OpenAPI versionado em `packages/contracts/openapi.yaml` gera o cliente TypeScript. Alterações compatíveis são aditivas; breaking changes exigem `/v2` ou período formal de depreciação.

Envelope de erro:

```json
{
  "error": {
    "code": "approval_required",
    "message": "Esta mensagem precisa de aprovação.",
    "correlation_id": "01...",
    "details": {}
  }
}
```

Endpoints do primeiro corte:

| Método e rota | Resultado | Autorização/idempotência |
|---|---|---|
| `GET /v1/me` | usuário, organizações e capacidades | autenticado |
| `GET /v1/inbox/threads` | cursor de threads, filtros e unread | viewer+; tenant implícito |
| `GET /v1/inbox/threads/{id}` | mensagens, consumidor e qualificação | viewer+; tenant implícito |
| `POST /v1/inbox/threads/{id}/drafts` | cria rascunho versionado | operator+; `Idempotency-Key` |
| `POST /v1/drafts/{id}/approve` | aprovação do hash exato | capability `outbound.approve`; `If-Match` |
| `POST /v1/drafts/{id}/send` | enfileira envio, retorna `202 JobRef` | rascunho aprovado; `Idempotency-Key` |
| `POST /v1/threads/{id}/qualify` | retorna/enfileira qualificação | operator+; `Idempotency-Key` |
| `PATCH /v1/consumers/{id}` | altera estágio/próxima ação | operator+; `If-Match` |
| `GET /v1/jobs/{id}` | estado/progresso/erro seguro | viewer+; mesmo tenant |
| `POST /v1/jobs/{id}/cancel` | solicita cancelamento | autor ou admin |
| `POST /v1/integrations/instagram/oauth/start` | URL OAuth e state one-time | admin+ |
| `GET /v1/integrations/instagram/oauth/callback` | troca código server-side | state + PKCE quando suportado |
| `DELETE /v1/integrations/instagram/{id}` | revoga/desconecta | admin+; confirmação/auditoria |
| `GET /webhooks/meta/instagram` | challenge de verificação | verify token |
| `POST /webhooks/meta/instagram` | persiste evento e responde rápido | HMAC do raw body; sem sessão web |

Comandos mutáveis carregam internamente `command_id`, ator, tenant, correlação e versão esperada. `Idempotency-Key` é obrigatório nos POSTs repetíveis e seu resultado fica tenant-scoped. `If-Match` usa a versão do agregado e conflito retorna `409`. Listas usam cursor estável, não offset. O frontend usa Server Components para leitura inicial; interações e atualizações ficam em Client Components pequenos. Server Actions não substituem a API pública nem contêm regra de domínio.

## Modelo de dados web inicial

O schema físico é único por ambiente, com isolamento por linha. Tabelas mínimas:

- `organizations`, `users`, `memberships`;
- `instagram_connections` (somente referência ao segredo no vault), `instagram_accounts`;
- `consumers`, `consumer_identities`, `consents`, `suppressions`;
- `conversation_threads`, `messages`, `message_drafts`, `approvals`, `outbound_actions`;
- `qualification_runs`, `qualification_signals`;
- `pipeline_entries`, `stage_events`, `operations`;
- `inbox_events`, `jobs`, `job_attempts`, `outbox_events`, `audit_events`;
- projeções analíticas deriváveis.

Mensagens externas usam IDs do provedor e payload bruto criptografado/retido por prazo definido. Campos usados em busca, política e auditoria são normalizados. Segredos e tokens Meta não ficam no banco em texto: somente `secret_ref`, metadados de escopo, expiração e status.

## Webhook, jobs e envio Instagram

O endpoint público roda no serviço Python, pois precisa de bytes brutos, HMAC e persistência transacional. Fluxo:

1. validar tamanho/content-type e `X-Hub-Signature-256` antes de parsear;
2. mapear conta externa para organização sem aceitar tenant do payload;
3. inserir `inbox_event` com chave de deduplicação;
4. na mesma transação, registrar outbox/job de normalização;
5. responder `200` rapidamente; IA nunca roda na request do webhook;
6. worker normaliza, aplica opt-out/consentimento, atualiza thread e enfileira qualificação;
7. a UI recebe atualização por polling curto inicialmente; SSE pode ser adicionado depois.

Jobs usam Postgres com claim `FOR UPDATE SKIP LOCKED`, lease/heartbeat, backoff com jitter e estados `queued`, `running`, `succeeded`, `failed`, `cancelled`, `needs_review`. Começar com Postgres evita Redis obrigatório no MVP; migrar o transporte para fila gerenciada somente se volume/latência medidos justificarem. Outbox garante que persistência e publicação não se separem.

Envio segue `drafted -> approved -> queued -> sending -> sent | failed | unknown`. A aprovação armazena hash, versão, ator e expiração; editar invalida. Timeout após POST Meta produz `unknown`, nunca retry cego. Opt-out, conexão revogada, kill switch ou janela/política inválida bloqueiam o claim do job, inclusive se o item já estava na fila.

## Deploy e operação

| Componente | Destino inicial | Razão |
|---|---|---|
| Next.js | Vercel | deploy preview, CDN e operação simples |
| API Python | serviço container ASGI com região fixa (ex.: Render/Fly/Railway) | processo Python persistente, health checks e raw-body webhook |
| Worker Python | processo separado no mesmo provedor/região | jobs não presos ao limite de request serverless |
| PostgreSQL | gerenciado, mesma região da API/worker | backup/PITR, TLS e baixa latência |
| Segredos | secret manager do provedor | rotação e acesso por identidade do workload |
| Arquivos | object storage privado com URLs assinadas | anexos e exports fora do banco |

Ambientes `development`, `preview/staging` e `production` têm bancos, chaves, apps Meta e domínios separados. Preview não recebe webhook de produção. Deploy segue migrate-expand → API/worker → web → backfill → contract; rollback de código nunca depende de desfazer migration destrutiva.

Checks: `/health/live` não consulta dependências; `/health/ready` valida banco e migrations. Logs estruturados incluem correlação, tenant pseudonimizado, job e integração, sem mensagem/token/PII. Alertas iniciais: assinatura inválida anômala, backlog/idade de jobs, `unknown` outbound, falha/latência Meta, expiração de token, erro 5xx e atraso da outbox. Banco exige backup diário e PITR; restore em staging é gate de produção.

## Migração incremental sem big bang

| Fase | Entrega | Critério de saída |
|---|---|---|
| 0 — fundação | monorepo, OpenAPI, CI, ambientes, threat model e ADRs aceitos | builds independentes; nenhum dado real |
| 1 — identidade | login, organização, membership, RBAC e RLS | testes cross-tenant e revogação de sessão passam |
| 2 — leitura | importar cópia autorizada de consumers/threads e exibir inbox/pipeline read-only | reconciliação por contagem/hash; desktop segue fonte |
| 3 — Instagram inbound | OAuth, vault, webhook, dedupe, inbox e opt-out | sandbox Meta E2E, replay e assinatura inválida comprovados |
| 4 — qualificação | Hunter e scoring via casos de uso Python | paridade por fixtures e explicação persistida |
| 5 — outbound assistido | draft, aprovação, kill switch, job e reconciliação | nenhum envio sem aprovação; timeout vira `unknown` |
| 6 — corte do cliente piloto | Postgres vira fonte do tenant piloto; desktop read-only/export | backup/restore, observabilidade e rollback ensaiados |
| 7 — escala | analytics, billing/limites, fila externa se necessário | decisão baseada em SLO/carga, não antecipação |

Não haverá sincronização bidirecional permanente SQLite↔Postgres. A migração é exportar → validar → importar com idempotência → reconciliar → definir um único writer por tenant. O desktop pode consumir a API futuramente, mas isso é decisão separada.

## ADR-001: monólito modular com três processos

### Status
Proposto

### Contexto
A base é um aplicativo Python modular e o time precisa chegar rápido a um SaaS sem duplicar regras nem operar dezenas de serviços.

### Opções

- microserviços por domínio: escalabilidade independente, porém contratos distribuídos, custo operacional e consistência complexa cedo demais;
- reescrever tudo em Next.js: um deploy aparente, porém perde a base Python testada e duplica regras;
- API/worker Python + web Next.js: preserva domínio e separa ciclos de UI e execução, ao custo de dois runtimes.

### Decisão
Adotar a terceira opção e manter módulos explícitos dentro do serviço Python.

### Consequências
Deploy e observabilidade precisam cobrir três processos, mas a arquitetura continua pequena, testável e reversível. Microserviços só serão extraídos por demanda comprovada de escala, segurança ou autonomia de equipe.

## ADR-002: PostgreSQL compartilhado com RLS por organização

### Status
Proposto

### Contexto
SQLite não atende múltiplos usuários e processos remotos. É necessário impedir vazamento entre clientes sem multiplicar bancos no início.

### Opções

- banco por tenant: isolamento forte, porém migrations e operação caras;
- schema por tenant: isolamento intermediário, ainda com alto custo operacional;
- schema compartilhado e `organization_id`: operação simples, exige disciplina e controles em profundidade.

### Decisão
Schema compartilhado, chaves tenant-scoped, filtros obrigatórios e RLS. Clientes regulados poderão ganhar banco dedicado depois sem mudar contratos de aplicação.

### Consequências
Testes de isolamento e contexto transacional são gates de todo repositório/query. Analytics globais exigem papel técnico separado e auditado.

## ADR-003: Clerk atrás de uma porta de identidade

### Status
Proposto

### Contexto
Construir login, MFA, recuperação e organizações atrasaria o piloto e ampliaria risco. Acoplamento direto ao fornecedor dificultaria evolução enterprise.

### Decisão
Usar Clerk inicialmente e traduzir claims para `IdentityPrincipal` interno. Autorização de negócio e memberships canônicas permanecem na API/Postgres.

### Consequências
Há custo e dependência externa, reduzidos por OIDC/JWT padrão e adapter isolado. Indisponibilidade do provedor impede novas sessões, mas tokens válidos podem continuar até expiração conforme política.

## ADR-004: jobs Postgres primeiro

### Status
Proposto

### Contexto
Webhook, qualificação e envio não podem depender do ciclo de request. Uma fila adicional aumenta superfície operacional antes de existir carga medida.

### Decisão
Implementar tabela de jobs/outbox em PostgreSQL com worker separado e semântica de lease. Avaliar fila gerenciada quando backlog, contenção ou throughput violarem SLOs.

### Consequências
Menos infraestrutura e consistência transacional simples; polling aumenta carga no banco e não é ideal para throughput muito alto. O handler é desacoplado do transporte para permitir troca.

## ADR-005: webhook Meta termina na API Python

### Status
Proposto

### Contexto
O contrato existente depende de HMAC sobre bytes exatos, deduplicação durável e associação segura conta→tenant.

### Decisão
A API Python pública recebe, valida e persiste; Next.js não faz proxy do webhook. O processamento pesado ocorre no worker.

### Consequências
O serviço Python precisa de domínio TLS público e alta disponibilidade. Em troca, há um único implementation point para segurança, parsing e idempotência.

## Critérios de arquitetura antes do piloto

- ameaça e data-flow revisados; nenhum token no browser/log/banco em claro;
- isolamento cross-tenant comprovado em API, jobs, exports, busca e analytics;
- OAuth/revogação Meta, webhook assinado e deduplicação testados ponta a ponta;
- opt-out e kill switch bloqueiam envio no momento da execução;
- aprovação vinculada ao hash; timeout ambíguo não duplica mensagem;
- backup, PITR e restore ensaiado; migrations com rollback operacional;
- WCAG e fluxos responsivos validados na interface web;
- rate limits, custo de IA e quotas por tenant aplicados server-side;
- runbooks para token expirado, Meta 429/5xx, backlog, `unknown` e incidente de dados;
- termos, privacidade, retenção, exportação e exclusão do titular definidos.

Até esses critérios terem evidência, a arquitetura autoriza desenvolvimento e staging, não lançamento público nem autonomia de envio.
