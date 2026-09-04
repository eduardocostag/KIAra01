# Plano de execução dos agentes — Kiara Lead Intelligence

Data: 2026-09-04  
Responsável: `agents-orchestrator`

## Objetivo, capacidade e rastreabilidade

Este plano transforma o inventário de 76 agentes e o roadmap em uma fila executável. O agente principal coordena e ocupa um dos quatro slots; cada rodada admite, portanto, **no máximo três especialistas simultâneos**. Os três só trabalham em paralelo se não compartilharem arquivos de escrita; caso contrário, são serializados dentro da rodada.

Cada agente tem uma responsabilidade primária única. Perfis de itens fora do MVP (mobile, cobrança, colaboração em tempo real e vídeo) produzem apenas parecer `ADIADO` ou `NÃO APLICÁVEL`, salvo mudança explícita de escopo.

Todo despacho informa fase, objetivo, arquivos de escrita e leitura, decisões anteriores, verificação esperada, artefato de saída e a obrigação de preservar mudanças alheias. Todo retorno registra data, caminhos examinados/alterados, conclusão, decisão ou diff, comandos realmente executados, resultado, evidência, risco residual e destinatário do handoff. Sem isso, permanece `Planejado`.

Estados: `PLANEJADO → EM_EXECUÇÃO → EM_QA → APROVADO`, ou `ADIADO/BLOQUEADO`. Um `FAIL` retorna ao implementador com achados concretos. Após três tentativas, vira `BLOQUEADO`; nunca se presume aprovação.

## Rodadas

| Rodada | Fase | Especialistas (máximo 3) | Saída e handoff |
|---:|---|---|---|
| 0 | Baseline realizado | `product-manager`, `product-sprint-prioritizer`, `project-manager-senior` | Produto, roadmap e inventário → coordenação. |
| 1 | Coordenação | `agents-orchestrator`, `project-shepherd`, `codebase-onboarding-engineer` | Plano, dependências e mapa do código → arquitetura. |
| 2 | 0 | `software-architect`, `backend-architect`, `workflow-architect` | Fronteiras e contratos → dados, UX e segurança. |
| 3 | 0 | `ux-researcher`, `ux-architect`, `workflow-optimizer` | Jornadas e processo mínimo → UI e governança. |
| 4 | 1 | `data-engineer`, `database-optimizer`, `database-reliability-engineer` | Contrato de dados, consultas, migrações e recuperação → implementação. |
| 5 | 1 | `ai-data-remediation-engineer`, `minimal-change-engineer`, `senior-developer` | CSV/persistência/undo com regras determinísticas → QA-1. |
| 6 | 2 | `ai-engineer`, `prompt-engineer`, `rag-pipeline-engineer` | Scoring, schemas, proveniência e memória → avaliação. |
| 7 | 2 | `search-relevance-engineer`, `multi-agent-systems-architect`, `model-qa-specialist` | Busca mensurável, limites multiagente e avaliação → governança. |
| 8 | 3 | `automation-governance-architect`, `agentic-identity-trust`, `identity-access-engineer` | Aprovação, identidade, idempotência e kill switch → implementação. |
| 9 | 3 | `autonomous-optimization-architect`, `visual-operations-copilot`, `api-platform-engineer` | Limites operacionais/financeiros e contratos externos → conectores. |
| 10 | 4 | `ui-designer`, `desktop-app-engineer`, `frontend-developer` | Contrato visual, estados e responsividade desktop → QA-UI. |
| 11 | 4–5 | `rapid-prototyper`, `developer-tooling-engineer`, `git-workflow-master` | Spikes isolados, comandos e rastreabilidade; só resultado aprovado integra. |
| 12 | 5 | `mcp-builder`, `email-intelligence-engineer`, `network-engineer` | Conectores autorizados, e-mail e rede → QA de API. |
| 13 | 5/P3 | `realtime-collaboration-engineer`, `voice-ai-integration-engineer`, `video-streaming-engineer` | Parecer de aplicabilidade; por padrão `ADIADO`. |
| 14 | 6–7 | `data-consolidation-agent`, `data-visualization-engineer`, `support-analytics-reporter` | Dataset, visualizações e métricas reconciliadas → testes. |
| 15 | 8/P3 | `tool-evaluator`, `finops-engineer`, `payments-billing-engineer` | Matriz ferramenta/custo; cobrança por padrão `ADIADO`. |
| 16 | 9 | `security-architect`, `secrets-credential-hygiene-engineer`, `cloud-security-architect` | Threat model, segredos e aplicabilidade cloud → AppSec. |
| 17 | 9 | `privacy-engineer`, `data-privacy-officer`, `compliance-auditor` | Controles, LGPD e matriz de evidências → segurança/documentação. |
| 18 | 9 | `appsec-engineer`, `threat-detection-engineer`, `incident-response-commander` | Correções, detecções e runbook → gate de segurança. |
| 19 | 9 | `ai-generated-code-auditor`, `penetration-tester`, `code-reviewer` | Achados por segurança/correção; `FAIL` volta ao dono do diff. |
| 20 | 10 | `test-automation-engineer`, `api-tester`, `performance-benchmarker` | Evidência funcional, contratual e de desempenho → análise. |
| 21 | 10 | `accessibility-auditor`, `ui-finish-gate-reviewer`, `evidence-collector` | Acessibilidade, acabamento e screenshots atuais → gate final. |
| 22 | 10 | `test-results-analyzer`, `reality-checker`, `executive-summary-generator` | Risco e veredito; resumo não contradiz o gate. |
| 23 | 11 | `sre`, `it-service-manager`, `devops-automator` | SLO/runbooks proporcionais e release reproduzível → documentação. |
| 24 | 11/P3 | `technical-writer`, `mobile-app-builder`, `mobile-release-engineer` | Manuais desktop; mobile registra viabilidade/adiamento. |
| 25 | Condicional | `jira-workflow-steward` | Sozinho e apenas com Jira autorizado; senão `NÃO APLICÁVEL`. |

Os 76 agentes aparecem exatamente uma vez como responsáveis primários. A rodada 0 registra entregas existentes; as demais só mudam de status com retorno verificável.

## Loops Dev-QA

Para cada unidade implementável: (1) atribuir dono e caminhos exclusivos; (2) executar teste focal; (3) obter QA independente; (4) devolver `FAIL` ao mesmo dono sem ampliar escopo; (5) registrar evidência antes do handoff.

| Gate | Origem | QA independente | Evidência de saída |
|---|---|---|---|
| QA-1 Dados | Rodadas 4–5 | `test-automation-engineer` + `database-reliability-engineer` | CSV inválido sem perda; estágio após reinício; undo/migração. |
| QA-2 IA | Rodadas 6–7 | `model-qa-specialist` + `ai-generated-code-auditor` | B2B/B2C auditáveis; hipótese não vira fato; regressão determinística. |
| QA-3 Governança | Rodadas 8–9 | `appsec-engineer` + `api-tester` | Dry-run, bloqueio sem aprovação, auditoria e não duplicidade. |
| QA-4 Desktop | Rodadas 10–11 | `accessibility-auditor` + `evidence-collector` | Persistência, filtros reconciliados, estados e resoluções-alvo. |
| QA-5 Integrações | Rodadas 12–15 | `api-tester` + `tool-evaluator` | Timeout/fallback mockados; nenhum segredo; conexão real não simulada. |
| QA-6 Segurança | Rodadas 16–19 | `penetration-tester` + `compliance-auditor` | Nenhum crítico aberto; riscos residuais documentados. |
| QA-7 Release | Rodadas 20–24 | `reality-checker` + `ui-finish-gate-reviewer` | Suíte, acessibilidade, desempenho, instalador limpo e rollback atuais. |

Reaparecer como QA não cria segunda responsabilidade no inventário; é revisão independente do artefato.

## Dependências e declaração comercial

O caminho crítico permanece `0 → 1 → 2 → 3 → 4 → 7 → 10 → 11`. Fases 2 e 5 podem avançar em paralelo após a Fase 1. Fases 6, 8 e 9 podem ser preparadas após a política da Fase 3, sem escrita concorrente. Fase 10 aguarda estabilização funcional; Fase 11 exige evidência posterior ao último diff relevante.

`DEMO` requer Fases 0–7 e cenários B2B/B2C ponta a ponta em dry-run. `PILOTO` acrescenta Fases 8–10 e sandboxes/credenciais autorizados. `DISTRIBUIÇÃO` acrescenta Fase 11, instalação limpa e rollback. Número de agentes ou evidência histórica não substitui esses critérios.
