# Arquitetura de UX — Kiara Lead Intelligence

Data: 2026-09-04  
Responsável: `ux-architect`  
Base: pedido comercial, `docs/ux-research-audit.md`, `docs/product-commercial-readiness.md` e estrutura atual da UI PySide6. Especificação implementável; não representa validação com usuários.

## Princípios

1. **Oportunidade antes de volume:** conduzir de métricas a uma oportunidade explicada e sua próxima ação.
2. **Preparar não é executar:** rascunho, aprovação e ação externa são estados e comandos distintos.
3. **Consentimento no ponto de decisão:** origem, base legal e canal permitido permanecem junto da ação B2C.
4. **Fato, hipótese e lacuna não se misturam:** cada afirmação tem tipo, origem, data e confiança aplicável.
5. **Recuperação explícita:** mutações têm confirmação, histórico e desfazer; tarefas têm cancelamento real.
6. **Uma navegação sempre disponível:** redimensionar nunca remove destinos ou kill switch.

## Arquitetura de informação

### Navegação global

Ordem e rótulos estáveis:

1. **Visão geral** — saúde, prioridades e atalhos de ativação.
2. **Pipeline** — oportunidades B2B, etapas, filtros e lote.
3. **Consumidores** — pessoas consentidas, sinais públicos e bloqueios B2C.
4. **Campanhas** — operações, cadências, resultados e aprovações.
5. **Conversas** — histórico pesquisável e Copiloto contextual.
6. **Integrações** — fontes, permissões, limites, testes e reconexão.
7. **Configurações** — perfil comercial, autonomia, privacidade e IA.

O **Dossiê** é rota contextual aberta a partir de Pipeline, Consumidores, Visão geral ou Conversas, não destino global. O **Copiloto** é um modo em Conversas, ligado a uma conversa e, opcionalmente, a uma oportunidade.

Hierarquia da janela: navegação global → cabeçalho da página (título, escopo, período, busca, ação primária) → lista/quadro e detalhe → feedback (erro, progresso, desfazer). Voltar do detalhe restaura destino, filtros, scroll e seleção.

## Navegação responsiva e foco

| Largura útil | Padrão | Contrato |
|---|---|---|
| ≥1180 px | Sidebar de 220–256 px | Ícone+rótulo e lista+detalhe quando couber. |
| 1020–1179 px | Rail de 64–72 px | Ícones com nome acessível e tooltip; expansão opcional. |
| <1020 px | Barra superior + gaveta | “Abrir navegação” sempre visível; gaveta contém sete destinos, Configurações, status e kill switch. |

Exatamente um padrão fica exposto. A gaveta leva foco ao primeiro destino; `Esc` fecha e restaura foco. Após navegar, foco vai ao título da página. Tudo deve permanecer alcançável em 900×680 e escalas de 125%, 150% e 200%.

**Parar ações** permanece visível em repouso. Durante tarefa cancelável, ganha ênfase, rótulo “Parar {operação}” e atalho `Esc`. Um modal aberto consome `Esc` primeiro, prevenindo cancelamento acidental. Em etapa não cancelável, mostrar “Finalizando etapa segura…” e o motivo do bloqueio.

## Onboarding empresarial

### Entrada e retomada

Primeiro uso explica benefício, duração e que integrações podem ser adiadas. Ações: **Começar configuração**, **Usar demonstração identificada** e **Retomar** se houver rascunho. Persistir a cada etapa, sem guardar segredo em texto aberto; sair confirma “Configuração salva como rascunho”.

| Etapa | Essenciais | Regra de avanço |
|---|---|---|
| 1. Operação | B2B/B2C/híbrida, empresa, região | Todos obrigatórios; híbrida mantém fluxos e consentimentos separados. |
| 2. Oferta | Produto, proposta de valor, ticket, diferenciais | Produto e proposta obrigatórios; moeda/unidade explícitas. |
| 3. Público | ICP/personas, segmento, critérios obrigatórios/eliminatórios | Ao menos um público e um critério; conflitos sinalizados. |
| 4. Abordagem | Canais, tom, objeções, responsável, calendário | Ação externa desabilitada sem responsável e canal permitido. |
| 5. Autonomia | Nível 0–7, aprovações, limites, kill switch | Padrão seguro: nível 3; exemplos concretos do permitido/proibido. |
| 6. IA e integrações | Provedor, fontes oficiais, permissões, teste | Opcional; status real “Não conectado”, nunca “Pronto” presumido. |
| 7. Revisão | Resumo, lacunas, efeitos e política de dados | Confirmar e criar; foco no primeiro erro. |

Cabeçalho: “Etapa X de 7” e nomes. Rodapé fixo: **Voltar**, **Salvar e sair**, **Continuar**. Ajuda fica junto ao campo; avançados ficam recolhidos e não bloqueiam o início. Ao concluir, oferecer checklist acionável: importar/conectar, revisar critérios, gerar oportunidades e abrir Visão geral. De uma base vazia, Importar CSV ou Conectar fonte deve exigir no máximo duas ativações.

## Visão geral (cockpit)

Ordem de leitura:

1. Escopo, período, origem dos dados e última atualização.
2. Tarefa em curso com progresso real, fontes, cancelar e detalhes.
3. Métricas calculadas: encontrados, qualificados, vencidos, reuniões, propostas e fechamentos.
4. Próximas ações: oportunidade, motivo, prazo, responsável e comando seguro.
5. Riscos: dados incompletos, integração, consentimento e etapa parada.
6. Funil e origens calculados/comparáveis.

Cards acionáveis devem ser controles reais. Score informa faixa, atualização e fatores; ausência é “Não calculado”. Filtros atualizam cards, gráficos, listas e exportação atomicamente. Durante atualização, manter último valor com “Atualizando”; falha preserva valor anterior e data.

Vazios orientados à causa: sem operação → **Concluir configuração**; sem fonte → **Importar CSV/Conectar fonte**; fonte sem resultado → revisar critérios/período/saúde; filtro sem resultado → **Limpar filtros**.

## Pipeline e Consumidores

### Pipeline B2B

Cabeçalho com busca, filtros, ordenação, seleção múltipla, importar e exportar. Em tela ampla, Kanban; em compacta, alternador **Quadro/Lista**, sendo Lista alternativa completa por teclado. Card: empresa, score explicável, origem, responsável, próxima ação e prazo. Abrir não move. **Alterar etapa** lista destinos e solicita motivo nas transições de alto impacto, como Perdido/Fechado.

### Consumidores B2C

Segmentação primária obrigatória: **Contatáveis**, **Sinais públicos**, **Bloqueados**. Cada item mostra o tipo antes do nome, origem, intenção, consentimento/base legal, canal permitido, retenção e próxima ação.

- Contatável: preparar contato apenas no canal/finalidade autorizados.
- Sinal público: preparar revisão/resposta pública por integração oficial; nunca contato privado.
- Bloqueado: exibir causa e remediação (opt-out, retenção, canal ou política).

Ação desabilitada tem explicação adjacente e acessível. Resposta pública não depende de opt-in privado. Checkout abre prévia dos itens/dados e cria rascunho; publicar/enviar é comando separado sujeito à aprovação.

## Dossiê

Cabeçalho fixo: identidade permitida, B2B/B2C/sinal, etapa, score+confiança, responsável e atualização. Em B2C, origem, consentimento e canal ficam sem scroll. Ações: **Preparar próxima ação**, **Alterar etapa**, **Mais**; “Enviar” nunca é dominante.

Seções:

1. Resumo executivo e recomendação.
2. Evidências verificadas — fato, fonte, data e identificador permitido.
3. Hipóteses a validar — linguagem condicional e confiança.
4. Lacunas e riscos — impacto e forma de confirmação.
5. Qualificação explicada — positivos, negativos, ausentes e cálculo.
6. Histórico e consentimento — eventos, responsável e auditoria.
7. Kit comercial — perguntas, roteiro, objeções, reunião, proposta e fechamento.

Cada seção tem vazio explícito, sem inventar conteúdo. Em tela larga, sumário lateral; em compacta, índice/acordeão no topo. Abrir anuncia o item e foca o título; atualização não rouba foco.

### Preparar, aprovar e executar

`Dossiê → Preparar próxima ação → Conversas com contexto → Revisar rascunho → Solicitar/registrar aprovação → Executar externamente → Registrar resultado`

Conversas mantém chips **Lead: {nome}**, canal e consentimento, mais a faixa **“Rascunho — ainda não executado”**. Trocar lead com rascunho exige salvar, descartar ou cancelar. “Enviar ao Copiloto” apenas refina; “Executar ação” mostra prévia final e respeita autorização. Execução registra chave de idempotência, resultado e responsável; falha jamais parece sucesso.

## Erro, cancelamento e desfazer

Modelo comum: `idle → loading/running → success | partial | error | cancelling → cancelled`. Mensagens nomeiam objeto e consequência. Atualizações são anunciadas por região acessível sem mover foco.

### Erros

- Inline: validação; foco no primeiro erro ao confirmar.
- Banner local: falha de lista/dossiê; manter contexto e oferecer **Tentar novamente**.
- Centro de atividade: falha de tarefa; etapa, fonte, processados e diagnóstico seguro.
- Modal: apenas risco irreversível/decisão obrigatória.
- Item removido: explicar, oferecer voltar/atualizar; nunca retorno silencioso.

### Cancelamento

1. Comando vira “Cancelando…” e bloqueia duplicação.
2. Encerrar em ponto seguro, registrando itens concluídos.
3. Informar **Cancelado**, quantidades preservadas/descartadas e **Retomar** ou **Iniciar novamente**.
4. Se terminou antes do cancelamento, informar conclusão e o resultado real.

### Desfazer

- Mover etapa e excluir/arquivar recuperável exibem snackbar por no mínimo 8 s, com botão e atalho.
- Mensagem nomeia objeto e transição: “Acme movida de Qualificado para Proposta”.
- Desfazer é idempotente; restaura etapa, seleção e histórico com evento compensatório, sem apagar auditoria.
- Irreversível exige confirmação com objeto, quantidade e consequência, sem promessa de desfazer.
- Lote mostra quantidade; falha parcial identifica itens malsucedidos.

## Contratos de componentes

| Componente | Entradas mínimas | Eventos | Estados obrigatórios |
|---|---|---|---|
| Navegação | destino, largura, status | navegar, gaveta, parar | ampla, rail, gaveta, foco restaurado |
| Barra de tarefa | nome, progresso real, fontes, cancelável | detalhes, cancelar | executando, cancelando, parcial, erro, concluído |
| Card | identidade, tipo, score, origem, próxima ação | abrir, selecionar, menu | normal, selecionado, vencido, incompleto |
| Score | total, faixa, fatores, ausentes, data | abrir evidências | calculado, desatualizado, não calculado |
| Ação protegida | rascunho, canal, consentimento, política | revisar, aprovar, executar | bloqueada+motivo, rascunho, aprovação, execução, resultado |
| Desfazer | objeto, mutação, prazo, token idempotente | desfazer, dispensar | ativo, desfazendo, restaurado, falhou |
| Conteúdo | causa, diagnóstico, recuperação | retry, limpar, configurar | carregando, vazio, erro, parcial |

## Critérios de aceite

1. Em 900×680 e 1019 px, sete destinos, Configurações e kill switch são acessíveis; exatamente uma navegação aparece.
2. Base vazia chega a Importar CSV/Conectar fonte em até duas ativações.
3. Onboarding salva rascunho, mostra progresso, valida essenciais e foca primeiro erro.
4. B2C nunca permite contato privado sem opt-in; resposta pública autorizada permanece disponível.
5. Preparar abre contexto identificado e rascunho não executado; geração e execução são comandos separados.
6. Mudar etapa tem alternativa por teclado, anúncio origem/destino, persistência e desfazer por ≥8 s.
7. Carregamento, vazio, erro, retry, cancelamento e falha parcial existem em listas, dossiê e tarefas.
8. Voltar do dossiê restaura destino, filtros, scroll e seleção.
9. Score ausente é “Não calculado”; calculado expõe fatores, faixa, confiança e data.
10. Nenhum estado crítico depende apenas de cor, hover ou ícone; foco permanece visível.

## Sequência e decisões

1. Shell responsivo, foco e kill switch.
2. Modelo de estados, barra de tarefa e feedback acessível.
3. Onboarding persistente e ativação.
4. Segmentos B2C e proteção por consentimento/canal.
5. Dossiê → rascunho → aprovação → execução.
6. Mudança por teclado, histórico e desfazer idempotente.
7. Score explicável e estados vazios/erro.
8. Validação conforme `docs/ux-research-audit.md` antes da prontidão comercial.

Decisões: navegação adaptativa em três faixas substitui ocultação; Dossiê permanece contextual; Integrações é global; segmentação B2C é estrutural, não filtro opcional; desfazer usa 8 s por inclusão. Validação empírica, visual final e persistência/idempotência dependem dos agentes e implementação respectivos; este documento não os aprova.
