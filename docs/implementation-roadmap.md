# Roadmap de implementação — Kiara Lead Intelligence

Data da priorização: 2026-09-04  
Responsável: `product-sprint-prioritizer`

## Decisão de portfólio

A entrega comercial deve ser tratada como uma sequência de gates, não como uma expansão simultânea das 15 frentes. O caminho crítico é: preservar o trabalho atual, estabilizar dados e persistência, provar os dois fluxos comerciais, concluir a interface operacional e somente então gerar o instalador e declarar prontidão.

O repositório já contém implementações para leads B2B, consumidores B2C, scoring, dossiês, pipeline, métricas, CSV, provedores com fallback e controles de chamadas remotas. O maior risco imediato não é ausência total de funcionalidades, mas integração incompleta e evidência desatualizada em um worktree com mudanças não confirmadas nos arquivos críticos.

## Critério de priorização

Ordem calculada por valor comercial, redução de risco, dependências e esforço relativo:

- **P0 — bloqueia demonstração ou pode corromper/expor dados:** persistência, consentimento, aprovação externa, CSV, scoring explicável, dossiê, separação B2B/B2C e regressões de UI.
- **P1 — necessário para vender e operar com confiança:** onboarding, filtros/métricas reais, pesquisa em segundo plano, saúde de integrações, UX completa e documentação operacional.
- **P2 — necessário para release controlado:** segurança aprofundada, desempenho, acessibilidade, build/instalador, atualização e rollback.
- **P3 — evolução pós-MVP:** cobrança, mobile, colaboração em tempo real e conectores sem credenciais disponíveis.

## Sequência executável

| Fase | Prioridade | Entrega | Dependências | Critério de saída verificável |
|---|---|---|---|---|
| 0. Baseline e contenção | P0 | Inventário dos diffs, dados mutáveis e artefatos; separar mudança do usuário de artefato de teste; executar suíte focal inicial. | Nenhuma | Estado Git registrado; nenhum arquivo do usuário perdido; falhas reproduzíveis classificadas por produto, ambiente ou teste. |
| 1. Núcleo de dados comercial | P0 | Concluir `csv_io`, mapeamento/preview/validação/normalização/deduplicação, persistência de estágio, histórico, undo e migrações. | Fase 0 | Testes de CSV e persistência passam; reabertura mantém estágio e dados; entradas inválidas geram relatório sem perda silenciosa. |
| 2. Qualificação e dossiê | P0 | Unificar scoring explicável B2B/B2C, proveniência, confiança, ausências, hipóteses e próxima ação; completar artefatos SDR/closer. | Fase 1 | Um lead B2B e um B2C produzem score auditável e dossiê completo sem converter inferência em fato. |
| 3. Governança de ações | P0 | Garantir preview, aprovação, auditoria, idempotência, cancelamento, supressão/opt-out e kill switch em toda ação externa. | Fases 1–2 | Nenhuma mensagem real sai em teste; tentativa não autorizada é bloqueada e auditada; repetição não duplica ação. |
| 4. Cockpit e pipeline | P0 | Corrigir UI crítica, Kanban com drag-and-drop persistente e undo, seleção, filtros, busca, detalhes e estados vazio/carregando/erro. | Fases 1–3 | Movimento visual persiste após reinício; filtros alteram lista e métricas consistentemente; não há sobreposição nas resoluções-alvo. |
| 5. Pesquisas, conversas e jobs | P1 | CRUD completo, seleção/exclusão múltipla, confirmação/undo, deduplicação e pesquisa invisível cancelável com progresso real. | Fase 1; governança da Fase 3 | CRUD e cancelamento passam em testes; pesquisa não abre janela externa; progresso deriva do job real. |
| 6. Onboarding e configurações | P1 | Fluxo guiado essencial/avançado, operação B2B/B2C/híbrida, ICP/persona, consentimento, autonomia, IA e integrações. | Contratos estabilizados nas Fases 1–3 | Configuração válida permite primeiro uso; inválida é explicada; reabertura preserva perfil; padrão é seguro. |
| 7. Dashboards reais | P1 | Métricas de funil, conversão, velocidade, origem, receita potencial, qualidade e ações vencidas, com filtro único compartilhado. | Fases 1, 4 e 5 | Cards, gráficos, tabelas e exportação respondem ao mesmo filtro e reconciliam com consultas de origem. |
| 8. IA e integrações | P1 | Roteamento por capacidade/custo/latência/contexto, schema, timeout/retry/circuit breaker/orçamento/redaction; central de saúde. | Fases 2–3 | Fallback e indisponibilidade têm testes determinísticos; provedor é identificável sem segredo; teste de integração não é confundido com conexão real. |
| 9. Privacidade e segurança | P2 | Segredos, logs, controle de acesso local, retenção, exclusão/portabilidade, sanitização e prompt injection. | Fases 1–3 e 8 | Varreduras e testes focais sem achado crítico aberto; fluxos LGPD demonstráveis; riscos residuais documentados. |
| 10. Acabamento e qualidade | P2 | Revisão visual, acessibilidade, desempenho, testes completos B2B/B2C e evidências em Windows. | Fases 4–9 | Gates de código, segurança, testes, desempenho, acessibilidade, realidade e UI possuem evidência atual, não apenas histórica. |
| 11. Release comercial | P2 | Dados demo identificados, ajuda, termos/privacidade, runbooks, backup/restore, build e instalador, atualização/rollback e checklist comercial. | Fase 10 aprovada | Instalação limpa, abertura, fluxo crítico e rollback testados; versão e limitações aparecem no produto e na documentação. |

## Caminho crítico e paralelismo seguro

O caminho crítico é `0 → 1 → 2 → 3 → 4 → 7 → 10 → 11`. Após os contratos da Fase 1, as Fases 2 e 5 podem avançar em paralelo. Após a política da Fase 3, onboarding, IA/integrações e privacidade podem avançar em paralelo, desde que não editem os mesmos módulos sem handoff explícito. Acabamento visual deve ocorrer depois da estabilização funcional para evitar retrabalho.

## Backlog do primeiro incremento

1. Rodar testes focais dos arquivos já modificados: CSV, cockpit, filtros, lead intelligence, scoring, consumer store/ingestion, providers e router.
2. Corrigir primeiro qualquer falha de integridade, importação, persistência de etapa ou regressão de inicialização.
3. Fechar contrato único de filtro e métricas antes de ampliar gráficos.
4. Criar cenário demonstrativo B2B no Rio Grande do Sul com dados identificados como demonstração e fontes/evidências explícitas.
5. Criar cenário demonstrativo B2C no Rio Grande do Sul com consentimento/base legal, retenção e opt-out explícitos.
6. Provar ambos ponta a ponta em dry-run: ingestão → qualificação → dossiê → pipeline → próxima ação aprovada.

## Itens deliberadamente fora do MVP imediato

- Cliente mobile e processo de lojas.
- Cobrança/assinatura integrada.
- Colaboração multiusuário em tempo real.
- Envio por redes sociais ou WhatsApp sem credenciais, aprovação e sandbox oficiais.
- Scraping de plataformas que proíbam a automação.
- SLOs de produção cloud antes de existir ambiente comercial definido.

Esses itens permanecem no roadmap, mas não devem atrasar uma demonstração local segura e verificável.

## Riscos e respostas

| Risco | Severidade | Resposta |
|---|---|---|
| Worktree contém grande volume de exclusões em artefatos temporários e mudanças em bancos locais. | Alta | Não limpar nem restaurar em massa; isolar status relevante por caminho e preservar dados do usuário. |
| Evidências existentes podem pertencer a uma versão anterior do código. | Alta | Reexecutar gates após a última mudança e registrar comando, data, resultado e artefato. |
| UI parece completa, mas persistência/undo podem não estar integrados. | Alta | Testar reinício real e falhas de gravação; não aprovar apenas por screenshot. |
| Métricas podem divergir entre cards, gráficos e exportações. | Alta | Uma consulta/estrutura de filtro compartilhada e teste de reconciliação. |
| Provedores externos dependem de credenciais e limites. | Média/alta | Mocks e dry-run no gate local; documentar bloqueio externo; nunca alegar validação real sem credencial. |
| Escopo de 15 frentes e 76 agentes favorece atividade sem entrega. | Alta | Cada participação deve produzir conclusão, decisão/diff e evidência; limitar trabalho em progresso ao caminho crítico. |

## Regra para declarar “pronta”

“Pronta para demonstração” exige as Fases 0–7 com os dois cenários ponta a ponta e nenhuma ação externa real. “Pronta para piloto comercial” exige também as Fases 8–10 e credenciais/sandboxes do piloto. “Pronta para distribuição” exige a Fase 11, incluindo teste do instalador em ambiente limpo. Nenhum desses estados deve ser inferido pela quantidade de funcionalidades ou por evidências antigas.
