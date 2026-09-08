# Auditoria heurística para o redesign — Kiara Web

**Data:** 2026-09-05  
**Responsável:** UX Researcher  
**Escopo:** experiência web B2C Instagram em `apps/web`, incluindo landing, shell autenticado, Dashboard, Inbox, Hunter, Pipeline, Dossiê, Integrações, Configurações, login e cadastro.  
**Decisão desta entrega:** somente pesquisa e recomendações; nenhum arquivo da aplicação foi alterado.

## Limites da evidência

Esta é uma auditoria heurística e um walkthrough cognitivo, não um estudo com usuários. Foram examinados o código atual, `docs/web-product-spec.md`, `docs/web-ux-architecture.md`, `docs/web-ui-contract.md`, `docs/web-accessibility-audit.md`, `docs/web-code-review.md` e as capturas `evidence/web-home.png` e `evidence/web-inbox-mobile.png`.

Não houve entrevista, teste moderado, analytics, eye tracking ou observação de uma operação real. Por isso, as prioridades abaixo combinam evidência direta da interface com hipóteses de risco; metas de usabilidade são critérios propostos para o piloto, não resultados já comprovados.

## Perguntas de pesquisa

1. Em cinco segundos, a pessoa entende que a Kiara organiza e qualifica DMs inbound do Instagram com aprovação humana?
2. Um operador encontra a conversa prioritária, entende o contexto e chega ao rascunho sem perder a noção do que foi ou não enviado?
3. A experiência mobile favorece a tarefa central ou exige rolagem e memória excessivas?
4. Um novo owner consegue sair do cadastro para um workspace configurado sem dead-end?
5. Estados de demonstração, conexão, consentimento e aprovação inspiram confiança sem prometer uma operação inexistente?

## Usuário e tarefa central

A persona primária provisória é uma pessoa que atende vendas B2C pelo Instagram, frequentemente alternando entre celular e computador e com pouco tempo por conversa. Seu trabalho principal não é “analisar leads”; é decidir com segurança: **qual DM requer atenção agora, o que ainda falta saber e qual resposta deve seguir para revisão**.

O owner/gestor é uma persona secundária. Ele configura oferta, regras, equipe e Instagram e verifica gargalos. A experiência deve favorecer o operador no uso diário sem esconder controles e evidências de governança do gestor.

## Síntese executiva

A base visual tem boa especificidade de produto: a landing fala de Instagram B2C, distingue preparação de envio e explicita aprovação humana. O shell é limpo e os componentes têm estados acessíveis melhores que um scaffold genérico.

O redesign, porém, não deve ser apenas cosmético. Há quatro riscos prioritários:

1. No mobile, a Inbox empilha lista, conversa e contexto; a ação central fica longe do item selecionado.
2. A interface combina linguagem de operação real com dados demonstrativos e controles sem efeito, prejudicando confiança.
3. Cadastro e autenticação prometem criação/seleção de workspace, mas não há onboarding implementado.
4. Ao trocar de conversa, o rascunho e a qualificação permanecem associados à fixture de Ana Costa, criando contexto inconsistente.

A direção recomendada é uma interface de **fila operacional calma e decisiva**: prioridade antes de métricas, uma ação primária por estado, detalhes progressivos e estados operacionais comprováveis.

## Achados priorizados

| ID | Prioridade | Evidência | Impacto provável | Recomendação específica |
|---|---|---|---|---|
| RUX-01 | **P0** | `InboxWorkspace` usa uma única grade que vira três blocos empilhados abaixo de `xl`; em `web-inbox-mobile.png`, a primeira dobra contém cabeçalho e lista, enquanto conversa, rascunho e contexto ficam abaixo. O contrato de UX exige rotas lista→detalhe no mobile. | A pessoa toca em uma conversa, mas não é levada ao conteúdo. Precisa rolar e lembrar qual item selecionou; responder rapidamente vira uma tarefa longa. | Em `<768 px`, usar `/app/inbox` para a lista e `/app/inbox/:conversationId` para conversa+contexto. Ao tocar, navegar imediatamente; ao voltar, restaurar filtro, busca e scroll. Manter ação “Preparar resposta” próxima ao compositor e respeitar safe area/teclado. |
| RUX-02 | **P0** | Landing mostra “Operação ativa”; Dashboard exibe badge verde “Fluxo saudável” enquanto informa que nenhuma conta Meta está conectada; busca global, “Conectar Instagram”, “Testar conexão”, “Nova oportunidade” e outras ações aparentam estar disponíveis sem operação persistente. | Estados verdes e affordances ativas podem ser interpretados como evidência de conexão ou sucesso. A discrepância reduz confiança precisamente nas ações sensíveis. | Criar um único modelo de status: `Demonstração`, `Não conectado`, `Conectando`, `Conectado/verificado`, `Ação necessária`, `Indisponível`. Nunca mostrar saudável sem teste confirmado. Ação ainda não funcional deve ser removida ou desabilitada com explicação adjacente, não simular sucesso. |
| RUX-03 | **P0** | Cadastro afirma “crie ou selecione a organização”, força redirecionamento para `/app`, mas não existe rota `/onboarding`; o layout operacional exige workspace ativo. | Primeiro usuário real pode cair em erro logo após criar a conta, interrompendo ativação e destruindo a primeira impressão. | Implementar onboarding retomável em seis etapas, conforme o contrato: negócio, qualificação, Instagram, atendimento, controle e revisão. Ausência de `orgId` deve redirecionar para criação/seleção, nunca lançar erro sem recuperação. Mostrar progresso, salvar por etapa e permitir conectar Instagram depois. |
| RUX-04 | **P0** | A conversa ativa muda por `selected`, mas `prepareDraft()` sempre cita “Ana”; fatos, lacunas, iniciais `AC` e próxima ação são fixos. | Um operador pode revisar texto ou evidência de outra pessoa. Além de carga cognitiva, é um risco grave de erro e confiança. | Toda região da Inbox deve receber um único `conversationId` ativo e dados derivados do mesmo DTO. Ao trocar de conversa, cancelar geração pendente, persistir/alertar rascunho não salvo e atualizar cabeçalho, mensagens, score, fatos, lacunas e CTA de forma atômica. Adicionar teste de não vazamento/stale state entre duas conversas. |
| RUX-05 | **P1** | A captura da landing renderiza tipografia serifada, apesar da intenção Geist. Em `globals.css`, `--font-sans` aponta para `var(--font-sans)`, enquanto o layout fornece `--font-geist-sans`. | A primeira impressão parece parcialmente sem estilo; texto pequeno da operação perde legibilidade e consistência entre marketing e produto. | Corrigir o token para a variável Geist. Usar sans de alta legibilidade em toda a aplicação; se houver fonte editorial de display, reservá-la ao hero e testar acentos pt-BR. Validar a fonte computada no navegador, não apenas o build. |
| RUX-06 | **P1** | A faixa amarela “MODO DEMONSTRAÇÃO” é o elemento mais saliente da landing e ocupa altura persistente também no mobile. A proposta de valor e a marca ficam visualmente subordinadas. | A honestidade é positiva, mas a apresentação começa pela limitação, não pelo benefício; em telas pequenas, reduz a área útil repetidamente. | Manter transparência com uma barra compacta de baixa saturação ou badge persistente “Demo”, acompanhado de “Abrir demo”. Dentro do produto, mostrar o estado no seletor de workspace/status da integração. Evitar repetir o mesmo aviso em cada cabeçalho. |
| RUX-07 | **P1** | Dashboard dá peso semelhante a quatro KPIs, estado da integração, funil e alerta. “Próximas ações” aparece abaixo das métricas, embora seja o principal trabalho diário. | O operador precisa interpretar o painel antes de agir; números demonstrativos podem competir com decisões reais e aumentar carga cognitiva. | Reordenar “Hoje” como fila: aprovações vencendo, novas DMs de alta intenção, follow-ups e bloqueios. Colocar uma ação explícita por item. Mover métricas para faixa secundária ou área “Desempenho” e sempre identificar período/fonte. |
| RUX-08 | **P1** | A Inbox expõe simultaneamente busca, quatro filtros, lista, conversa, qualificação, consentimento, fatos, lacunas, próxima ação, bloqueio e três ações de rascunho. Em larguras intermediárias, tudo vira sequência vertical. | Muitos conceitos competem antes de a pessoa concluir a etapa atual; aumenta tempo de varredura e chance de executar o comando errado. | Usar revelação progressiva: lista → conversa/rascunho como núcleo; contexto em painel lateral no desktop e drawer “Qualificação” no mobile. Mostrar a próxima ação e o gate atual primeiro; evidências detalhadas entram em seções expansíveis. |
| RUX-09 | **P1** | O estado visual selecionado na lista usa principalmente um fundo azul muito sutil; filtros têm rótulos longos em uma faixa horizontal; a captura mobile não mostra a principal ação antes da dobra. | Baixa orientação espacial e maior esforço de toque, sobretudo sob pressa, brilho externo, baixa visão ou uso com uma mão. | Reforçar seleção com barra/borda, texto “Selecionada” acessível e contraste calculado. No mobile, priorizar `Novas`, `Para aprovar` e `Aguardando`; mover filtros restantes para “Mais filtros”. Meta: conversa→rascunho em até dois passos, sem rolagem da lista para encontrar a ação. |
| RUX-10 | **P1** | “Hunter” aparece como destino global e usa categorias próprias, embora a proposta principal seja inbound e o produto descreva Hunter como capacidade da Inbox/Pipeline. “Score”, “confidence” e o nome Hunter exigem aprendizado. | O operador pode não saber se deve começar em Inbox, Hunter ou Pipeline, fragmentando o mesmo caso comercial. | Em teste de card sorting, validar o rótulo. Hipótese inicial: renomear para “Oportunidades” ou incorporar “Sinais” à Inbox; manter “Hunter” como nome da inteligência/assistente, não necessariamente como arquitetura de informação. Sempre explicar score por fatores e data. |
| RUX-11 | **P2** | Busca global e identidades `Studio Aurora`, `Eduardo` e `EG` estão hardcoded; tema Claro/Escuro/Sistema prometido no contrato de UX não está visível. | Personalização fictícia e controles incompletos fazem a experiência parecer protótipo. | Derivar nome, workspace e avatar da sessão/DTO; no modo demo, rotular a organização como “Workspace de demonstração”. Remover busca até existir ou conectá-la a resultados reais. Disponibilizar tema no menu de conta. |
| RUX-12 | **P2** | Várias mutações locais não exibem pending, erro, retry, expiração ou recuperação; descartar demo elimina estado imediatamente e o Pipeline não oferece mudança de etapa/undo na interface web. | A pessoa não sabe se a ação foi registrada nem como desfazer um erro. | Padronizar máquina visual de estado para ações: pronta → processando → confirmada/pendente de aprovação → erro recuperável. Preservar rascunho, confirmar descarte e oferecer undo para a última transição elegível. |

## Recomendações de hierarquia para a próxima interface

### 1. Landing: uma promessa, uma prova, uma ação

- Hero: “Transforme DMs do Instagram em próximas ações — com aprovação humana”.
- CTA primário único: “Abrir demonstração” enquanto cadastro real não estiver operacional; depois, “Criar workspace”.
- Prova visual: uma conversa completa em três estados — recebida, qualificada, pronta para revisão — sem chamar a operação de ativa.
- Segurança e controle aparecem como prova logo após o benefício, não como linguagem genérica de “acesso seguro”.
- A barra de demo informa o estado sem dominar a identidade visual.

### 2. “Hoje”: fila de trabalho antes de dashboard

Ordem sugerida:

1. **Precisa de você agora:** aprovações e violações de SLA.
2. **Novas oportunidades:** DMs com intenção e lacuna principal.
3. **Aguardando retorno:** follow-ups com data e responsável.
4. **Proteções ativas:** bloqueios e saúde da integração.
5. Métricas do período, em segundo plano.

Cada linha deve responder “por que agora?”, “qual é a próxima ação?” e “o que acontece ao clicar?”.

### 3. Inbox desktop: foco no diálogo

- Lista entre 320–360 px com prioridade, último texto, tempo, status e responsável.
- Conversa como região dominante, com separação inequívoca entre lead e operador.
- Compositor sempre mostra `Rascunho — não enviado`, gate e validade da aprovação.
- Contexto lateral começa por “Próxima ação” e “Lacunas”; score/fatos completos ficam progressivos.
- Um único CTA primário por estado: `Preparar`, `Solicitar aprovação` ou `Enviar`, nunca os três competindo.

### 4. Inbox mobile: navegação master-detail

```text
Inbox                         Conversa
Busca e filtro                ← Inbox   Ana Costa
──────────────────            status + origem
Nova · Ana Costa       →      mensagens
Para aprovar · Lucas   →      ──────────────────
Aguardando · Marina    →      rascunho
                              [Preparar resposta]
                              [Qualificação]
```

O detalhe deve abrir como rota. “Qualificação” vira drawer; o compositor permanece visível acima do teclado e da safe area. O botão Voltar devolve a pessoa ao mesmo ponto da lista.

### 5. Onboarding: valor antecipado e conexão honesta

- Mostrar “Etapa X de 6”, tempo estimado e salvamento automático confirmado.
- Explicar por que cada campo melhora a qualificação, evitando formulários abstratos.
- Na conexão Meta, diferenciar requisitos, autorização, validação e saúde.
- Permitir “Explorar com dados de demonstração” sem misturar esse estado com um workspace real.
- Finalizar com checklist claro: workspace criado, regras salvas, Instagram conectado ou pendente e primeira ação recomendada.

## Critérios de sucesso do redesign

Metas propostas para o piloto, a serem medidas com dados sintéticos:

| Resultado | Critério |
|---|---|
| Compreensão em 5 segundos | ≥80% descrevem “organiza/qualifica DMs do Instagram com revisão humana”; 0% concluem que envia automaticamente. |
| Tarefa central desktop | ≥90% abrem a DM prioritária, identificam uma lacuna e solicitam aprovação sem ajuda; mediana ≤90 s. |
| Tarefa central mobile | ≥90% saem da lista para o rascunho em até 2 navegações; nenhuma rolagem da lista é necessária depois da seleção. |
| Consistência de contexto | 100% dos testes automatizados e sessões exibem nome, mensagens, fatos e rascunho da mesma conversa; zero conteúdo residual ao trocar de item. |
| Onboarding | ≥70% concluem configuração base em até 10 min, excluindo tempo externo de OAuth; abandono por dead-end = 0. |
| Confiança | Média ≥4/5 para “sei o que será executado” e “sei se a conta está conectada”. |
| Prevenção de erro | Zero envio sem aprovação válida e zero seleção de DM privada para sinal público/opt-out. |
| Recuperação | 100% localizam como retomar falha de rede, rascunho preservado e última mudança elegível. |
| Acessibilidade | Caminho crítico completo por teclado; WCAG 2.2 AA em axe; teste com NVDA/Chrome, zoom 200% e forced colors sem bloqueador. |

## Plano mínimo de validação

### Rodada formativa

- 5 operadores de vendas/atendimento por Instagram e 3 owners/gestores.
- Pelo menos 4 participantes mobile-first; incluir pessoas com baixa visão, ampliação, navegação por teclado ou leitor de tela.
- Sessões moderadas de 45–60 minutos, consentimento explícito e contas sintéticas.

Tarefas:

1. Explicar o que a Kiara faz após cinco segundos na landing.
2. Criar workspace, configurar uma oferta e identificar o estado da conexão Instagram.
3. No celular, encontrar a DM mais urgente, entender intenção/lacuna e preparar resposta.
4. Corrigir o rascunho, solicitar aprovação e explicar se algo foi enviado.
5. Trocar de conversa e confirmar que todo o contexto mudou.
6. Recuperar uma falha de API e localizar uma oportunidade no Pipeline.

Coletar conclusão, tempo, desvios, erros, SEQ após cada tarefa e confiança percebida. O SUS pode resumir a rodada, mas não substitui a observação dos erros críticos.

## Ordem recomendada de implementação

1. Corrigir contexto cruzado da Inbox e estados de confiança (RUX-02/04).
2. Implementar a navegação mobile lista→detalhe (RUX-01).
3. Criar onboarding/workspace recuperável (RUX-03).
4. Corrigir tipografia e reorganizar hierarquia de Landing e “Hoje” (RUX-05/06/07).
5. Reduzir carga da Inbox e validar arquitetura de informação do Hunter (RUX-08/09/10).
6. Completar personalização, tema, feedback, recuperação e testes com usuários (RUX-11/12).

O gate visual só deve aprovar o redesign depois de a tarefa principal ficar mais curta, o estado operacional ser verificável e os testes mostrarem que beleza não ocultou risco ou ação.
