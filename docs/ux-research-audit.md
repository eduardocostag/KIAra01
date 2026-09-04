# Auditoria UX — Kiara Lead Intelligence

Data: 2026-09-04  
Escopo: auditoria heurística baseada no código PySide6 e nas evidências visuais existentes. Não houve entrevistas, survey nem teste moderado com usuários; personas e jornadas abaixo são hipóteses de trabalho, não achados empíricos.

## Objetivo e método

Perguntas de pesquisa:

1. Um operador comercial consegue sair de dados brutos para a próxima ação sem perder contexto?
2. Um gestor entende saúde, prioridade e risco do pipeline?
3. Um negócio B2C consegue distinguir sinal público de pessoa contatável sem violar consentimento?
4. Os fluxos essenciais continuam descobríveis em janelas menores, teclado e tecnologias assistivas?

Método: walkthrough cognitivo dos fluxos B2B/B2C, inspeção heurística (visibilidade do estado, correspondência com o mundo real, controle, prevenção de erros, reconhecimento, eficiência e recuperação) e revisão de sinais de acessibilidade no código. Fontes examinadas: `app/ui/desktop.py`, `app/ui/sdr_cockpit.py`, `app/ui/consumer_cockpit.py`, `app/ui/commercial_settings.py`, testes de UI e imagens em `evidence/`.

## Personas provisórias

### Camila — operadora SDR (B2B)

- Trabalha diariamente com dezenas ou centenas de leads; alterna entre priorização, pesquisa, contato e registro.
- Precisa saber “quem abordar agora, por quê e por qual canal”, distinguindo fato, hipótese e lacuna.
- Sucesso: preparar contato ou reunião rapidamente, registrar resultado e manter próxima ação explícita.
- Riscos: mover etapa por engano, perder o lead selecionado ao trocar de tela, confiar em score sem explicação ou disparar abordagem com dado não verificado.

### Rafael — gestor/dono da operação (B2B)

- Consulta visão geral e pipeline algumas vezes por dia; configura ICP, oferta, limites e regras.
- Precisa comparar períodos, localizar gargalos e saber se números representam atividade real.
- Sucesso: detectar risco e decidir foco sem abrir cada dossiê.
- Riscos: métricas sem definição, filtros sem confirmação clara do escopo e cards de orientação que parecem acionáveis, mas não são.

### Luana — atendente de social commerce (B2C)

- Revisa sinais orgânicos e pessoas que deram opt-in; prepara resposta pública, conversa ou checkout.
- Precisa reconhecer imediatamente consentimento, canal permitido e diferença entre interesse casual e intenção de compra.
- Sucesso: avançar a pessoa pelo canal autorizado, ou bloquear corretamente a ação privada.
- Riscos: interpretar oportunidade pública como lead contatável, não entender por que a ação está desabilitada ou não saber como conectar uma fonte.

### Pessoa prospectada/consumidora — sujeito dos dados

- Não opera a interface, mas é afetada por decisões tomadas nela.
- Necessita uso proporcional, origem rastreável, respeito ao opt-out e contato apenas no canal/finalidade consentidos.
- Sucesso: não receber contato indevido e ter seus sinais tratados como hipóteses até confirmação.

## Jornadas e fricções

### B2B: configurar → captar → priorizar → preparar → registrar → avançar

1. **Configurar operação.** O diálogo divide conteúdo em Essencial, Público ideal, Oferta e Avançado, usa linguagem orientadora e nomes acessíveis. Fricção: não há indicação de completude, validação visível de campos mínimos ou resumo do efeito das mudanças antes de salvar.
2. **Captar/importar.** Pipeline oferece “Importar CSV” e “Exportar visão”. Fricção: o estado inicial da Visão geral sugere importar/conectar fonte em cards visualmente semelhantes a ações, mas sem botões; o caminho depende de o usuário descobrir Pipeline.
3. **Priorizar.** Métricas, filtros, próximas ações e score apoiam triagem. Fricção: score/prontidão aparecem como números sem explicação no card/tabela; a justificativa existe apenas após selecionar o lead.
4. **Inspecionar.** O dossiê separa fatos, hipóteses, lacunas, objeções e riscos — boa prevenção de alucinação. Fricção: ao acionar “Preparar próxima ação”, o sistema troca para Conversas e apenas preenche o compositor; falta confirmação contextual persistente do lead e do que ainda não foi executado.
5. **Mover/registrar.** O Kanban aceita drag-and-drop e clique/teclado abre o card. Fricção crítica: mover por arraste persiste imediatamente, sem desfazer, confirmação para transições de alto impacto ou feedback durável; não há alternativa de teclado para mover entre colunas.

### B2C: conectar fonte → revisar sinal/pessoa → validar consentimento → preparar resposta/checkout

1. **Entrada.** O estado vazio explica fontes oficiais, consentimento e intenção. Fricção alta: não há CTA “Conectar fonte” nem indicação de onde executar a conexão.
2. **Triagem.** A tabela reúne pessoa/sinal público, origem, intenção, etapa, consentimento e próxima ação. Fricção: pessoas consentidas e oportunidades públicas convivem na mesma lista sem filtro ou agrupamento; isso aumenta risco de confusão operacional.
3. **Dossiê.** Origem, necessidade, sinais, consentimento/canais, lacunas e oferta ficam separados — boa correspondência ao raciocínio do atendente.
4. **Ação.** O botão só habilita com próxima ação e canal permitido. Fricção crítica: o estado desabilitado não explica qual condição falta; para sinal público, uma resposta pública recomendada pode ficar inacessível porque não há canal privado autorizado, embora o texto recomende revisão/resposta pública.
5. **Checkout.** O rótulo muda para “Preparar checkout” quando pronto para comprar. Fricção: não há prévia nesta tela sobre o que será preparado, quais dados serão usados ou se haverá apenas rascunho versus ação externa.

## Achados priorizados

| ID | Severidade | Achado e evidência | Impacto | Requisito testável |
|---|---|---|---|---|
| UX-01 | Crítica | `desktop.py` oculta a sidebar abaixo de 1020 px; o rail é criado e ocultado sem caminho de reexibição. | Navegação principal desaparece em janelas intermediárias/compactas. | Em 900×680 e 1019 px de largura, todos os cinco destinos e Configurações devem ser alcançáveis por mouse e teclado; exatamente uma navegação compacta ou ampla deve estar visível. |
| UX-02 | Crítica | “Parar ações” recebe atalho Escape, mas é definido como invisível e não há reexibição no arquivo. | Função de emergência não é descobrível; usuários de voz/automação não sabem que podem interromper. | Durante qualquer ação ocupada, “Parar ações” deve estar visível, focável e acionável por Escape; em repouso, deve existir caminho visível para o kill switch. |
| UX-03 | Alta | Cards do estado vazio de “Próximas ações” descrevem ações, mas não emitem ação; o vazio B2C recomenda conectar fontes sem CTA. | Dead-end no primeiro uso e baixa ativação. | Com base vazia, usuário deve chegar a Importar CSV ou Conectar fonte em no máximo 2 ativações, com botão rotulado e foco por teclado. |
| UX-04 | Alta | Consumidores consentidos e oportunidades públicas sem opt-in compartilham tabela; ação B2C é bloqueada sem explicar causa. | Aumenta erro de canal/consentimento e abandono por ambiguidade. | A lista deve oferecer filtro/segmentação “Contatáveis / Sinais públicos / Bloqueados”; botão desabilitado deve expor texto/tooltip com condição ausente; resposta pública não deve depender de opt-in privado. |
| UX-05 | Alta | Drag-and-drop do Kanban persiste mudança imediatamente e não oferece desfazer nem equivalente de teclado para mover. | Erros de etapa afetam relatórios e operação, especialmente para mobilidade reduzida/leitor de tela. | Após mover, exibir confirmação com “Desfazer” por ao menos 5 s; oferecer ação de mudança de etapa operável por teclado e anunciar origem/destino. |
| UX-06 | Alta | Ao preparar próxima ação, a UI troca para Conversas e preenche o campo, mas não envia; contexto selecionado fica fora da área principal. | Usuário pode interpretar preparação como concluída ou enviar para o lead errado. | Exibir chip persistente “Lead: {empresa}” e texto “Rascunho — ainda não executado”; enviar ao modelo e executar ação externa devem ser comandos distintos. |
| UX-07 | Média | Score/prontidão aparecem sem definição ou decomposição antes da abertura do detalhe. | Gestor pode superconfiar no número e operador não entende prioridade. | Todo score deve ter tooltip/nome acessível com faixa, última atualização e fatores; valor ausente deve ser “Não calculado”, não zero implícito. |
| UX-08 | Média | Configuração tem quatro abas, porém sem progresso, campos obrigatórios ou validação pré-salvamento visível. | Perfil incompleto gera resultados pobres sem diagnóstico. | Marcar campos mínimos, impedir/alertar salvamento incompleto e mostrar resumo “X de Y essenciais preenchidos”; foco deve ir ao primeiro erro. |
| UX-09 | Média | Sidebar exibe plano de pesquisa em estados fixos (“Pronto/Em espera”), fontes fixas e uma dica estatística sem fonte apresentada. | Pode comunicar telemetria inexistente ou promessa comercial não verificável. | Estados e fontes devem vir de disponibilidade real; dica quantitativa deve citar fonte/data ou ser removida; teste com serviços ausentes não pode mostrar “Pronto”. |
| UX-10 | Média | Conversas usa seletor no cabeçalho, enquanto a lista lateral é populada mas permanece oculta. | Redundância interna e baixa capacidade de localizar histórico quando houver muitas conversas. | Com 20 conversas, localizar uma conversa conhecida deve exigir pesquisa ou lista com título+data; não depender de combo longo sem busca. |
| UX-11 | Média | Tabela e detalhes respondem a seleção, mas não há estado de carregamento/erro; retornos silenciosos são usados quando store/item não existe. | Falhas parecem “nada aconteceu”, prejudicando confiança e suporte. | Operações de carregar/selecionar devem ter estados carregando, vazio, erro recuperável e retry; item removido deve gerar mensagem visível. |
| UX-12 | Baixa | Vários rótulos essenciais usam símbolos/abreviações (`K`, `AI`, `B2C`, ícones textuais); nomes acessíveis existem em vários controles, mas feedback dinâmico não é anunciado. | Curva de aprendizado e barreiras para leitores de tela. | Em teste com teclado/leitor de tela, destino, seleção, estado ocupado, erro e conclusão devem ser anunciados; foco não pode sumir após troca de workspace. |

## Requisitos de acessibilidade e inclusão

- Navegação completa sem mouse, inclusive seleção e mudança de etapa no pipeline.
- Ordem de foco consistente: navegação → filtros/cabeçalho → lista → detalhe → ação primária.
- Estados não dependem somente de cor; score, consentimento e urgência precisam de texto.
- Ações desabilitadas precisam de explicação adjacente ou tooltip acessível.
- Testar Windows em 125%, 150% e 200% de escala, 900×680 e 1440×860; sem corte, sobreposição ou destinos inacessíveis.
- Incluir participantes com baixa visão, uso exclusivo de teclado e leitor de tela. Não registrar PII real em sessões; usar contas/dados sintéticos e consentimento de gravação separado.

## Plano de validação com usuários

Pesquisa mista em duas rodadas:

- **Rodada formativa:** 5 operadores SDR, 3 gestores/donos e 5 atendentes B2C; incluir ao menos 3 participantes que usem tecnologia assistiva ou ampliação. Sessões moderadas de 60 minutos, think-aloud, dados sintéticos.
- **Rodada quantitativa:** 20 participantes por perfil operacional após correções críticas. O tamanho serve para medir sinais direcionais de usabilidade; não deve ser apresentado como representativo do mercado sem amostragem adequada.

Tarefas:

1. Configurar ICP/oferta e identificar o que falta antes de salvar.
2. Importar leads, encontrar a oportunidade prioritária, justificar o score e preparar uma abordagem sem executá-la.
3. Mover um lead de etapa, corrigir um movimento acidental e registrar interação.
4. Separar sinal público de consumidor contatável, explicar consentimento/canal e preparar a ação adequada.
5. Repetir navegação e ações críticas apenas com teclado em janela de 900×680.

Métricas de aceite:

- ≥ 90% de conclusão sem assistência nas tarefas 1–4; 100% para interromper uma ação.
- Mediana ≤ 2 ativações do estado vazio à importação/conexão.
- Zero contato privado selecionado para sinal sem opt-in.
- ≥ 80% dos participantes explicam corretamente que “Preparar” cria rascunho, não executa ação externa.
- SUS ≥ 75 e confiança pós-tarefa ≥ 4/5, segmentadas por perfil e tecnologia assistiva.

## Ordem recomendada

1. Corrigir UX-01 e UX-02 antes de qualquer demonstração comercial.
2. Resolver ativação e segurança B2C (UX-03/04) e recuperação do Kanban (UX-05).
3. Tornar rascunho/contexto inequívocos (UX-06) e score explicável (UX-07).
4. Validar com usuários; só então otimizar configuração, histórico e estados secundários.

