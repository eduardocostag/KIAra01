# Auditoria SQLite — Kiara Lead Intelligence

Data: 2026-09-04  
Responsável: `database-optimizer`

## Escopo e conclusão

Foram inspecionados os schemas e acessos SQLite em `app/leads`, `app/consumers`,
`app/knowledge`, `app/memory`, `app/planning`, `app/personal`, `app/automation`,
`app/workflows` e `app/integrations/email`.

O desenho é adequado para uma aplicação desktop local: há queries parametrizadas,
chaves únicas para identidades declaradas, transações nos fluxos compostos, WAL nos
stores mais concorridos e índices nas principais FKs e linhas do tempo. Havia três gaps
seguros de corrigir: ordenações B2B sem índice correspondente, listagem/retenção B2C sem
índice correspondente e FKs declaradas mas não aplicadas no repositório de conhecimento.

## Correções implementadas

1. `LeadStore`: índices `idx_leads_score_updated`, `idx_leads_stage_score_updated` e o
   parcial `idx_leads_due_actions` cobrem as listagens geral/por estágio e ações vencidas.
2. `ConsumerStore`: `idx_consumer_people_updated` cobre a listagem geral e o índice
   parcial `idx_consumer_people_retention` cobre a purga sem indexar prazos vazios.
3. `KnowledgeStore`: habilita `journal_mode=WAL`, `foreign_keys=ON` e
   `busy_timeout=5000`; `chunks.document_id` agora rejeita órfãos.

As mudanças usam `CREATE INDEX IF NOT EXISTS` ou PRAGMAs de conexão, portanto são
aditivas e compatíveis com bancos existentes.

## Evidência reproduzível

```powershell
python -m pytest tests/test_database_indexes.py tests/test_leads.py tests/test_consumers_store.py tests/test_knowledge.py -q
```

Resultado observado: `21 passed in 0.81s`.

`tests/test_database_indexes.py` usa `EXPLAIN QUERY PLAN` para verificar nominalmente os
cinco índices adicionados. Também tenta inserir um chunk órfão e prova que o SQLite
responde com `sqlite3.IntegrityError`.

## Deduplicação e integridade avaliadas

- B2B: `UNIQUE(company, whatsapp, location)` e `ON CONFLICT` preservam um lead quando a
  identidade fornecida é idêntica.
- B2C: contatos são normalizados e únicos por `(kind, normalized_value)`; identidades
  sociais são únicas por `(platform, scoped_id)`; conflitos multi-pessoa exigem revisão.
- Conhecimento: documentos usam SHA-256 dos bytes; chunks são únicos por posição e hash
  dentro do documento; a diversificação remove conteúdo repetido da resposta.
- Automação: `(automation_id, run_key)` impede uma segunda reivindicação da execução.
- Supressões: hashes de destinatário são PKs e os upserts mantêm uma entrada por alvo.

## Riscos remanescentes (sem alteração automática)

- A identidade B2B é sensível a caixa, pontuação e formatação do telefone. Corrigi-la
  exige migração com relatório de colisões; uma mudança automática poderia mesclar
  empresas distintas.
- A deduplicação documental usa bytes exatos. O mesmo texto com codificação/metadados
  diferentes pode ser reingerido; deduplicação semântica requer política de versão.
- `KnowledgeStore.search` e `MemoryEngine.search` avaliam candidatos em Python. É O(n) e
  precisa de benchmark e estratégia vetorial antes de prometer escala alta.
- Alguns stores menores não padronizam WAL/busy timeout. A uniformização deve vir com
  testes de concorrência na auditoria de confiabilidade.
- Datas são TEXT ISO-8601. Comparações dependem de formato uniforme; entradas externas
  devem ser normalizadas antes da persistência.

## Decisão de prontidão

Os acessos locais críticos agora têm índices coerentes e o store de conhecimento aplica
sua FK. Isso reduz risco no piloto assistido, mas não prova escala comercial: ainda são
necessários dados representativos, benchmarks de latência/contenção, `integrity_check`,
backup/restauração e teste de recuperação nos gates de performance e confiabilidade.
