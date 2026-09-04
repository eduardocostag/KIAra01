# Contratos de workflow — Kiara Lead Intelligence

**Versão:** 0.1  
**Data:** 2026-09-04  
**Autor:** `workflow-architect`  
**Status:** Review — especificação confrontada com o código; lacunas abertas não estão aprovadas

## Escopo e regra de leitura

Este documento define o comportamento exigido para pesquisa B2B/B2C, qualificação, pipeline, outreach e CSV. `Implementado` significa que o caminho foi localizado no código; não equivale a teste executado nesta rodada. `Parcial` e `Ausente` são contratos ainda não satisfeitos. Toda ação externa permanece em dry-run até preview, aprovação, política, auditoria e idempotência formarem um único fluxo verificável.

## Registro — visão por workflow

| Workflow | Entrada | Ator primário | Persistência | Estado real | Red flag |
|---|---|---|---|---|---|
| Pesquisa B2B local | intenção de pesquisa no chat | `AgentCore` | `leads.db` após extração/verificação | Parcial | sem job persistente, progresso, cancelamento cooperativo ou retomada |
| Descoberta B2C orgânica | intenção de descoberta | `AgentCore` | `consumers.db`, somente sinal público | Parcial | sem ciclo persistente do job; sinal corretamente não cria pessoa/consentimento |
| Ingestão B2C consentida | payload de adaptador oficial/formulário | adaptador + `ConsumerStore` | `consumers.db` | Implementado | envelope não é transação única entre pessoa, identidade e consentimentos |
| Qualificação B2B | lead + evidências + perfil | `CommercialIntelligenceService` | JSON estruturado em `leads` quando salvo | Implementado/parcial | geração e persistência são chamadas separadas; risco de artefato não salvo |
| Qualificação B2C | pessoa + evidências + consentimento | `ConsumerIntelligenceService` | resultado é calculado; pessoa/consentimento ficam em SQLite | Parcial | qualificação/handoff não possuem snapshot persistente/versionado |
| Movimento de pipeline B2B | drop ou editor | UI + `LeadStore` | `leads.stage` + `lead_events` | Parcial | sem undo; drop reduz múltiplas etapas a seis colunas visuais |
| Movimento de pipeline B2C | ação de estágio | UI + `ConsumerStore` | `consumer_people.stage` | Parcial | sem histórico, responsável, controle de conflito ou undo |
| Preparação de outreach | botão/chat | operador + IA | conversa e/ou `sales_artifacts` | Parcial | botão gera texto; não constitui aprovação persistida para envio |
| Envio externo | ferramenta sensível | operador + provider | auditoria geral e provider | Parcial/crítico | UUID é validado, mas não há ledger local que impeça reenvio da mesma chave |
| Importação CSV B2B | seletor de arquivo | operador + `LeadCsvService` | `leads.db` linha a linha | Parcial | sem preview/mapeamento explícito; importação parcial não tem undo em lote |
| Exportação CSV B2B | visão filtrada | operador + `LeadCsvService` | arquivo UTF-8-SIG | Implementado/parcial | escrita direta no destino; contrato requer arquivo temporário + troca atômica |
| Conversas salvas | UI Copiloto | operador + `ConversationStore` | JSON por troca atômica | Parcial | só criar/adicionar/excluir; sem renomear, favoritar, busca, lote ou undo |

## Registro — visão por componente

| Componente | Workflows |
|---|---|
| `app/core/agent_core.py` | pesquisa B2B, descoberta B2C, preparação conversacional |
| `app/leads/store.py` | identidade B2B, qualificação persistida, pipeline, interações, métricas |
| `app/leads/intelligence.py` | fatos/inferências/desconhecidos, score, dossiê, drafts e gates |
| `app/leads/policy.py`, `suppression.py` | reserva transacional, limite, cooldown, opt-out |
| `app/consumers/ingestion.py`, `store.py`, `intelligence.py` | ingestão consentida, deduplicação, retenção, qualificação B2C |
| `app/leads/csv_io.py` | importação/exportação B2B |
| `app/ui/sdr_cockpit.py`, `desktop.py` | drop, filtros, seleção, CSV, kit de abordagem |
| `app/tools/communications.py`, `integrations/communications.py` | preview e execução externa |
| `app/security/permissions.py`, `audit.py`, `kill_switch.py` | confirmação, auditoria e interrupção global |
| `app/ui/conversations.py` | conversas locais |

## Registro — visão por jornada

| Jornada | Encadeamento obrigatório |
|---|---|
| Operador encontra empresa | criar job → pesquisar fontes → verificar evidência → deduplicar → qualificar → persistir lead/dossiê → apresentar resultado |
| Consumidor entra por canal autorizado | validar envelope/idade/origem → validar consentimento → deduplicar identidade → persistir pessoa/consentimento → qualificar → bloquear ou entregar handoff |
| Operador avança oportunidade | ler versão/estado → validar transição → persistir evento e estágio atomicamente → atualizar UI → oferecer undo |
| Operador prepara contato | gerar draft fundamentado → preview imutável → reservar política → aprovar → revalidar consentimento/supressão → enviar uma vez → auditar resultado |
| Operador importa planilha | selecionar → detectar encoding/cabeçalho → mapear/preview → validar todas as linhas → confirmar → gravar lote idempotente → emitir relatório/undo |

## Registro — visão por estado

| Entidade | Estados exigidos | Transições e observabilidade |
|---|---|---|
| Job de pesquisa | `queued → running → cancelling → cancelled`; `running → completed/failed` | UI mostra contagem/fontes reais; operador vê etapa/erro; banco guarda checkpoint; logs usam `job_id` |
| Lead B2B | enum de `novo` a `convertido/perdido` | toda mudança registra origem, ator, anterior/novo e versão; terminais exigem ação explícita |
| Pessoa B2C | `novo_opt_in` a `cliente/nutricao/perdido` | contato só sai se consentimento atual e não suprimido; mudanças precisam histórico |
| Outreach | `draft → previewed → reserved → approved → sending → sent`; saídas `cancelled/failed/unknown` | `unknown` após timeout nunca pode ser reenviado sem consulta/reconciliação |
| Importação | `selected → previewed → confirmed → committing → completed/partial/failed → undone` | UI e relatório preservam contagens e erros por linha |

## WF-01 — Pesquisa B2B em segundo plano

**Pré-requisitos:** perfil/região válidos, ferramenta de busca disponível, política de fonte permitida.  
**Happy path:** criar `research_job` com chave derivada da solicitação normalizada; executar consultas sem janela visível; registrar fonte consultada e contagem real; extrair somente candidatos literais; verificar individualmente; `upsert` pela identidade B2B; gerar qualificação/dossiê; concluir com IDs persistidos.

**Falhas e recuperação:** entrada ambígua → solicitar localização, sem criar lead; fonte indisponível/429 → backoff limitado e manter checkpoint; timeout de fonte (10 s sugeridos) → marcar fonte falha e seguir se houver evidência suficiente; JSON do modelo inválido → uma correção estruturada e depois `failed`; falha SQLite → rollback da unidade corrente; cancelamento → parar antes da próxima chamada/persistência e marcar `cancelled`; concorrência → uma chave ativa por solicitação/escopo; retomada só a partir de checkpoint.

**Observável:** cliente vê etapa, `processados/total`, fonte atual e Cancelar; operador vê `job_id`, tempos e falha; banco guarda solicitação, status, checkpoint e IDs produzidos; logs não contêm telefone bruto desnecessário.

**Realidade:** o código pesquisa de modo assíncrono na thread de solicitação e persiste leads, mas não foi localizado um registro de job, progresso real, cancelamento cooperativo ou retomada. Status: **Missing/P0 para o contrato de background**.

## WF-02 — Descoberta e ingestão B2C

**Ramo orgânico:** sinal público permitido → persistir apenas oportunidade pela `source_url`; nunca criar pessoa nem consentimento. Duplicata atualiza o sinal. Revisão humana decide CTA público ou descarte.

**Ramo consentido:** validar tamanho/campos/origem/idade/timestamps/canais → calcular chave `platform+origin+external_id` → deduplicar por identidade e contatos → persistir pessoa, identidade e um registro de consentimento por canal → qualificar. Sem consentimento, menor de idade, origem incompatível ou identidade conflitante → rejeição permanente sem contato. Opt-out/expiração → bloqueio imediato e supressão preservada mesmo após purge.

**Concorrência/idempotência:** o mesmo evento deve retornar o mesmo `person_id` e não duplicar consentimento/touchpoint; eventos diferentes que apontem para duas pessoas geram `identity_conflict` e fila de revisão. Atualmente a chave é calculada, mas não há ledger de eventos consumidos nem transação única de ingestão: **Parcial/P0**.

## WF-03 — Qualificação e dossiê

**B2B:** carregar lead, observações e perfil → aceitar como fato apenas evidência com fonte/status/confiança → separar hipóteses e desconhecidos → calcular dimensões/versionar modelo → aplicar desqualificadores → gerar próxima ação, meeting brief e drafts → validar fundamentação → persistir tudo numa transação. Falha de validação não substitui snapshot anterior. Duas qualificações concorrentes usam `expected_updated_at` ou versão; perdedora recalcula.

**B2C:** revalidar consentimento no instante da decisão → calcular dimensões conservadoras → exigir intenção forte, evidência e confiança para SQL → gerar handoff → persistir snapshot/versionamento. Sinal social fraco isolado permanece nurture; sem consentimento fica blocked; opt-out fica disqualified.

**Realidade:** regras explicáveis existem. B2B tem campos persistentes, porém cálculo/gravação são separados; B2C não persiste snapshot de qualificação. Não há controle otimista de concorrência. Status: **Parcial/P0**.

## WF-04 — Pipeline, histórico e undo

**Happy path:** receber `{entity_type,id,from_stage,to_stage,expected_version,actor,reason}` → validar existência e transição → atualizar estado e inserir evento na mesma transação → retornar `{event_id,new_version}` → UI só confirma após sucesso.

**Undo:** disponível por janela configurável enquanto nenhum evento posterior existe. Comando `{event_id,expected_version}` cria evento compensatório; nunca apaga histórico. Se outro ator alterou o lead, retornar `409 stale_version`. Falha de gravação mantém o card na coluna original. Cancelar drag antes do drop não gera evento.

**Realidade:** B2B grava mudança e `lead_events`, mas não expõe leitura/undo/ator/versão; B2C só atualiza a linha. O drop atual mapeia etapas detalhadas para seis macrocolunas. Status: **Missing/P0 para undo e conflito; Missing/P1 para histórico B2C**.

## WF-05 — Outreach com aprovação e idempotência

1. Gerar draft somente de fatos e hipóteses marcadas; salvar `draft_id` e hash do conteúdo.
2. Preview mostra destinatário, canal, conteúdo, origem do contato, consentimento e efeitos.
3. Reservar política transacionalmente; bloqueios de supressão, cooldown, limite ou autonomia encerram o fluxo.
4. Aprovação humana referencia exatamente `{draft_id,content_hash,recipient,channel}` e expira; qualquer edição invalida aprovação.
5. Imediatamente antes do envio, revalidar kill switch, consentimento/supressão e reserva.
6. Enviar com chave estável por ação; persistir tentativa antes da chamada.
7. Sucesso registra provider ID, interação e transição atomicamente. Timeout fica `unknown` e exige reconciliação, não retry cego. Cancelamento antes de `sending` libera reserva; depois disso tenta interromper e reconcilia.

**Handoff:** `UI → PermissionGate → ProspectingPolicyEngine → SendMessageTool → Provider`. Payload mínimo: `{action_id,draft_id,content_hash,lead_id,recipient,channel,idempotency_key,approval_id}`. Falha: `{code,retryable,state}`. Timeout sugerido: 15 s, tratado como resultado desconhecido.

**Realidade:** preview, permissão sensível, UUID, reserva/cancelamento e kill switch existem isoladamente. O botão do cockpit apenas pede geração textual. Não há approval/attempt ledger durável nem prova de encadeamento único. Status: **Missing/P0; envio real deve permanecer desabilitado**.

## WF-06 — CSV import/export

**Importação:** abrir arquivo somente após seleção; detectar UTF-8-SIG/UTF-8 e rejeitar encoding inválido → normalizar cabeçalhos → exigir empresa → apresentar mapeamento, preview e relatório → confirmar → criar `import_batch` e hash do arquivo → gravar cada linha com savepoint, deduplicando pela identidade → concluir `completed/partial` → permitir undo compensatório somente nos registros criados pelo lote; registros preexistentes atualizados exigem snapshots anteriores.

**Falhas:** coluna/etapa/score inválido gera erro por linha; arquivo excessivo é rejeitado antes de carregar; cancelamento antes da confirmação não grava; falha global reverte lote; concorrência usa restrição única e reconcilia contagens. Reimportar o mesmo hash não duplica e pede confirmação para reaplicar atualizações.

**Exportação:** congelar filtro/IDs visíveis → serializar UTF-8-SIG → escrever temporário → substituir destino atomicamente → retornar contagem/hash. Cancelamento ou erro preserva arquivo anterior.

**Realidade:** aliases, validação básica, deduplicação por `upsert`, erros por linha e UTF-8-SIG existem. Não existem preview/mapeamento, lote, hash, limite, undo ou exportação atômica. Status: **Parcial/P0**.

## Contratos comuns de erro

| Código | Retry | Recuperação |
|---|---:|---|
| `validation_error` | não | corrigir entrada; zero efeito |
| `identity_conflict` | não | revisão humana; não fundir automaticamente |
| `stale_version` | não | recarregar estado e reaplicar intenção |
| `rate_limited` | sim | backoff com jitter e limite |
| `dependency_timeout` | condicional | pesquisa retoma checkpoint; envio vira `unknown` |
| `cancelled` | não | preservar resultados já confirmados e registrar checkpoint |
| `persistence_error` | sim após diagnóstico | rollback; UI mantém estado anterior |
| `approval_required/expired` | não | gerar novo preview/aprovação |
| `suppressed_or_no_consent` | não | bloquear contato; nunca contornar |

## Inventário de compensação

| Recurso | Compensação |
|---|---|
| job de pesquisa | cancelar chamadas futuras; manter log/checkpoint |
| lead criado por lote | excluir somente se não recebeu evento posterior; caso contrário sinalizar revisão |
| atualização por CSV | restaurar snapshot pré-lote por evento compensatório |
| reserva de outreach | `complete(reservation_id, sent=False)` antes do envio |
| estágio do pipeline | evento inverso condicionado à versão |
| arquivo exportado | troca atômica; temporário incompleto é removível |
| mensagem enviada | não há undo técnico; registrar, permitir follow-up corretivo e respeitar opt-out |

## Casos de teste derivados

| ID | Cenário | Resultado esperado |
|---|---|---|
| WF-T01 | duas pesquisas B2B idênticas concorrentes | um job ativo; sem leads duplicados |
| WF-T02 | cancelar pesquisa durante fonte 2 | estado `cancelled`, sem novas chamadas, checkpoint persistido |
| WF-T03 | sinal social B2C sem opt-in | oportunidade pública apenas; zero pessoa/mensagem |
| WF-T04 | evento B2C repetido | mesmo `person_id`, sem consentimento/touchpoint duplicado |
| WF-T05 | qualificação concorrente | gravação obsoleta recebe conflito |
| WF-T06 | mover card e reiniciar | nova etapa e evento persistem |
| WF-T07 | undo após outra mudança | `409`, nenhum estado sobrescrito |
| WF-T08 | editar mensagem após aprovação | aprovação invalidada; envio bloqueado |
| WF-T09 | timeout do provider após aceitar mensagem | estado `unknown`; nenhum retry automático |
| WF-T10 | CSV misto | válidos conforme confirmação; inválidos no relatório; contagens reconciliadas |
| WF-T11 | cancelar preview CSV | zero mutação |
| WF-T12 | falha ao substituir exportação | arquivo anterior intacto |

## Assunções e perguntas abertas

| # | Assunção não verificável no código | Risco |
|---|---|---|
| A1 | operação comercial permanece local/single-user | versão otimista ainda é necessária para threads/jobs concorrentes |
| A2 | providers honram idempotency key | sem ledger/reconciliação, duplicação externa continua possível |
| A3 | fonte pesquisada permite automação | violação de termos se não houver allowlist/política por fonte |

- Qual SLA e janela de undo devem valer por workflow?
- Qual registro é a fonte de verdade da aprovação: auditoria geral ou ledger comercial dedicado?
- Quais transições B2B/B2C são proibidas ou exigem motivo?
- A importação deve ser estritamente atômica ou aceitar sucesso parcial confirmado?

## Auditoria spec × realidade

| Finding | Severidade | Resolução necessária |
|---|---|---|
| RC-WF-01: pesquisa não possui lifecycle persistente/cancelável | Alta | implementar job, checkpoint e cancelamento cooperativo |
| RC-WF-02: Kanban não possui undo/conflito e B2C não possui histórico | Alta | evento versionado e compensação |
| RC-WF-03: aprovação/idempotência não formam fluxo ponta a ponta | Crítica | ledger durável e revalidação imediatamente antes do provider |
| RC-WF-04: CSV muta antes de preview e não tem lote/undo | Alta | workflow em duas fases com batch |
| RC-WF-05: qualificação B2C calculada não é snapshot persistido | Média | persistir versão, evidências e decisão |
| RC-WF-06: conversas não atendem gestão solicitada | Média | renomear/favoritar/buscar/lote/undo com schema versionado |

Nenhum workflow deste documento deve ser marcado `Approved` até um Reality Checker confrontar a implementação posterior e os casos acima possuírem evidência executada.
