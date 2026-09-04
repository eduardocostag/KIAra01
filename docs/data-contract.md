# Contrato de dados comerciais B2B/B2C

**Status:** implementável, versão 1.0, auditado em 2026-09-04. Este documento descreve o estado atual e o contrato-alvo; não declara que todos os controles-alvo já existem.

## Camadas e envelope

| Camada | Conteúdo | Regra |
|---|---|---|
| Bronze | payload/linha original, metadados e hash | imutável, append-only; rejeição não vira lead silenciosamente |
| Silver | pessoa/empresa normalizada, evidências e consentimentos | somente dados validados; conflito de identidade vai para revisão |
| Gold | funil, prioridades e métricas | lê Silver, possui `quality_score`, SLA e versão do modelo |

Todo evento deve possuir `event_id`, `idempotency_key`, `entity_kind`, `source_system`, `source_type`, `source_locator`, `source_record_id`, `captured_at`, `ingested_at`, `schema_version`, `raw_hash`, `collector_version`, `processing_status` e `validation_errors[]`. O bruto é preservado separadamente conforme retenção.

- Mesma chave e mesmo hash: replay sem nova entidade, observação ou evento.
- Mesma chave e hash diferente: nova revisão vinculada à anterior.
- Desconhecido permanece `null`, nunca zero, falso ou texto conclusivo por implicação.
- Mudança incompatível é quarentenada e alertada; adição exige versão explícita.
- Timestamps entram com timezone e são persistidos em UTC.

## B2B — empresa e evidência

Identidade-alvo: identificador empresarial verificado; na ausência, domínio normalizado; depois telefone E.164; somente por último `nome_normalizado + local_normalizado`. Comparação de nome usa Unicode NFKC, espaços colapsados e `casefold`, preservando o valor de exibição.

`leads` é a projeção Silver atual. `source_snapshots` e `field_observations` já representam parte da proveniência. Cada afirmação deve apontar para observação com valor bruto/normalizado, snapshot, URL, tipo, instante, confiança e status (`OBSERVED`, `VERIFIED`, `CONFLICTING`, `REJECTED`). Score e qualificação precisam de `score_model_version` e das observações usadas.

**Gap crítico:** o índice atual `(company, whatsapp, location)` compara texto bruto, duplicando variações de caixa/telefone e podendo colidir homônimos. Criar `lead_identity_keys`, executar backfill em dry-run, listar conflitos e exigir merge humano antes de impor unicidade. Não migrar automaticamente.

## B2C — pessoa, consentimento e sinal orgânico

Deduplicação ocorre por `(platform, scoped_id)` ou contato declarado normalizado. E-mail usa `casefold`; telefone mantém dígitos no estado atual e deve evoluir a E.164 apenas com país conhecido. Chaves que apontem a pessoas distintas falham fechadas para revisão humana.

A entrada exige origem compatível, ID externo, captura com timezone, contato/identidade social, consentimento explícito anterior à captura, propósito e canais permitidos; menores e categorias sensíveis são rejeitados. A chave idempotente é SHA-256 de plataforma, origem e ID externo. Sinal orgânico público é oportunidade, não pessoa nem consentimento.

**Gap crítico:** a chave de `ConsumerLeadPayload` não é persistida e campos B2C não têm snapshot. Antes de webhooks, criar `consumer_ingestion_events` com chave única, hash, payload protegido, status e erro; gravar pessoa, contato, identidade e consentimento numa transação, preservando `captured_at` e fonte originais.

## CSV v1

UTF-8 com BOM, vírgula, cabeçalho obrigatório e uma linha por lead. Ordem canônica: `empresa,nicho,local,whatsapp,site,fonte,score,etapa,qualificacao,proxima_acao`. `empresa` é obrigatória; `score` é inteiro limitado pelo store a 0–100; `etapa` pertence a `LeadStage`. Linha inválida não entra e retorna erro numerado. Replay faz upsert pela identidade B2B atual.

Valores iniciados por `=`, `+`, `-`, `@`, tab ou CR recebem apóstrofo na exportação contra fórmulas. Na importação, somente esse marcador reconhecível é removido; apóstrofo literal é preservado. O round-trip está testado.

**CSV v2 necessário para autonomia:** preview em duas fases, `schema_version`, `source_record_id`, dry-run, relatório de conflitos, transação do lote, limites, rollback e arquivo de rejeições. CSV v1 é adequado a lote assistido.

## Qualidade, auditoria e aceite

Cada linha Gold expõe `quality_score` 0–100 e `quality_flags[]`: identidade 30, proveniência 25, atualidade 15, completude 15, consistência 15. Sem evidência, não há pontos de proveniência. Por execução medir recebidos, aceitos, rejeitados, repetidos, conflitos, criados, atualizados, latência e schema. Alertar corrupção silenciosa, rejeição >1%, duplicação >0,5%, atraso >15 minutos, mudança de schema e queda de volume >30% contra mediana móvel.

Entidades-alvo possuem `created_at`, `updated_at`, `deleted_at` e `source_system`; deleção operacional é soft delete. O estado atual não tem `deleted_at`/`source_system` uniformes, portanto a migração é aditiva.

Aceite produtivo: replay idempotente; 100% das mudanças de schema detectadas; zero merge ambíguo automático; afirmações de score rastreáveis; reconciliação `recebidos = aceitos + rejeitados + repetidos`; rollback de lote testado; métricas/alertas emitidos; relatório de backfill revisado.
