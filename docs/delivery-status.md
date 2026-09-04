# Status de entrega — Kiara Lead Intelligence

**Data-base:** 2026-09-04  
**Responsável pela consolidação:** `project-shepherd`  
**Escopo:** demonstração comercial controlada, piloto assistido e preparação para distribuição Windows

## Resumo executivo

**Status geral: Amarelo — execução coordenável, prontidão comercial ainda não aprovada.** O MVP e a sequência de gates estão definidos, mas o baseline técnico atual ainda não foi fechado. Há mudanças não confirmadas em módulos de leads, UI, testes e bancos locais; as evidências de testes disponíveis são anteriores às mudanças correntes. Portanto, não há base para declarar as Fases 0–7 concluídas nem para reutilizar os gates históricos como aprovação da versão atual.

**Próximo marco:** fechar a Fase 0 e obter um baseline reproduzível dos testes focais do primeiro incremento, preservando os dados do usuário. Só então iniciar correções no núcleo de dados.

**Posicionamento autorizado neste estágio:** copiloto comercial local, single-user, com demonstração em dry-run e ações externas sob controle humano. Piloto, distribuição e automação autônoma permanecem não aprovados.

## Linha de entrega e dependências

| Marco | Estado em 2026-09-04 | Dependência para iniciar/encerrar | Próximo handoff | Critério de decisão |
|---|---|---|---|---|
| Fase 0 — baseline e contenção | **Em aberto** | Inventário de diffs e dados mutáveis; execução focal atual | Engenharia + testes | Falhas atuais classificadas e worktree preservado |
| Fase 1 — núcleo de dados | **Aguardando Fase 0** | Baseline confiável | Dados/backend → QA | CSV, persistência, reabertura, histórico/undo e migrações provados |
| Fases 2–3 — qualificação e governança | **Aguardando Fase 1** | Contratos de dados estáveis | IA/backend/governança → segurança e QA | Dossiês auditáveis; autorização, supressão e idempotência provadas em dry-run |
| Fases 4 e 7 — cockpit e métricas | **Aguardando Fases 1–3** | Persistência, política e filtro compartilhado | UI/dados → acessibilidade e evidências | Estado persiste; filtros e métricas reconciliam; UI crítica sem regressão |
| Fases 5, 6 e 8–9 | **Planejadas em paralelo controlado** | Contratos das Fases 1–3 | Especialistas → gates técnicos | Jobs, onboarding, integrações e privacidade atendem critérios próprios |
| Fase 10 — qualidade integral | **Bloqueada por predecessoras** | Fases 4–9 concluídas | Revisores → `reality-checker` | Evidência nova de testes, segurança, desempenho, acessibilidade e UI |
| Fase 11 — release comercial | **Bloqueada por Fase 10 e dependências externas** | Gate integral, documentos legais, assinatura e ambiente limpo | Release → patrocinador | Instalação, operação, backup/restore, atualização e rollback provados |

O caminho crítico permanece `0 → 1 → 2 → 3 → 4 → 7 → 10 → 11`. Trabalho paralelo só deve começar quando o contrato predecessor estiver registrado; alterações simultâneas nos mesmos módulos exigem handoff explícito.

## Dependências externas reais

| Dependência | Necessária para | Estado conhecido | Responsável pela provisão | Tratamento enquanto ausente |
|---|---|---|---|---|
| Credenciais e sandboxes oficiais dos provedores/canais escolhidos | Validar integrações reais no piloto | Não evidenciado | Patrocinador/operador do piloto | Usar mocks e dry-run; não prometer conector ativo |
| Aprovação e termos de uso das plataformas de contato | Executar contato externo de forma autorizada | Não evidenciado | Negócio/jurídico + dono da conta | Manter qualquer envio desativado |
| Certificado Authenticode válido e cadeia confiável | Distribuição Windows assinada | Não evidenciado | Responsável de release/empresa | Build de desenvolvimento pode continuar; release pública não |
| Máquina/VM Windows limpa, independente do ambiente de desenvolvimento | Teste de instalação, abertura, atualização e rollback | Não evidenciado | Responsável de release | Preparar roteiro; não aceitar teste apenas na máquina de desenvolvimento |
| Termos, aviso de privacidade, política de retenção e canal de suporte aprovados | Piloto assistido | Não evidenciado | Negócio/jurídico/DPO | Demonstração somente com dados demo e limitações explícitas |
| Usuários de piloto, dados autorizados e baseline de métricas | Calibrar score e provar valor comercial | Não evidenciado | Product owner/comercial | Não alegar eficácia de vendas; usar cenário sintético identificado |

Essas dependências não impedem as Fases 0–10 em ambiente local com mocks. Elas se tornam bloqueios somente no gate indicado e não justificam interromper a estabilização interna.

## Riscos ativos e respostas

| ID | Risco | Probabilidade/impacto | Sinal atual | Resposta e gatilho de escalonamento |
|---|---|---|---|---|
| R-01 | Perda ou sobrescrita de trabalho/dados locais | Alta/Alta | Bancos e `data/conversations.json` modificados; muitos artefatos temporários removidos | Proibir limpeza/restauração em massa; isolar comandos por caminho. Escalar antes de qualquer ação destrutiva ou migração sem backup. |
| R-02 | Aprovação baseada em evidência obsoleta | Alta/Alta | Evidências de teste principais datam de 24/08; código/testes mudaram em 04/09 | Reexecutar todos os gates após o último diff relevante e registrar comando, data, commit/estado e artefato. |
| R-03 | Integração incompleta entre UI e persistência | Alta/Alta | Contratos apontam gaps de undo/versionamento; UI e stores estão em evolução | Provar reinício, concorrência e falha de gravação; screenshot não encerra o gate. |
| R-04 | Ação externa indevida ou duplicada | Média/Crítico | Ledger único de aprovação/envio ainda é decisão aberta | Manter execução externa desabilitada até preview, aprovação, idempotência, supressão e auditoria passarem. |
| R-05 | Escopo e WIP excessivos | Alta/Alta | 76 responsabilidades planejadas e 12 fases interdependentes | Limitar execução ao caminho crítico e, no máximo, às frentes paralelas liberadas pelo predecessor. |
| R-06 | Promessa comercial maior que a capacidade provada | Alta/Alta | Produto local/single-user; eficácia do score e conectores reais não validados | Usar posicionamento aprovado e submeter toda alegação ao gate de realidade. |
| R-07 | Uso indevido de dados reais como demonstração | Média/Crítico | Origem/consentimento dos dados existentes em `data/` não confirmados | Não reutilizar esses dados como demo; criar dataset sintético rotulado e validar ausência de PII real. |

## Decisões vigentes

1. A primeira oferta é uma demonstração controlada e, depois, piloto assistido; GA não está autorizada.
2. A estabilização do núcleo existente precede novos conectores, mobile, cobrança e colaboração em tempo real.
3. B2B e B2C devem permanecer separados no modelo, na UI e nos gates de consentimento.
4. Toda demonstração usa dry-run, dados identificados como demonstração e nenhuma ação externa real.
5. O fluxo B2B é a recomendação para aprofundamento após os gates; ampliar B2C depende de evidência de piloto e decisão de produto.
6. Nenhuma evidência histórica vale para a versão corrente sem reexecução após as mudanças relevantes.
7. O registro fonte de verdade para aprovação/envio precisa ser decidido antes da Fase 3: recomendação pendente de arquitetura entre ledger comercial dedicado e auditoria geral.

## Decisões necessárias e donos

| Quando | Decisão | Dono recomendado | Prazo relativo | Consequência da ausência |
|---|---|---|---|---|
| Antes de implementar Fase 1 | Estratégia de migração, backup e recuperação dos bancos locais | Arquitetura de dados + product owner | Antes do primeiro diff de persistência | Risco de corrupção/perda e gate bloqueado |
| Antes de encerrar Fase 3 | Fonte de verdade de aprovação/envio e política de idempotência | Software/backend/security architects | Antes dos testes de ação protegida | Outreach permanece desativado |
| Antes de preparar demo | Dataset sintético B2B/B2C e roteiro comercial aceitos | Product manager + comercial + DPO | Após Fase 3 | Demonstração não pode usar dados atuais por presunção |
| Antes do piloto | Provedores/canais realmente suportados e contas sandbox | Product owner + dono das contas | Durante Fases 8–10 | Piloto restrito ao modo local/dry-run |
| Antes da Fase 11 | Responsável por certificado, máquina limpa, suporte e rollback | Patrocinador + release/ops | Antes do build candidato | Distribuição não autorizada |

## Cadência e controle

- Atualizar este documento ao encerrar cada fase ou quando um risco mudar de severidade.
- Para cada handoff, registrar arquivos tocados, testes executados, resultado, artefato e risco residual.
- Reunião/checagem operacional curta por incremento; revisão de gate ao fim da fase, sem declarar percentual de conclusão por contagem de tarefas.
- Escalonar imediatamente: perda/corrupção de dados, envio sem aprovação, quebra de consentimento/supressão, segredo exposto ou regressão de instalação.
- Solicitar decisão do patrocinador apenas quando o bloqueio for externo ou mudar escopo, custo, prazo ou promessa comercial.

## Próximas ações coordenadas

1. Concluir inventário focal do worktree e identificar quais bancos/dados pertencem ao usuário.
2. Executar e registrar a suíte focal definida no roadmap, sem alterar dados reais.
3. Classificar falhas e atribuir donos da Fase 1; congelar expansão de escopo até o baseline.
4. Fechar estratégia de backup/migração e o contrato de persistência antes da implementação.
5. Após Fases 1–3, preparar os dois cenários sintéticos e iniciar as frentes paralelas autorizadas.

## Evidência consultada

- `docs/implementation-roadmap.md`, `docs/product-commercial-readiness.md`, `docs/workflow-contracts.md`, `docs/ux-research-audit.md`, `docs/ux-architecture.md` e `docs/ui-design-contract.md`.
- Estado Git focal observado em 2026-09-04: mudanças em leads/UI/testes e quatro arquivos de dados/bancos; documentos de planejamento ainda não rastreados.
- Diretório `evidence/`: artefatos existentes inspecionados por nome/data; os principais relatórios de teste são de 24/08 e não foram tratados como aprovação da versão atual.
- Nenhum teste foi executado por esta coordenação e nenhum código foi alterado.
