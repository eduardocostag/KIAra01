# Blueprint de redesenho UX/UI — Kiara Web

**Status:** contrato implementável para a próxima iteração visual; não representa código pronto nem validação com usuários  
**Data:** 2026-09-05  
**Responsável:** UX Architect  
**Escopo:** produto autenticado em `apps/web`, com continuidade visual para a landing pública  
**Prioridade:** operação B2C inbound pelo Instagram, com qualificação explicável e aprovação humana

## 1. Resultado do redesenho

A Kiara deve parecer uma central comercial inteligente e confiável, não um painel administrativo genérico. O impacto vem de três escolhas: hierarquia editorial forte, um único foco operacional por tela e uma assinatura visual reconhecível baseada em azul-noite + íris elétrica. A facilidade de uso vem de rotas progressivas no mobile, ações contextualizadas e estados honestos.

Em qualquer rota, o operador deve responder em até três segundos:

1. O que precisa da minha atenção?
2. O que a Kiara entendeu e quão confiável é essa leitura?
3. Qual é a próxima ação segura?

O redesenho não altera as regras do produto: gerar, editar, aprovar e enviar continuam operações diferentes; sinal público não autoriza DM privada; opt-out e kill switch sempre prevalecem; sucesso externo só pode ser exibido após confirmação do backend/provedor.

## 2. Diagnóstico das evidências atuais

Fontes examinadas: `evidence/web-home.png`, `evidence/web-inbox-mobile.png`, componentes atuais de `apps/web/src/components/app-shell`, páginas autenticadas, `docs/web-product-spec.md`, `docs/web-ux-architecture.md`, `docs/web-ui-contract.md`, `docs/web-code-review.md` e `docs/web-accessibility-audit.md`.

### O que preservar

- A landing já possui assinatura de marca, mensagem específica para Instagram B2C e contraste dramático.
- O shell tem navegação curta, skip link, estado ativo claro e aviso de autonomia.
- A Inbox já separa lista, conversa e contexto no desktop.
- A linguagem de aprovação humana, canal permitido e dados demonstrativos é honesta.
- Os componentes shadcn/Radix fornecem base acessível e customizável.

### O que corrigir

- A landing tem personalidade maior que o produto autenticado; dentro do app, cards brancos equivalentes deixam tudo com o mesmo peso.
- O dashboard começa por uma saudação genérica e quatro métricas homogêneas, em vez de priorizar decisões.
- A Inbox mobile empilha lista, conversa e contexto numa página longa; selecionar uma conversa precisa abrir uma rota, não revelar outro painel abaixo da lista.
- A Inbox expõe vários botões simultaneamente mesmo quando existe apenas uma próxima ação válida.
- Hunter usa uma grade de cards com pouco contexto comparativo; sinais, oportunidades e bloqueios precisam de inspeção progressiva.
- O Pipeline comprime cinco colunas numa grade responsiva; o quadro deve ter colunas de largura estável e rolagem horizontal intencional.
- O Dossiê repete cards pequenos e deixa a linha do tempo isolada; decisão, risco e próxima ação devem permanecer visíveis.
- O banner amarelo de demonstração domina a marca. A advertência deve continuar persistente, porém integrada ao chrome do produto.
- Busca global, comando rápido e alternância Claro/Escuro/Sistema não estão disponíveis de forma consistente.

## 3. Tese visual: “radar de oportunidades”

A interface combina superfícies calmas com sinais luminosos pontuais. Não usar glassmorphism generalizado, gradientes em todos os cards ou arco-íris de status.

- **Base:** grafite azulado no escuro; névoa azul muito clara no claro.
- **Assinatura:** íris/cobalto para ação principal, seleção e inteligência assistida.
- **Pulso:** uma linha ou halo discreto em áreas de prioridade, nunca como decoração repetida.
- **Estados:** esmeralda, âmbar e vermelho somente para semântica operacional.
- **Dados:** numerais tabulares e bom contraste; gráficos nunca dependem apenas de cor.
- **Movimento:** 140–180 ms para hover, seleção, sheet e expansão. Nada deve atrasar a ação.

### Regra de impacto

Cada tela pode ter apenas uma superfície de alta ênfase: hero operacional, conversa selecionada, job em execução ou CTA final. O restante sustenta essa decisão com baixo ruído.

## 4. Contrato de design

### 4.1 Tokens de cor

Usar tokens semânticos em OKLCH e classes shadcn (`background`, `card`, `muted`, `border`, `primary`, `ring`). Valores são baseline de implementação e devem passar por contraste calculado.

| Token semântico | Claro | Escuro | Uso |
|---|---|---|---|
| `--background` | `oklch(0.975 0.010 265)` | `oklch(0.125 0.024 267)` | canvas global |
| `--surface` / `--card` | `oklch(0.995 0.004 265)` | `oklch(0.165 0.027 267)` | painéis principais |
| `--surface-elevated` | `oklch(1 0 0)` | `oklch(0.205 0.030 267)` | popovers, composer, dialogs |
| `--foreground` | `oklch(0.19 0.030 267)` | `oklch(0.965 0.008 265)` | texto primário |
| `--muted-foreground` | `oklch(0.50 0.025 267)` | `oklch(0.72 0.020 265)` | texto secundário |
| `--border` | `oklch(0.89 0.018 265)` | `oklch(1 0 0 / 0.11)` | divisores e contornos |
| `--primary` | `oklch(0.56 0.225 271)` | `oklch(0.72 0.180 270)` | CTA, seleção, foco de IA |
| `--primary-subtle` | `oklch(0.94 0.045 271)` | `oklch(0.30 0.080 271 / 0.55)` | fundos selecionados |
| `--success` | `oklch(0.61 0.155 153)` | `oklch(0.73 0.145 153)` | confirmação real |
| `--warning` | `oklch(0.70 0.150 78)` | `oklch(0.79 0.140 78)` | atenção/revisão |
| `--danger` | `oklch(0.58 0.220 27)` | `oklch(0.72 0.180 27)` | bloqueio/falha |
| `--info` | `oklch(0.60 0.145 235)` | `oklch(0.75 0.130 235)` | estado informativo |

Regras:

- não usar classes Tailwind de cores arbitrárias em superfícies fundamentais;
- status sempre combina ícone, rótulo e cor;
- `primary` não significa “sucesso”; confirmação usa `success`;
- mensagens da Kiara usam `primary-subtle`, sem parecer mensagem enviada pelo operador;
- o tema claro não é uma inversão lavada do escuro: bordas e superfícies precisam de separação real.

### 4.2 Tipografia

Família de produto: Geist Sans. Geist Mono apenas para IDs, horários, contadores, scores e atalhos.

| Papel | Tamanho/linha | Peso | Uso |
|---|---:|---:|---|
| Display operacional | 40/44 px | 650–700 | uma frase curta no Dashboard |
| H1 | 30/36 px | 650 | título da rota |
| H2 | 20/28 px | 620 | seção/painel |
| H3 | 15/22 px | 600 | grupos e cards |
| Corpo | 14/22 px | 400 | interface padrão |
| Corpo forte | 14/22 px | 550 | rótulos e linhas |
| Auxiliar | 12/18 px | 450 | metadados |
| Micro | 11/16 px | 550 | timestamps, badges; nunca texto longo |
| Métrica | 32/36 px | 650 | números principais com `tabular-nums` |

Títulos são compactos e sem serif no produto autenticado. Limitar descrições de página a 68 caracteres por linha.

### 4.3 Espaço, densidade e geometria

- Escala: 4, 8, 12, 16, 20, 24, 32, 40 e 48 px.
- Densidade confortável em Dashboard/Dossiê/Configurações: `gap-6`, `p-6`.
- Densidade operacional em Inbox/Pipeline/Hunter: `gap-3/4`, `p-3/4`.
- Controles: 40 px no desktop; 44 px em touch/mobile.
- Raio base: 10 px; controles 10 px; cards 14 px; painéis especiais 18 px; pílulas somente para filtros/status.
- Borda substitui sombra na maior parte das superfícies. Sombra apenas em popovers, composer elevado e painel em foco.
- Separadores internos devem substituir “card dentro de card”.

### 4.4 Elevação

| Nível | Estilo | Elementos |
|---|---|---|
| 0 | canvas sem sombra | fundo da aplicação |
| 1 | borda + superfície | cards, lista, colunas |
| 2 | borda forte + sombra curta | composer, toolbar sticky, card selecionado |
| 3 | sombra de overlay | Sheet, Dialog, Command |

### 4.5 Ícones e imagens

- Lucide, traço consistente, 16 px em controles e 20 px em navegação.
- Ícone nunca substitui rótulo de uma ação nova ou crítica.
- Avatares podem usar iniciais; nunca inventar foto de cliente.
- O orb/estrela Kiara aparece somente na marca, em ações assistidas e no estado de geração; no máximo uma vez por região.

## 5. Shell da aplicação

### 5.1 Desktop amplo — `>=1280 px`

- Sidebar fixa de 264 px.
- Utility bar de 64 px, sticky, sobre o conteúdo.
- Conteúdo operacional ocupa toda a largura restante; máximo de 1720 px somente em telas ultrawide.
- Sidebar contém: marca, workspace, grupo “Trabalho”, grupo “Sistema”, indicador compacto de autonomia e conta.
- Ordem principal: **Hoje, Inbox, Hunter, Pipeline, Integrações**.
- Configurações, Ajuda, tema e Sair ficam no menu de conta.
- Inbox exibe badge numérico; os outros destinos só exibem badge quando existe pendência acionável.

### 5.2 Desktop compacto/tablet paisagem — `1024–1279 px`

- Rail de 76 px com tooltips e estado ativo por forma + cor.
- Workspace, conta, tema e configurações abrem em popover/sheet.
- Inbox vira duas colunas; contexto abre em Sheet à direita.
- Não ocultar destinos sem oferecer alternativa direta.

### 5.3 Tablet — `768–1023 px`

- Topbar de 60 px e drawer de navegação.
- Uma região primária por vez.
- Inbox lista e thread são rotas distintas.
- Filtros e contexto usam Sheet.

### 5.4 Mobile — `<768 px`

- Topbar de 56 px: marca compacta, workspace abreviado, atividade e conta.
- Bottom navigation persistente: Hoje, Inbox, Pipeline e Mais. `Mais` contém Hunter, Integrações, Configurações, ajuda e tema.
- Conteúdo tem 16 px de margem e `padding-bottom` que respeita a barra e `safe-area-inset-bottom`.
- Nenhuma tela empilha lista + detalhe + contexto.
- Ações da rota podem usar barra inferior sticky acima da navegação; teclado virtual não pode esconder composer/CTA.

### 5.5 Utility bar

Ordem: breadcrumb contextual → busca/comando → saúde/atividade → workspace → conta. Em telas pequenas, busca é ícone que abre Command.

O aviso demo atual deve virar uma faixa integrada de 28–32 px:

`◉ Demonstração · dados fictícios · envio desativado`

Fundo âmbar sutil, texto de alto contraste, sem amarelo saturado em tela inteira. É persistente e não pode ser dispensado enquanto fixtures estiverem ativas.

### Wireframe do shell

```text
┌──────────────────┬───────────────────────────────────────────────────────────┐
│ KIARA            │ Demo · dados fictícios · envio desativado                │
│ Studio Aurora ▾  ├───────────────────────────────────────────────────────────┤
│                  │ / Inbox / Ana Costa   [⌘ K Buscar ou comandar]   ● Saúde │
│ HOJE             ├───────────────────────────────────────────────────────────┤
│ Inbox          3 │                                                           │
│ Hunter           │                    CONTEÚDO DA ROTA                        │
│ Pipeline         │                                                           │
│                  │                                                           │
│ SISTEMA          │                                                           │
│ Integrações      │                                                           │
│                  │                                                           │
│ Autonomia 3      │                                                           │
│ EG · Conta ▾     │                                                           │
└──────────────────┴───────────────────────────────────────────────────────────┘
```

## 6. Dashboard “Hoje”

O Dashboard deixa de ser coleção de KPIs e vira uma fila de decisão.

### Hierarquia

1. **Hero operacional:** “3 conversas precisam de você”, resumo do porquê e CTA `Revisar agora`.
2. **Linha de saúde:** Instagram, webhook, aprovação/kill switch e horário da última atualização.
3. **Fila prioritária:** aprovações, novas DMs, SLA e bloqueios, ordenados por urgência.
4. **Próximas ações:** lista escaneável com prazo, responsável e motivo.
5. **Pulso do funil:** métricas reais compactas; gráfico é secundário.

Não iniciar com “Boa tarde, Eduardo”. A saudação pode ser auxiliar, mas a informação central é o trabalho pendente.

### Wireframe

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ HOJE                                                                        │
│ 3 conversas precisam de você                         [Revisar agora →]      │
│ 2 aprovações · 1 lead perto do SLA · atualizado às 14:32                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ ● Instagram demo/saudável   ● Aprovação ativa   ● Kill switch disponível  │
├───────────────────────────────────────┬─────────────────────────────────────┤
│ PRIORIDADES                           │ PULSO DE HOJE                       │
│ [Aprovar resposta · Ana · 12 min]     │ 03 novas DMs        +2 desde ontem │
│ [Responder Marina · SLA em 24 min]    │ 02 qualificadas     67% do total   │
│ [Revisar consentimento · Lucas]       │ 94% dentro do SLA                  │
│                          [Ver todas]  │ [mini funil acessível]              │
├───────────────────────────────────────┴─────────────────────────────────────┤
│ PRÓXIMAS AÇÕES · responsável · prazo · motivo                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Composição shadcn

`Card` apenas para hero e duas regiões principais; filas são listas com `Separator`. Usar `Badge`, `Button`, `Progress`, `Tooltip` e `Alert` para estados. Evitar quatro cards métricos iguais no topo.

## 7. Inbox — caminho crítico

### 7.1 Geometria desktop

Em `>=1280 px`, a Inbox usa altura do viewport abaixo do chrome e três painéis com scroll independente:

- lista: 340–380 px;
- conversa: `minmax(480px, 1fr)`;
- contexto: 320–360 px;
- divisores de 1 px, sem cards externos aninhados;
- header, toolbar, cabeçalho da conversa e composer são sticky dentro de seus painéis.

```text
┌──────────── LISTA 360 ───────────┬──────────── THREAD flex ───────────┬── CONTEXTO 344 ──┐
│ Inbox                  3 novas   │ Ana Costa     Canal permitido [⋯] │ 82 · confiança alta│
│ [Buscar] [Filtros ▾]             ├───────────────────────────────────┤ Intenção            │
│ Todas Novas Aprovação Cliente    │ Hoje                              │ Consultoria          │
├──────────────────────────────────┤   [mensagem recebida]              ├─────────────────────┤
│ ● Ana Costa     14:22   PRIOR.   │                    [operador]      │ Fatos verificados    │
│   “Queria entender...”           │                                   │ • metragem [fonte]   │
│   Aprovação · SLA 18 min         │   ✦ Leitura Kiara                  ├─────────────────────┤
├──────────────────────────────────┤     intenção + explicação          │ Lacunas              │
│   Marina Lima    14:06           │                                   │ • orçamento          │
│   Aguardando cliente             ├───────────────────────────────────┤ Próxima ação         │
│                                  │ RASCUNHO · ainda não enviado       │ Confirmar escopo     │
│                                  │ [editor]                            │ [Abrir dossiê]       │
│                                  │             [Solicitar aprovação]  │                     │
└──────────────────────────────────┴───────────────────────────────────┴─────────────────────┘
```

### 7.2 Linha da conversa

Cada item de lista tem 76–88 px e apresenta, nesta ordem:

1. não lida/prioridade por marca + texto;
2. nome e horário;
3. trecho em uma linha;
4. estado operacional e prazo/SLA;
5. responsável somente quando relevante.

Selecionada: fundo `primary-subtle`, indicador vertical de 3 px e contraste AA. Não usar avatar colorido como único indicador.

### 7.3 Thread

- Mensagem inbound fica à esquerda em superfície neutra; mensagem do operador à direita em `primary-subtle`.
- Cada bolha tem remetente acessível, horário e status de entrega.
- Leitura da Kiara não é bolha de conversa: usar bloco inline com borda/ícone, rotulado “Análise da Kiara”.
- O cabeçalho mostra nome, origem, estado de política, responsável e Dossiê; ações secundárias ficam em `DropdownMenu`.
- Nova mensagem não força auto-scroll se o operador estiver lendo histórico; exibir `2 novas mensagens ↓`.

### 7.4 Composer como máquina de estados

Mostrar somente a ação canônica do estado atual:

| Estado | Conteúdo | Ação primária |
|---|---|---|
| sem rascunho | intenção + lacunas | `Preparar resposta` |
| gerando | progresso/atividade e cancelar | `Cancelar` secundária |
| rascunho | editor, contagem, política | `Solicitar aprovação` |
| editado após aprovação | aviso “aprovação invalidada” | `Solicitar nova aprovação` |
| pendente | autor/horário e conteúdo bloqueado | nenhuma; `Cancelar solicitação` secundária |
| aprovado | prévia final e validade | `Revisar envio` |
| bloqueado/opt-out | motivo + remediação | nenhuma ação externa |
| enviando | estado idempotente | nenhuma duplicação |
| falhou/desconhecido | explicação e reconciliação | `Verificar status` antes de retry |

`Enviar pelo Instagram` só aparece na confirmação final e somente habilitado quando backend, aprovação, política, conta e kill switch forem revalidados.

### 7.5 Contexto

Topo: score grande + confiança + “calculado em”. Abaixo, quatro seções expansíveis: intenção, fatos, lacunas e política. “Próxima ação” fica em superfície de alta ênfase. `Registrar bloqueio` vai para menu de risco e abre `AlertDialog`; não deve ser um grande botão vermelho permanente.

### 7.6 Tablet e mobile por rota

- `/app/inbox`: somente lista.
- `/app/inbox/[conversationId]`: thread.
- `/app/inbox/[conversationId]?panel=context`: contexto em Sheet ou sub-rota acessível.
- O botão Voltar restaura `filter`, `q`, `cursor`, item selecionado e scroll.
- No mobile, composer fica sticky e o contexto abre por botão `Qualificação 82` no cabeçalho.
- Jamais renderizar a thread abaixo da lista, mesmo que CSS a esconda visualmente.

## 8. Hunter

Hunter deve parecer uma bancada de investigação, não uma vitrine de cards.

### Estrutura

1. Cabeçalho: escopo/fonte, consulta e ação `Nova pesquisa`.
2. Job bar real: fila, progresso, cancelar, resultados incrementais e custo/limite quando disponível.
3. Tabs semânticas: `Contatáveis`, `Sinais públicos`, `Bloqueados` com contagem.
4. Desktop: lista comparável à esquerda (42%) e inspector à direita (58%).
5. Mobile: lista e detalhe em rotas distintas.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ HUNTER  Pesquise sinais permitidos, com origem e explicação [Nova pesquisa] │
│ Job 18/32 fontes · 7 resultados · 00:18                  [Cancelar]          │
│ [Contatáveis 4] [Sinais públicos 2] [Bloqueados 1]                          │
├──────────────────────────────┬───────────────────────────────────────────────┤
│ [buscar] [origem] [recência] │ SINAL PÚBLICO                                │
│ Studio Norte   91 alta       │ Reforma anunciada publicamente               │
│ intenção + fonte + data      │ Origem verificada · 2 h                       │
│──────────────────────────────│ Evidência · confiança · lacunas               │
│ Casa Bela      78 média      │ Canal permitido: resposta pública apenas      │
│ ...                          │ Próxima ação recomendada                      │
│                              │ [Adicionar para revisão]                      │
└──────────────────────────────┴───────────────────────────────────────────────┘
```

Um resultado começa pelo tipo (`CONTATÁVEL`, `SINAL PÚBLICO`, `BLOQUEADO`), seguido de origem/data, intenção, confiança e motivo. Score sem fatores não pode ser a informação dominante. Botões usam verbos específicos: `Abrir conversa inbound`, `Adicionar para revisão`, `Ver motivo do bloqueio`; nunca `Abordar` de forma genérica.

## 9. Pipeline

### Toolbar

Título + contagem, busca, filtros persistentes, responsável/período e controle `Quadro | Lista`. Filtros ativos aparecem como chips removíveis e entram na URL.

### Quadro

- Colunas com largura fixa de 288–312 px e rolagem horizontal intencional.
- Cabeçalho de coluna sticky, contador e SLA agregado.
- Cards com nome, intenção, origem, confiança, próxima ação, prazo e responsável.
- Bordas de prioridade; sem faixas multicoloridas por estágio.
- Drag é atalho. Menu `Alterar etapa` é a operação canônica e funciona por teclado/touch.
- Estados terminais solicitam motivo em `Dialog`; ação destrutiva usa `AlertDialog`.

```text
┌ NOVO · 3 ─────────┐ ┌ QUALIFICAÇÃO · 4 ─┐ ┌ QUALIFICADO · 2 ─┐ →
│ Ana Costa         │ │ Marina Lima        │ │ Lucas Rocha      │
│ Consultoria · 82  │ │ Projeto · 74       │ │ Reforma · 91     │
│ Próx: orçamento   │ │ Próx: metragem     │ │ Próx: proposta   │
│ Hoje · Eduardo [⋯]│ │ Amanhã · Joana [⋯] │ │ 14:30 · Edu. [⋯] │
└───────────────────┘ └────────────────────┘ └──────────────────┘
```

### Lista

É a experiência padrão no mobile e alternativa de densidade no desktop. Cabeçalhos sticky, seleção por teclado, coluna de próxima ação antes de metadados menos importantes e ações por linha em `DropdownMenu`. Mudança persistida gera snackbar por 10 segundos com `Desfazer`, anunciada por live region.

## 10. Dossiê

O Dossiê organiza evidência para decisão. Não deve parecer relatório estático.

### Desktop

- Breadcrumb/voltar preserva a origem e os filtros.
- Header compacto com identidade, estágio, score/confiança, responsável, canal/política e atualização.
- Grid de 12 colunas: conteúdo principal 8; painel de decisão sticky 4.
- Tabs: `Resumo`, `Qualificação`, `Histórico`, `Kit comercial`.
- Evidências, hipóteses e lacunas usam padrões visualmente diferentes e sempre exibem fonte/data quando aplicável.
- Painel de decisão: próxima ação, lacunas críticas, prazo e CTA `Preparar próxima ação`.

```text
← Inbox / Ana Costa
┌─────────────────────────────────────────────────────────────────────────────┐
│ AC  Ana Costa     Qualificado · 82/100 alta      [Preparar próxima ação]   │
│ @anacosta · Instagram inbound · canal permitido · Eduardo · há 7 min       │
└─────────────────────────────────────────────────────────────────────────────┘
  [Resumo] [Qualificação] [Histórico] [Kit comercial]
┌─────────────────────────────────────────────┬───────────────────────────────┐
│ Resumo executivo                            │ PRÓXIMA AÇÃO                  │
│ ─────────────────────────────────────────── │ Confirmar faixa de orçamento │
│ Evidências verificadas  [3]                 │ Hoje · Eduardo                │
│ Hipóteses               [2]                 │ [Preparar próxima ação]       │
│ Lacunas e riscos         [2]                │                               │
│                                             │ Riscos / política             │
└─────────────────────────────────────────────┴───────────────────────────────┘
```

No mobile, metadados viram resumo expansível; tabs têm rolagem horizontal sem cortar rótulos; CTA fica numa barra inferior sticky. “Enviar” nunca é o CTA principal do Dossiê.

## 11. Integrações e Configurações

### Integrações

A conexão principal do Instagram ocupa uma única superfície rica, não dois cards equivalentes:

- identidade da conta e estado real;
- capacidades concedidas;
- webhook/última verificação;
- falha sanitizada e remediação;
- ações `Conectar`, `Reautorizar`, `Testar` e `Desconectar` conforme estado;
- `Testar` inclui rótulo “somente leitura; não envia DM”.

Integrações futuras aparecem apenas se há roadmap real; caso contrário, não criar cards “em breve” que diluam a prioridade.

### Configurações

- Desktop: subnav local de 232 px + formulário máximo de 720 px + resumo de impacto lateral opcional.
- Mobile: seletor de seção no topo e uma seção por rota.
- Seções: Operação, Qualificação, Atendimento, Equipe, Autonomia, Privacidade, IA, Aparência, Auditoria.
- Formulários possuem save bar sticky somente quando há mudanças, com `Descartar` e `Salvar alterações`.
- Salvar exibe `pending`, confirmação real ou erro por campo/região; nunca “salvo localmente” fora de demo.
- Alterações críticas mostram impacto e pedem confirmação.
- Aparência oferece três previews clicáveis: Claro, Escuro e Sistema; a seleção persiste por conta.

## 12. Command palette, busca e tema

### Command palette

Atalho `Ctrl+K`/`⌘K`, acionável também por botão com rótulo. Implementar com `Command + Dialog`.

Grupos:

- Navegar: Hoje, Inbox, Hunter, Pipeline, Integrações, Configurações;
- Encontrar: conversas e leads autorizados no workspace ativo;
- Ações seguras: nova pesquisa, abrir aprovações, conectar Instagram;
- Ajuda: atalhos, documentação e suporte.

Resultados mostram tipo, contexto e destino. A palette respeita permissão/tenant e nunca executa envio, exclusão, bloqueio ou mudança de etapa diretamente; abre a tela/preview apropriado. Escape fecha e devolve foco.

### Tema

- Opções: Claro, Escuro, Sistema.
- Primeiro acesso usa Sistema; escolha persiste por conta e pode usar fallback local antes da sincronização.
- Toggle compacto no menu de conta; controle completo em Configurações > Aparência.
- Evitar flash de tema antes da hidratação.
- Todos os estados e gráficos têm paridade nos dois temas.

## 13. Biblioteca de componentes de produto

Compor sobre shadcn/Radix; não criar `div` estilizada quando uma primitiva já resolve semântica e foco.

| Componente de produto | Primitivas | Responsabilidade |
|---|---|---|
| `KiaraAppShell` | `Sheet`, `DropdownMenu`, `Tooltip` | navegação, workspace, conta, mobile |
| `DemoRibbon` | `Alert` | honestidade persistente de fixtures |
| `GlobalCommand` | `Command`, `Dialog` | navegação e busca rápida |
| `ThemeSwitcher` | `DropdownMenu`/segmented buttons | Claro/Escuro/Sistema |
| `OperationalHero` | `Card`, `Button`, `Badge` | prioridade dominante da página |
| `HealthStrip` | `Badge`, `Tooltip`, `Separator` | saúde e atualização |
| `ConversationList` | `ScrollArea`, `Button`, `Badge` | triagem e seleção |
| `ConversationThread` | `ScrollArea`, `Separator` | histórico e novas mensagens |
| `ApprovalComposer` | `Textarea`, `Alert`, `Button`, `Dialog` | máquina de estados governada |
| `QualificationPanel` | `Progress`, `Accordion`, `Badge` | fatos, lacunas, confiança, policy |
| `HunterInspector` | `Tabs`, `ScrollArea`, `Sheet` | comparação e inspeção progressiva |
| `PipelineToolbar` | `Input`, `Select`, `Popover` | busca, filtros, view |
| `StageColumn` | `ScrollArea`, `Badge` | coluna estável de oportunidades |
| `LeadDecisionPanel` | `Card`, `Separator`, `Button` | próxima ação e risco |
| `IntegrationStatus` | `Card`, `Alert`, `Dialog` | conexão e saúde real |
| `StatePanel` | `Skeleton`, `Alert`, `Button` | loading/empty/error/permission |
| `UndoToast` | `Toast/Sonner` | desfazer com temporizador acessível |

Componentes adicionais a obter via shadcn apenas quando necessários: `command`, `scroll-area`, `popover`, `accordion`, `alert-dialog`, `breadcrumb`, `sonner` e `switch`.

## 14. Estados obrigatórios

### 14.1 Hierarquia de estados

1. **Global:** demo, offline/reconectando, sessão expirada, workspace trocado.
2. **Rota:** carregando, vazia, sem permissão, erro total.
3. **Painel:** erro parcial, dados desatualizados, paginação/job.
4. **Ação:** idle, pending, success confirmado, erro recuperável, estado desconhecido.

Um erro de painel não deve derrubar a rota inteira. Dados antigos podem permanecer com `Atualizado às…` e ação `Tentar novamente`.

### 14.2 Matriz visual

| Estado | Tratamento | Recuperação |
|---|---|---|
| carregando | skeleton da geometria conhecida | sem spinner solto em tela vazia |
| vazio inicial | ícone discreto + causa + um CTA | conectar, receber primeira DM ou pesquisar |
| vazio por filtro | preservar toolbar | `Limpar filtros` |
| erro parcial | Alert inline na região | retry sem perder seleção/edição |
| offline | faixa sticky abaixo do chrome | reconexão visível; bloquear ação externa |
| reconectando | atividade indeterminada + timestamp | não prometer sincronização |
| sessão expirada | Dialog que preserva trabalho seguro | reautenticar e retomar sem repetir |
| sem permissão | página 403 com workspace/papel | voltar ou solicitar acesso |
| opt-out/bloqueado | tratamento de perigo, motivo e data | revisão permitida; ação externa removida |
| estado desconhecido | warning persistente | reconciliar antes de retry |
| demo | ribbon global + badges locais úteis | nenhuma mutação real simulada como sucesso |

### 14.3 Microcopy

- Preferir “Ainda não enviado” a “Rascunho criado com sucesso”.
- Preferir “Aprovação registrada por Joana às 14:22” a “Aprovado”.
- Preferir “Não foi possível confirmar o envio” a “Erro 500”.
- Preferir “Sinal público — DM privada não permitida” a “Lead bloqueado”.
- Botões descrevem resultado: `Solicitar aprovação`, `Revisar envio`, `Alterar etapa`.

## 15. Acessibilidade e uso eficiente

- Um `h1` por rota, landmarks nomeados e skip link como primeiro foco.
- Foco visível de 2 px com offset em ambos os temas.
- Alvos mínimos de 44×44 px no touch; ações compactas no desktop mantêm área de clique adequada.
- Ordem de foco da Inbox: toolbar → lista → header da conversa → thread → composer → contexto.
- Painéis independentes têm nomes acessíveis e scroll sem prender teclado.
- Sheet/Dialog aprisiona foco, fecha com Escape e restaura o acionador.
- Mudanças de status usam `aria-live="polite"`; alertas críticos usam anúncio assertivo com parcimônia.
- Atalhos são documentados e nunca obrigatórios.
- Pipeline oferece `Alterar etapa`; drag não é requisito.
- Contraste mínimo WCAG 2.2 AA, incluindo texto sobre fundos translúcidos.
- Testar zoom 200%/400%, `prefers-reduced-motion`, forced colors e navegação por teclado.
- Mobile deve funcionar a 320 px sem overflow horizontal de página; apenas o quadro pode rolar horizontalmente por design.

## 16. Performance percebida

- Shell aparece antes dos dados de rota e não salta ao hidratar.
- Skeletons correspondem à forma final; não usar shimmer intenso.
- Filtros locais respondem em até 100 ms; busca remota sinaliza debounce e cancelamento.
- Preservar seleção, rascunho e scroll durante revalidação.
- Novos eventos entram sem roubar foco; botão de “novas atualizações” permite aplicar.
- Painéis longos usam virtualização apenas após medição; não introduzir complexidade prematura.

## 17. Breakpoints e critérios de reflow

| Largura | Shell | Inbox | Hunter | Pipeline | Dossiê |
|---:|---|---|---|---|---|
| 320–767 | top + bottom nav | rota lista/thread | rota lista/detalhe | lista | coluna + CTA sticky |
| 768–1023 | top + drawer | rota lista/thread | lista + Sheet | lista/board scroll | coluna + aside abaixo |
| 1024–1279 | rail 76 | lista + thread; Sheet contexto | split 40/60 | board scroll | 8/4 |
| 1280–1599 | sidebar 264 | 360/flex/340 | split 42/58 | board scroll | 8/4 |
| >=1600 | sidebar 264 | 380/flex/360 | split com max legível | colunas 304 | 8/4 com max 1440 |

## 18. Handoff de implementação

### Ordem

1. Corrigir tokens, fontes literais Geist no `@theme inline`, temas e providers.
2. Refatorar shell responsivo, demo ribbon, workspace/account e command palette.
3. Criar componentes compartilhados de estado, saúde e ação.
4. Implementar Dashboard “Hoje”.
5. Dividir Inbox em lista, thread, composer e contexto; criar rota de conversa mobile.
6. Refatorar Hunter em lista + inspector.
7. Corrigir Pipeline com colunas estáveis, lista e mudança de etapa acessível.
8. Reorganizar Dossiê, Integrações e Configurações.
9. Integrar DTOs reais sem permitir fixtures em produção.
10. Executar gates de React, lint, typecheck, build, browser, acessibilidade e acabamento.

### Fronteiras sugeridas

```text
src/components/app-shell/
  app-shell.tsx
  sidebar-nav.tsx
  mobile-nav.tsx
  utility-bar.tsx
  demo-ribbon.tsx
  global-command.tsx
  theme-switcher.tsx

src/components/dashboard/
  operational-hero.tsx
  health-strip.tsx
  priority-queue.tsx

src/components/inbox/
  inbox-layout.tsx
  conversation-list.tsx
  conversation-thread.tsx
  approval-composer.tsx
  qualification-panel.tsx

src/components/hunter/
  hunter-job-bar.tsx
  hunter-results-list.tsx
  hunter-inspector.tsx

src/components/pipeline/
  pipeline-toolbar.tsx
  stage-column.tsx
  opportunity-card.tsx
  change-stage-dialog.tsx

src/components/leads/
  lead-header.tsx
  lead-tabs.tsx
  lead-decision-panel.tsx

src/components/shared/
  state-panel.tsx
  policy-badge.tsx
  score-confidence.tsx
  source-reference.tsx
```

Extrair unidades sem transformar cada linha em componente. Responsabilidade e estado devem permanecer próximos da região que controlam.

## 19. Critérios de aceite visual e de usabilidade

1. Dashboard comunica a prioridade dominante antes de métricas e saudação.
2. Em desktop amplo, Inbox ocupa o viewport útil em três painéis com scroll independente.
3. Em mobile, selecionar conversa navega para uma rota; thread/contexto nunca aparecem empilhados sob a lista.
4. Cada estado do composer tem no máximo uma ação primária habilitada.
5. Hunter permite comparar resultados e inspecionar origem, confiança, permissão e próxima ação sem depender de cards isolados.
6. Pipeline usa colunas de largura estável, Lista equivalente e mudança de etapa sem drag.
7. Dossiê mantém próxima ação, política, risco e prazo visíveis.
8. Command palette abre por teclado e botão, respeita tenant/permissão e não executa ação externa diretamente.
9. Claro, Escuro e Sistema têm paridade e persistência, sem flash perceptível.
10. Loading, vazio, filtro vazio, erro parcial, offline, sessão expirada, sem permissão, opt-out e estado desconhecido possuem recuperação explícita.
11. Não há overflow horizontal da página em 320, 360, 768, 1024, 1280, 1440 e 1600 px; exceção intencional: área do Kanban.
12. Navegação, filtros, Inbox, aprovação, Pipeline e tema funcionam por teclado com foco visível.
13. Nenhuma fixture, ação local ou integração ausente é apresentada como dado/resultado real.
14. O acabamento usa uma cor de marca dominante, raios/densidade consistentes e no máximo uma superfície de alta ênfase por tela.

## 20. Gate de evidência

Antes de declarar o redesenho concluído:

- capturar Dashboard, Inbox, Hunter, Pipeline, Dossiê, Integrações e Configurações em claro e escuro;
- capturar Inbox lista e thread separadamente em 360×800;
- validar todos os viewports do critério 11;
- executar navegação completa por teclado e axe nas rotas críticas;
- testar `prefers-reduced-motion`, zoom 200%, forced colors e teclado virtual mobile;
- validar que o tema não pisca e que o Command devolve foco;
- revisar console sem erros e fluxo demo sem alegações de persistência/envio;
- submeter ao Accessibility Auditor e ao UI Finish Gate Reviewer.

## 21. Limites

- Este artefato não valida desejo do usuário; recomenda teste moderado com o cliente de lançamento depois do protótipo navegável.
- O blueprint não autoriza envio, scraping, DM fria, ações automáticas ou expansão multicanal.
- Acabamento visual não substitui backend real, Meta/Clerk/PostgreSQL em staging, segurança, observabilidade e isolamento multi-tenant.
- Nenhum código foi alterado por este trabalho; a execução deve preservar contratos de autenticação, governança e API existentes.
