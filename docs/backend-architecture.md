# Arquitetura backend incremental — Kiara Lead Intelligence

## Decisão executiva

A Kiara deve evoluir como **monólito modular local-first**, com contratos de aplicação explícitos e SQLite como armazenamento primário da edição desktop. O desenho atual não justifica microserviços: é uma aplicação Windows de usuário único, com módulos Python já separados e necessidade forte de operação offline. A evolução recomendada preserva os stores e provedores existentes, mas introduz uma camada de aplicação, uma fila persistente de jobs, eventos transacionais e projeções analíticas.

O caminho para serviço remoto fica aberto por portas (protocolos) e contratos versionados, sem impor hoje a complexidade operacional de filas externas, containers ou consistência distribuída.

## Inventário auditado

| Área | Implementação atual | Pontos fortes | Lacuna comercial |
|---|---|---|---|
| Leads B2B | `LeadStore` em `data/leads.db`; leads, interações, eventos de estágio, snapshots e observações | WAL, chaves estrangeiras, lock local, histórico de estágio e transação combinada em `record_interaction_and_transition` | mutações não carregam ator/correlação; histórico não cobre todos os campos; não há undo; migrations são introspectivas e embutidas |
| Consumidores B2C | `ConsumerStore` em `data/consumers.db`; identidade, consentimento, touchpoints, suppressions e retenção | modelo de consentimento e supressão já separado; purge explícito | mudança de estágio sem histórico; analytics B2C não são uma projeção comum; faltam exportação do titular e tombstone auditável |
| Automação | `AutomationStore` e `AutomationEngine` em `data/automations.db` | claim único por `(automation_id, run_key)`, retries limitados, execução interrompida marcada como falha, histórico consultável | scheduler vive no processo; não há lease/heartbeat/cancelamento persistente, backoff exponencial, DLQ ou reconciliação de efeitos de resultado desconhecido |
| Workflows | `WorkflowStore` em `data/workflows.db` e builder conversacional | rascunho desativado e revisão antes de ativar | especificação fica como JSON opaco; não há versionamento, execução, aprovação por etapa ou vínculo robusto com jobs |
| Planejamento | `PlanStore` em `data/planning.db` | goal e checkpoints persistentes | é um mecanismo paralelo a automações; não há contrato único de execução longa |
| E-mail e comunicações | Drafts persistentes; Graph/Gmail por protocolos; `OutboundMessage` com idempotency key | preview/draft e credenciais desacopladas; timeout HTTP | o idempotency key não possui ledger local de efeito externo; status do draft é insuficiente para `prepared/approved/sending/sent/unknown/failed`; leitura e escrita não têm retry/circuit breaker uniforme |
| LLMs | `LLMProvider`, fallback, `ModelRouter`, `GuardedRemoteProvider` | perfis fast/reasoning/vision, limite diário, redaction e circuit breaker remoto | roteamento considera principalmente texto; orçamento é JSON local; métricas não persistem; falta envelope de resultado com provider/modelo/custo/latência/schema/trace |
| Integrações | `JsonHttpClient`, MCP hub, Obsidian e Microsoft Graph | portas claras e idempotency header disponível | política de timeout/retry/status/health não é uniforme; erros perdem código, corpo seguro e retryability |
| Eventos | `EventBus` assíncrono em memória | desacoplamento simples dentro do processo | eventos são perdidos em crash/restart e handlers concorrentes não têm retry, ordenação por agregado ou checkpoint |
| Observabilidade | `MetricsRegistry` em memória | p50/p95 e contadores baratos | reinício perde tudo; sem correlation ID, métricas de negócio por período ou SLOs |

## Arquitetura-alvo

```text
PySide / CLI / voz
        |
Application Services (commands + queries + policies)
        |
        +-- Unit of Work --------> stores SQLite existentes
        |                              |
        |                              +-- domain_events / outbox
        |
        +-- Job Service ----------> job_queue / job_attempts / job_effects
        |
        +-- Integration Gateway --> Graph / Gmail / MCP / busca / LLM
        |
        +-- Analytics Projector --> analytics_events / daily_funnel
```

Os módulos de domínio continuam sendo `leads`, `consumers`, `automation`, `workflows`, `planning`, `knowledge` e `memory`. A UI deixa de coordenar gravações e efeitos externos diretamente e chama casos de uso pequenos, por exemplo:

- `MoveOpportunity(command) -> MoveOpportunityResult`
- `UndoOperation(command) -> UndoResult`
- `ImportLeads(command) -> ImportReport`
- `PrepareOutbound(command) -> PreparedAction`
- `ApproveOutbound(command) -> JobId`
- `StartResearch(command) -> JobId`
- `CancelJob(command) -> JobState`
- `GetDashboard(query) -> DashboardSnapshot`

Todo command mutável deve carregar `command_id`, `actor_id`, `correlation_id`, `causation_id`, `occurred_at` e `expected_version` quando houver edição concorrente. Repetir um `command_id` retorna o resultado anterior sem repetir o efeito.

## Undo e trilha de alterações

Undo deve ser **compensatório e limitado**, não um rollback genérico do banco. Para cada operação reversível, a mesma transação grava o estado do domínio e um registro em `operations`:

```sql
CREATE TABLE operations (
  id TEXT PRIMARY KEY,
  command_id TEXT NOT NULL UNIQUE,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  operation_type TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  before_json TEXT NOT NULL,
  after_json TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  undoable_until TEXT,
  undone_by TEXT,
  version INTEGER NOT NULL
);
CREATE INDEX idx_operations_aggregate
  ON operations(aggregate_type, aggregate_id, created_at DESC);
```

Primeiros casos suportados: mover estágio no Kanban, renomear/favoritar conversa ou pesquisa, exclusão lógica e edição de próxima ação. O undo executa um novo command, valida que a versão atual ainda corresponde ao `after_json`, restaura somente campos declarados pelo tipo da operação e registra `undone_by`. Se houve alteração posterior conflitante, retorna conflito em vez de apagar trabalho novo.

Envio de mensagem, publicação, chamada externa consumada e purge de retenção não são “desfeitos”. Eles usam compensações específicas quando disponíveis (cancelar evento, arquivar draft) e mostram claramente quando o efeito é irreversível. Exclusões recuperáveis usam `deleted_at` e janela de retenção; purge físico ocorre em job separado e auditado.

## Jobs persistentes e pesquisa em segundo plano

Criar um `JobStore` compartilhado em um novo `data/jobs.db` é a menor mudança segura. Não reutilizar `automation_runs`: automação define **quando** disparar; job representa **uma execução concreta**, cancelável e observável.

Estados: `queued -> leased -> running -> succeeded | failed | cancelled | needs_review`. O estado `needs_review` é obrigatório para crash após início de efeito externo, quando não for possível provar se o provedor concluiu a ação.

Campos mínimos de `jobs`: `id`, `kind`, `payload_json`, `state`, `priority`, `progress_current`, `progress_total`, `progress_message`, `cancel_requested_at`, `available_at`, `lease_owner`, `lease_expires_at`, `attempt_count`, `max_attempts`, `idempotency_key`, `correlation_id`, `created_at`, `started_at`, `finished_at`, `last_error_code`, `last_error_safe` e `result_json`. Índices: `(state, available_at, priority)`, `correlation_id` e unicidade de `idempotency_key` por `kind`.

Regras operacionais:

1. Claim atômico por `BEGIN IMMEDIATE`, com lease e heartbeat; lease expirado volta a `queued` apenas para jobs comprovadamente idempotentes.
2. Retry com backoff exponencial e jitter apenas para erros classificados como transitórios; `401/403`, schema inválido e política/LGPD falham sem retry automático.
3. Após `max_attempts`, job vai para `failed`; itens venenosos podem ser clonados manualmente com nova chave e vínculo `retry_of`.
4. Cancelamento é cooperativo entre páginas/lotes. O worker verifica `cancel_requested_at` antes de cada efeito e persiste progresso real, nunca um temporizador simulado.
5. Pesquisa grava fontes e resultados incrementalmente; a UI lê o job por polling local ou sinal Qt, sem abrir navegador visível.
6. Shutdown para de aceitar jobs, solicita checkpoint e libera somente leases sem efeito externo em andamento.

`AutomationEngine` passa gradualmente a enfileirar jobs em vez de executar ferramentas diretamente. Isso preserva triggers e idempotência atuais enquanto centraliza retries, cancelamento e histórico.

## Eventos transacionais e analytics reais

O `EventBus` deve continuar como notificação de baixa latência, mas a fonte confiável passa a ser uma **outbox SQLite** gravada na mesma transação da alteração de domínio:

```sql
CREATE TABLE outbox_events (
  id TEXT PRIMARY KEY,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  aggregate_version INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  published_at TEXT,
  UNIQUE(aggregate_type, aggregate_id, aggregate_version, event_type)
);
```

Eventos iniciais: `lead.created.v1`, `lead.stage_changed.v1`, `interaction.recorded.v1`, `consumer.created.v1`, `consumer.stage_changed.v1`, `consent.changed.v1`, `research.completed.v1`, `outbound.prepared.v1`, `outbound.sent.v1`, `meeting.created.v1`, `proposal.prepared.v1` e `deal.won.v1`.

Uma projeção `analytics.db` consome a outbox de cada banco usando checkpoint por origem. Ela mantém eventos imutáveis e agregados diários. Assim, cards, gráficos, tabelas e exportações usam o mesmo `DashboardQuery` e os mesmos filtros: período, B2B/B2C, origem, região, responsável e estágio.

Métricas devem ter definições estáveis:

- conversão A→B: entidades que entraram em B no período / entidades elegíveis que entraram em A;
- tempo de estágio: diferença entre eventos consecutivos de estágio, com mediana e p95;
- taxa de resposta: respostas recebidas / contatos enviados, excluindo dry-run;
- receita potencial: soma do valor estimado de oportunidades abertas, nunca ticket médio aplicado silenciosamente;
- qualidade: distribuição de `confidence_score`, completude e idade da evidência;
- vencidas: próxima ação anterior a agora, não concluída e fora de estágio terminal.

O dashboard retorna também `as_of`, `filters`, `data_freshness_seconds` e `is_demo`. Dados de demonstração precisam de `dataset_kind='demo'` e nunca se misturam por padrão aos reais.

## Contrato de integrações e provedores

Introduzir um envelope comum sem substituir imediatamente os adapters atuais:

```python
IntegrationResult[T](
    value: T | None,
    provider: str,
    operation: str,
    external_id: str | None,
    latency_ms: float,
    attempts: int,
    idempotency_key: str | None,
    error_code: str | None,
    retryable: bool,
)
```

Toda escrita externa segue `prepare -> approve -> enqueue -> execute -> reconcile`. A aprovação é um registro persistente com hash exato do payload, ator, escopo e expiração; qualquer edição após aprovação invalida a aprovação. `job_effects` registra `prepared`, `attempted`, `acknowledged` ou `unknown`, com external ID quando disponível.

Política HTTP comum: timeout de conexão e total explícitos, no máximo três tentativas para operação segura/idempotente, backoff com jitter, `Retry-After`, circuit breaker por integração e sanitização de erro. Nunca fazer retry automático de POST sem chave aceita pelo provedor ou reconciliação por external ID.

Saúde de integração deve ser persistida em `integration_status`: provider, capacidade, estado (`not_configured/healthy/degraded/down/auth_required/rate_limited`), último sucesso, última falha segura, latência, limite conhecido e próxima verificação. O botão “Testar” executa uma operação read-only; nunca envia mensagem de teste real.

Para LLM, ampliar o roteamento por um `ModelRequest` com capacidade, criticidade, limite de contexto, schema de saída, privacidade permitida, teto de custo e prazo. O resultado guarda provider/modelo, tokens estimados ou reportados, custo estimado, latência, fallback usado, versão do prompt e validação de schema. Fallback só ocorre quando a política de privacidade permite e não deve transformar erro de schema em resposta livre.

## Consistência, migrações e backup

- Manter um banco por bounded context reduz o raio de corrupção; operações que exigem atomicidade ficam dentro do mesmo banco. Consistência entre bancos é eventual via outbox e jobs.
- Substituir `CREATE/ALTER` dispersos por migrations numeradas, idempotentes e testadas, preservando `PRAGMA user_version`. Fluxo expand-and-contract: adicionar, backfill em lotes, ler novo com fallback, validar, só depois remover legado.
- Em toda conexão: `foreign_keys=ON`, `journal_mode=WAL`, `busy_timeout`, transações curtas e fechamento explícito. Hoje essas opções não são uniformes entre stores.
- Backup usa SQLite Online Backup API por arquivo, manifesto com versão/schema/SHA-256 e cópia conjunta de JSONs essenciais. Não copiar apenas o `.db` enquanto há WAL ativo.
- Restore roda em diretório temporário, valida `integrity_check`, versões e hashes, fecha stores/workers, troca arquivos de forma atômica e mantém o conjunto anterior para rollback.
- Definir retenção separada para conteúdo, eventos analíticos, logs técnicos e auditoria. Exclusão de titular enfileira um job idempotente, produz relatório de abrangência e preserva apenas prova mínima legal/pseudonimizada quando aplicável.

## Segurança e observabilidade

Logs estruturados devem conter `timestamp`, `level`, `event`, `error_code`, `correlation_id`, `job_id`, `integration`, `duration_ms` e contexto de tenant/usuário quando existir; nunca prompt completo, token, mensagem ou PII por padrão. O `AuditLog` continua sendo a trilha de ações sensíveis, separado de logs operacionais.

SLIs locais iniciais:

- p95 de queries interativas abaixo de 200 ms;
- 99,9% dos commands persistidos sem erro em sessões saudáveis;
- idade do job mais antigo na fila;
- taxa de jobs concluídos/falhos/cancelados/`needs_review`;
- latência, erro e circuito por integração/provider;
- atraso da projeção analítica;
- quantidade de efeitos externos em estado `unknown` (alerta imediato na UI).

Métricas técnicas podem ser armazenadas em agregados horários com retenção limitada; não persistir amostras ilimitadas como o registro em memória atual.

## Plano incremental e critérios de aceite

### Fase 1 — fronteiras e segurança de mutação

Criar contracts de command/query, correlation IDs, `operations` e casos de uso de mover/undo. Adaptar primeiro o Kanban; manter métodos existentes como compatibilidade interna.

Aceite: movimento persiste após reinício; histórico mostra ator; undo restaura a etapa; edição concorrente gera conflito; nenhum evento externo é disparado.

### Fase 2 — jobs persistentes

Criar `JobStore`, worker único local e API de progresso/cancelamento. Migrar pesquisa B2B/B2C e depois automações para enqueue.

Aceite: reinício retoma job idempotente; cancelamento para entre lotes; progresso corresponde a itens persistidos; duplicação do command não duplica resultados; crash durante efeito ambíguo produz `needs_review`.

### Fase 3 — outbox e analytics

Adicionar outbox primeiro a leads e consumers, backfill de eventos mínimos e projetor analítico. Trocar dashboard e exportação para uma query comum.

Aceite: totais reconciliam com os stores; todos os filtros alteram cards/gráficos/tabela/exportação igualmente; reprocessar a projeção é idempotente; demo e real ficam separados.

### Fase 4 — integrações e modelos

Aplicar envelope, health status, approvals persistentes, ledger de efeitos e política uniforme de retry/circuit breaker. Ampliar `ModelRouter` com requisitos e schema.

Aceite: payload aprovado é imutável; POST não idempotente não é repetido; falhas não vazam segredo/PII; UI mostra provider utilizado e saúde sem credencial; schema inválido falha de modo explícito.

### Fase 5 — migração e recuperação

Centralizar migrations, backup/restore, retenção e exportação/exclusão do titular.

Aceite: restore validado em cópia limpa; rollback preserva conjunto anterior; migrations funcionam de banco vazio e de fixtures legadas; `integrity_check` passa antes e depois.

## Riscos que não devem ser ocultados

- SQLite atende bem ao desktop single-user, mas compartilhamento de banco por rede, múltiplos processos escritores ou colaboração multiusuário exigirão uma API dona dos dados, provavelmente com PostgreSQL.
- Headers de idempotência não garantem suporte real do provedor; cada adapter precisa declarar e testar sua semântica.
- O estado atual do `EventBus` não garante entrega; automações de negócio importantes não devem depender somente dele.
- Marcar execução interrompida como `failed` evita repetição, mas não prova ausência do efeito externo. O estado `needs_review` e reconciliação são necessários antes de uso comercial autônomo.
- JSON opaco facilita evolução inicial, porém campos usados em filtro, ordenação, integridade e analytics devem ser promovidos a colunas tipadas e indexadas.
- Uma central de integrações pode informar configuração e saúde, mas credenciais e aprovações oficiais de Meta, Google, Microsoft ou WhatsApp continuam bloqueios externos legítimos.

## Fora de escopo desta especificação

Esta auditoria não declara implementação, testes ou prontidão comercial. Nenhum código foi alterado. O documento define a sequência de menor risco para completar undo, jobs, analytics e integrações aproveitando a base existente.
