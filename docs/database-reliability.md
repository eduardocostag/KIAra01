# Confiabilidade dos dados — Kiara Lead Intelligence

Auditoria executada em 2026-09-04 sobre os stores SQLite e JSON locais, com foco em integridade, migração, WAL, recuperação após falha e restauração.

## Resultado objetivo

- Os 11 bancos existentes em `data/` responderam `PRAGMA quick_check=ok` e `PRAGMA foreign_key_check` sem violações.
- Sete bancos estão em WAL. Comunicações, conhecimento e workflows ainda usam journal `DELETE`.
- A memória tinha uma janela real de inconsistência: `revise` e `consolidate` persistiam a nova linha antes de marcar as anteriores como superadas. Uma falha intermediária deixava dados semanticamente incompletos. A operação agora é atômica e faz rollback integral.
- Os principais stores JSON usam troca por arquivo temporário, protegendo contra JSON parcialmente gravado. Isso não substitui backup.

## Evidência de teste

`python -m pytest tests/test_memory.py tests/test_advanced_memory_planning.py tests/test_leads.py tests/test_consumers_store.py -q`

Resultado: `27 passed in 1.30s`. O novo teste injeta uma falha no segundo passo de uma revisão e comprova rollback da versão recém-inserida.

## Risco residual e gate comercial

Não foi encontrado processo de backup versionado, retenção, cópia fora do dispositivo ou teste automatizado de restauração. Logo, existe persistência local, mas **não existe recuperabilidade comprovada**. Um backup nunca restaurado não conta como plano de recuperação.

Antes de GA, o negócio deve aprovar RPO/RTO. Para piloto assistido, ponto de partida: RPO de 24 horas e RTO de 4 horas, com captura consistente pela API de backup SQLite, manifesto SHA-256, cópia fora do dispositivo e restore mensal em diretório descartável. Cada restore deve executar `quick_check`, `foreign_key_check`, smoke tests e registrar o RTO medido.

## Migrações e compatibilidade

- Leads usam `user_version=5`, consumidores `1` e memória `2`; vários stores seguem em `0`, sem histórico explícito. Isso impede provar upgrade/downgrade seguro e deve ser resolvido antes de atualizações automáticas.
- A migração legada da memória é transacional, mas ainda falta teste de interrupção de processo e reabertura sobre cópia realista.
- Não há replicação/failover: o produto é desktop single-node. HA distribuída não deve ser prometida.

## Decisão

Integridade atual: aprovada para desenvolvimento e piloto assistido. Recuperação/DR: **não aprovada para GA** até existir restore completo, cronometrado e documentado. Nenhum backup dos dados reais foi criado ou removido nesta auditoria.
