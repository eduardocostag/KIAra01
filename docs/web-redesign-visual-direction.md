# Direção visual premium — Kiara Web

**Status:** contrato visual implementável para a onda de redesign; nenhum código de interface foi alterado nesta etapa.  
**Data:** 2026-09-05  
**Especialista:** UI Designer  
**Escopo auditado:** `apps/web/src/app`, `apps/web/src/components`, `apps/web/src/lib/mock-data.ts`, `docs/web-ui-contract.md`, `docs/web-ux-architecture.md`, `evidence/web-home.png`, `evidence/web-inbox-mobile.png` e a referência desktop `evidence/ui-redesign-windows.png`.

## 1. Diagnóstico executivo

A Kiara já tem uma estrutura funcional, segura e razoavelmente consistente, mas sua apresentação ainda se aproxima de um dashboard shadcn genérico. O produto usa a mesma combinação recorrente de `Sparkles`, cards brancos, violeta/cobalto, badges e gradientes de muitos SaaS de IA. A interface comunica capacidade, mas ainda não produz reconhecimento de marca nem transforma sua diferença real — **converter uma conversa inbound em uma próxima ação governada** — em linguagem visual.

O problema mais visível nas duas capturas é tipográfico: `globals.css` declara `--font-sans: var(--font-sans)` dentro de `@theme inline`, uma referência circular. O resultado observado é fallback serifado em títulos, corpo, botões e listas, apesar de `Geist` estar configurada no layout. Isso prejudica legibilidade, acabamento e consistência. A captura pública também contém caixas vermelhas numeradas de auditoria; ela é útil para estrutura, mas não serve como evidência final de acabamento.

Outros achados:

- a faixa amarela de demonstração domina o primeiro impacto e, no mobile, consome duas linhas antes da navegação;
- o glifo `Sparkles` e o wordmark com tracking amplo não são distintivos;
- o app mistura cobalto, violeta, cyan, verde, âmbar, rosa e o gradiente do Instagram sem uma hierarquia semântica firme;
- cards, bordas e raios funcionam, porém quase todas as informações têm peso de superfície semelhante;
- a Inbox possui boa divisão funcional, mas a seleção, a leitura da Kiara, o gate humano e a próxima ação ainda não formam uma narrativa visual contínua;
- dashboard, Hunter e Pipeline repetem o padrão ícone-em-quadrado + card + badge, reduzindo reconhecimento entre tarefas;
- há bom fundamento de acessibilidade no código, mas contraste em transparências, foco, zoom e tecnologia assistiva continuam pendentes conforme a auditoria existente.

## 2. Ideia central: Kiara Signal

**Promessa visual:** _da mensagem ao próximo passo, sem perder o controle_.

A identidade deve representar uma cadeia curta e confiável:

`conversa → leitura → decisão → ação aprovada`

O dispositivo proprietário é a **Trilha Kiara**: uma linha fina que liga nós de evento. Um nó aberto representa informação recebida; um losango representa interpretação; um nó com halo representa decisão humana; uma seta curta representa a próxima ação. A trilha aparece em pontos de alta relevância — hero, timeline, leitura assistida, aprovação e pipeline — nunca como decoração em todas as superfícies.

### Glifo K Signal

Substituir `Sparkles` como marca principal por um SVG próprio de 32 × 32:

- haste vertical de `(9, 7)` a `(9, 25)`;
- nó central em `(9, 16)`;
- dois ramos partindo do nó central até `(23, 7)` e `(23, 25)`;
- terminais circulares de 3 px; traço de 1,75 px, pontas arredondadas;
- o desenho forma um **K** e simultaneamente uma bifurcação decisão/ação;
- caixa padrão de 36 × 36, raio 11 px, fundo `--brand-solid`, foreground `--brand-on-solid`;
- versão monocromática para favicon e impressão; não usar gradiente dentro do símbolo.

`Sparkles` permanece apenas como ícone semântico de um evento gerado/analisado pela Kiara. Não deve ser logotipo.

### Personalidade

- **Precisa:** números e estados são inequívocos.
- **Humana:** conversas têm respiro; aprovação é visível e tranquilizadora.
- **Atenta:** prioridades são percebidas rápido, sem alarmismo.
- **Premium:** contraste, ritmo e detalhe substituem excesso de efeitos.
- **Governada:** “preparado”, “aprovado” e “enviado” nunca parecem o mesmo estado.

## 3. Sistema cromático em OKLCH

Os valores abaixo são o baseline canônico. Antes de release, todas as combinações reais — especialmente transparências — devem ser verificadas por contraste calculado; os valores não substituem o gate WCAG.

### Tema claro — Porcelana

```css
:root {
  --background: oklch(0.982 0.006 270);
  --foreground: oklch(0.205 0.028 267);
  --surface-1: oklch(1 0 0);
  --surface-2: oklch(0.965 0.011 270);
  --surface-3: oklch(0.938 0.018 270);
  --card: var(--surface-1);
  --card-foreground: var(--foreground);
  --popover: oklch(1 0 0);
  --popover-foreground: var(--foreground);

  --primary: oklch(0.49 0.225 274);
  --primary-hover: oklch(0.445 0.215 274);
  --primary-foreground: oklch(0.99 0.003 270);
  --brand-solid: var(--primary);
  --brand-on-solid: var(--primary-foreground);
  --brand-subtle: oklch(0.945 0.04 276);
  --brand-subtle-foreground: oklch(0.36 0.16 274);
  --signal-cyan: oklch(0.68 0.125 211);
  --signal-lilac: oklch(0.71 0.145 302);

  --secondary: oklch(0.948 0.012 269);
  --secondary-foreground: oklch(0.28 0.03 267);
  --muted: oklch(0.955 0.01 270);
  --muted-foreground: oklch(0.455 0.034 267);
  --accent: var(--brand-subtle);
  --accent-foreground: var(--brand-subtle-foreground);
  --border: oklch(0.89 0.019 270);
  --input: oklch(0.875 0.022 270);
  --ring: oklch(0.55 0.20 274);

  --success: oklch(0.46 0.125 158);
  --success-subtle: oklch(0.95 0.045 158);
  --warning: oklch(0.53 0.14 78);
  --warning-subtle: oklch(0.955 0.047 84);
  --destructive: oklch(0.51 0.205 27);
  --destructive-subtle: oklch(0.955 0.04 27);
  --info: oklch(0.49 0.15 244);
  --info-subtle: oklch(0.95 0.035 244);
}
```

### Tema escuro — Noite Índigo

```css
.dark {
  --background: oklch(0.125 0.022 267);
  --foreground: oklch(0.965 0.008 270);
  --surface-1: oklch(0.16 0.026 267);
  --surface-2: oklch(0.19 0.03 267);
  --surface-3: oklch(0.225 0.034 267);
  --card: var(--surface-1);
  --card-foreground: var(--foreground);
  --popover: oklch(0.19 0.03 267);
  --popover-foreground: var(--foreground);

  --primary: oklch(0.72 0.17 273);
  --primary-hover: oklch(0.77 0.15 273);
  --primary-foreground: oklch(0.145 0.03 267);
  --brand-solid: var(--primary);
  --brand-on-solid: var(--primary-foreground);
  --brand-subtle: oklch(0.245 0.07 274);
  --brand-subtle-foreground: oklch(0.82 0.105 277);
  --signal-cyan: oklch(0.76 0.125 211);
  --signal-lilac: oklch(0.78 0.13 302);

  --secondary: oklch(0.205 0.028 267);
  --secondary-foreground: oklch(0.94 0.01 270);
  --muted: oklch(0.205 0.025 267);
  --muted-foreground: oklch(0.72 0.026 270);
  --accent: var(--brand-subtle);
  --accent-foreground: var(--brand-subtle-foreground);
  --border: oklch(1 0 0 / 0.115);
  --input: oklch(1 0 0 / 0.16);
  --ring: oklch(0.72 0.17 273);

  --success: oklch(0.74 0.14 158);
  --success-subtle: oklch(0.24 0.055 158);
  --warning: oklch(0.79 0.14 84);
  --warning-subtle: oklch(0.255 0.052 78);
  --destructive: oklch(0.72 0.18 27);
  --destructive-subtle: oklch(0.25 0.06 27);
  --info: oklch(0.74 0.12 244);
  --info-subtle: oklch(0.24 0.05 244);
}
```

### Regras de uso

1. Índigo é marca, seleção, inteligência e ação primária — não um status genérico.
2. Ciano representa pulso/canal/evento novo; não é segunda cor de CTA.
3. Verde significa apenas condição confirmada ou permitida.
4. Âmbar significa revisão, espera ou atenção; não deve parecer erro.
5. Vermelho significa bloqueio, falha ou ação destrutiva.
6. “Instagram” usa ícone monocromático com label; o gradiente fúcsia/laranja só pode aparecer no detalhe da integração, nunca como paleta da Kiara.
7. Estado sempre combina cor + ícone + texto.

## 4. Superfícies, bordas e elevação

### Hierarquia de superfície

- **Canvas:** `background`; nunca recebe sombra.
- **Panel:** `surface-1`, borda de 1 px; Inbox, formulários e tabelas.
- **Raised:** `surface-2`; menus, composer e área selecionada.
- **Spotlight:** `brand-subtle`; somente leitura da Kiara, onboarding ativo e decisão selecionada.
- **Overlay:** `popover`; sombra forte e scrim, somente drawers/dialogs.

Evitar cards aninhados. Dentro de um grande painel operacional, usar seções, dividers e mudança sutil de superfície. Dashboard pode usar cards; Inbox não deve parecer uma coleção de cards.

```css
:root {
  --radius-control: 0.625rem; /* 10 px */
  --radius-card: 0.875rem;    /* 14 px */
  --radius-panel: 1.125rem;   /* 18 px */
  --shadow-1: 0 1px 2px oklch(0.16 0.03 267 / 0.06);
  --shadow-2: 0 10px 28px oklch(0.16 0.03 267 / 0.10);
  --shadow-3: 0 28px 80px oklch(0.10 0.03 267 / 0.22);
}
```

No dark mode, borda/luminosidade fazem a separação; reduzir a opacidade das sombras em 30%. Não usar glassmorphism em cards. `backdrop-blur` fica restrito ao header sticky e overlays.

### Signal edge

Componente proprietário para seleção e inteligência:

- borda esquerda interna de 3 px `primary`;
- nó de 6 px em `signal-cyan` alinhado ao título;
- fundo `brand-subtle` com no máximo 70% de opacidade;
- em dark, halo `0 0 0 1px primary/18`, sem glow externo forte.

Usar em conversa selecionada, Insight Kiara e etapa atual. Não usar em todos os cards.

## 5. Tipografia Geist

Usar Geist Sans em toda a interface; Geist Mono somente para score, métrica, horário, ID, atalhos e valores tabulares. A landing também usa Geist, sem fonte serifada adicional. Isso preserva uma família única e torna a marca reconhecível pelo ritmo e não por mistura tipográfica.

Correção obrigatória em Tailwind v4:

```css
@theme inline {
  --font-sans: "Geist", "Geist Fallback", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "Geist Mono", "Geist Mono Fallback", ui-monospace, monospace;
  --font-heading: "Geist", "Geist Fallback", ui-sans-serif, system-ui, sans-serif;
}
```

Manter as classes variáveis de `next/font` em `<html>`. Não usar `var(--font-sans)` como valor de `--font-sans` dentro de `@theme inline`.

| Papel | Tamanho/linha | Peso | Tracking | Uso |
|---|---:|---:|---:|---|
| Hero XL | `clamp(3.25rem, 6vw, 5.75rem)` / `0.94` | 600 | `-0.058em` | landing, uma vez |
| Display | 48/52 | 600 | `-0.045em` | CTA editorial |
| Page title | 30/36 | 600 | `-0.035em` | páginas do app |
| Section | 18/26 | 600 | `-0.018em` | título de região |
| UI body | 14/22 | 400 | `-0.006em` | app |
| Marketing body | 18/30 | 400 | `-0.012em` | landing |
| Label | 13/18 | 550 | `0` | controles |
| Overline | 11/16 | 650 | `0.14em` | poucos agrupamentos |
| Data mono | 12/18 ou 28/32 | 500–600 | `-0.02em` | tempo, score, métricas |

Não usar uppercase em navegação. Overline uppercase fica limitado ao eyebrow da página e aos rótulos de trilha. Texto secundário não pode ficar abaixo do contraste AA.

## 6. Espaçamento, densidade e layout

Escala: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96` px.

- app operacional: densidade **compacta calma** (`gap-4`, painéis `p-4/5`, regiões `gap-6`);
- marketing: densidade **editorial** (`gap-8/12`, seções `py-20/28`);
- controles desktop: 36 ou 40 px; controles primários 44 px;
- em viewport touch, todos os alvos interativos têm pelo menos 44 × 44 px;
- sidebar expandida: 248 px; rail: 72 px entre 1024–1279 px;
- conteúdo geral: máximo 1600 px; Inbox/Pipeline podem ocupar tudo;
- texto/formulário: máximo 720 px;
- Inbox ampla: `320px minmax(480px, 1fr) 360px`;
- nenhuma seção crítica deve depender de hover ou drag.

## 7. Iconografia e ilustração

- Lucide com `strokeWidth={1.75}`; 16 px em controles, 18 px em navegação, 20 px em cabeçalhos.
- Um ícone por ação; ícones decorativos recebem `aria-hidden`.
- Ícone não fica automaticamente dentro de quadrado colorido. O contêiner é reservado a integrações, avatar de entidade e marcos de jornada.
- Não usar emoji como ícone de produto.
- Sem banco de imagens e sem pessoas sintéticas no lançamento. O produto real é a prova visual.
- Padrão ambiente proprietário da landing: grade de pontos de 24 px, 1 px, `primary` a 8% de opacidade, mascarada radialmente atrás da prévia. Não repetir no app.

## 8. Motion e microinterações

```css
--motion-instant: 90ms;
--motion-fast: 140ms;
--motion-standard: 180ms;
--motion-panel: 240ms;
--ease-out: cubic-bezier(0.22, 1, 0.36, 1);
--ease-standard: cubic-bezier(0.2, 0, 0, 1);
```

- hover operacional: mudança de fundo/borda, sem elevar cada linha;
- cards de marketing podem subir no máximo 1 px;
- seleção: `140ms` para background + signal edge;
- drawer/dialog: `240ms`, opacity + translate máximo 12 px;
- aprovação confirmada: halo único de 320 ms; nunca pulsação infinita;
- novas DMs: nó ciano estático; animação somente na chegada e por uma repetição;
- skeleton reproduz a geometria real e não deve simular progresso;
- respeitar `prefers-reduced-motion`; nenhuma informação depende de animação.

## 9. Componentes proprietários sobre shadcn/Radix

| Componente | Receita visual | Comportamento |
|---|---|---|
| `KiaraBrand` | K Signal + wordmark Geist 650, tracking `0.08em`; subtítulo sem divisor vertical | compacto no rail; wordmark completo no sidebar/landing |
| `SignalTrail` | linha 1 px + nós abertos/losango/halo | timeline da conversa, qualificação, aprovação e envio |
| `IntelligencePanel` | signal edge, `brand-subtle`, título com K Signal pequeno | separa fatos, inferências e lacunas; nunca parece mensagem humana |
| `GovernanceGate` | faixa horizontal com escudo, estado e ator/tempo | deixa claro “não enviado”, “aguardando”, “aprovado”, “bloqueado” |
| `NextAction` | título + motivo + prazo mono + owner; CTA secundário | unidade central do dashboard e do lead |
| `StatusBadge` | ícone 12 px + texto, tint semântico | variantes `new`, `review`, `approved`, `blocked`, `unknown` |
| `ScoreSignal` | número mono + confiança + barra segmentada | evita velocímetro decorativo; explica fatores em popover/sheet |
| `ConversationRow` | sem card, divider, avatar discreto, preview e sinal de prioridade | seleção por signal edge; unread não depende só de ponto |
| `Composer` | raised surface, label de estado acima, ações à direita | preparar, editar, aprovar e enviar são estados visivelmente diferentes |
| `CommandSearch` | shadcn `Command` em `Dialog`, atalho `⌘/Ctrl K` | busca global por lead/conversa, não placeholder inerte |

### Botões

- uma única ação `default` por região;
- `default`: índigo sólido, sem gradiente;
- `secondary`: surface-3, borda sutil;
- `outline`: ações neutras e reversíveis;
- `ghost`: navegação/ações de baixa ênfase;
- `destructive`: somente para bloquear, revogar ou desconectar;
- ação proibida não deve ser apenas disabled: apresentar motivo adjacente ou tooltip acessível.

### Cards

Usar `Card` apenas quando a unidade precisa ser percebida como objeto independente. KPI, oportunidade e integração são cards; lista de conversa, fatos e etapas internas são seções. Remover o padrão automático de ícone dentro de bloco colorido de todas as instâncias que não representam uma entidade.

## 10. Landing — composição alvo

### Header

- 72 px, fundo Noite Índigo; K Signal, “KIARA” e “Lead Intelligence” em uma linha sem divisor;
- links “Como funciona”, “Controle humano” e “Segurança” a partir de desktop;
- `Entrar` como ghost; `Começar` como primary;
- demo não usa faixa amarela de 48 px: usar barra semântica de 32 px em `warning-subtle`, com ícone, “Demo segura” e link “O que está desativado”. Em mobile, uma linha truncável com detalhe em dialog/sheet acessível.

### Hero

- eyebrow: `INSTAGRAM INBOUND → QUALIFICAÇÃO → PIPELINE`;
- headline recomendado: **“Transforme cada DM em uma próxima ação.”**;
- subcopy: “A Kiara lê o contexto, mostra o que falta e prepara a resposta. Você revisa antes de qualquer envio.”;
- CTA primário “Criar workspace”; secundário “Ver fluxo em 90 segundos” somente se houver demonstração real, caso contrário “Conhecer o fluxo”;
- preview do produto ocupa 52–55% no desktop e mostra uma Trilha Kiara completa: DM → Insight → Revisão → Próxima ação;
- somente dois efeitos de marca: campo radial/grade atrás da preview e halo discreto do CTA. Nenhum gradiente em texto.

### Corpo

1. faixa de confiança com três fatos verificáveis: “Sem instalação”, “Aprovação humana”, “Canal oficial”;  
2. seção “Da mensagem à decisão” com trilha horizontal em desktop e vertical no mobile;  
3. prova de produto com três recortes reais: Inbox, contexto e Pipeline;  
4. seção “Automação com limites claros”, destacando `Preparado ≠ Aprovado ≠ Enviado`;  
5. CTA final em superfície sólida, sem depoimentos ou métricas inventadas.

### Meta acima da dobra

Em 1440 × 900, exibir header, headline completa, subcopy, dois CTAs e pelo menos 75% da prévia. Em 390 × 844, exibir headline, subcopy e CTA principal antes de 720 px; a prévia entra logo após, sem overflow horizontal.

## 11. App autenticado — composição alvo

### Shell

- sidebar Noite Índigo no dark e Porcelana contrastada no light; K Signal no topo;
- item ativo: signal edge + fundo sutil, não botão índigo cheio;
- header de 56 px com Command Search, workspace, saúde do Instagram, atividade e conta;
- seletor de tema no menu de conta; padrão `system`;
- mobile: topbar de 52 px e navegação inferior opcional para Visão geral, Inbox e Pipeline; Hunter/Integrações no menu;
- a indicação Demo permanece visível, porém não rouba duas linhas do viewport.

### Page header

- eyebrow opcional, `h1` e descrição em bloco; badge “Dados demonstrativos” move para a barra global de demo e deixa de se repetir em todas as páginas;
- ação primária alinhada ao título em desktop e full-width somente quando apropriado no mobile;
- altura alvo 92–116 px, reduzindo o atraso até o primeiro conteúdo operacional.

### Dashboard

Ordem: **Atenção agora → Próximas ações → Saúde → Métricas → Funil**. O estado da integração não deve preceder toda tarefa quando estiver saudável. KPIs usam número mono, microdescrição e tendência somente quando houver dado real. “Próximas ações” vira a superfície dominante e usa `NextAction`, não linhas genéricas de card.

### Inbox

- lista, conversa e contexto são três zonas contínuas com dividers;
- conversa selecionada usa signal edge e label textual “Nova”/“Revisão”, não apenas ponto;
- mensagens do cliente: `surface-2`; mensagens do operador: `brand-subtle`; insight da Kiara: `IntelligencePanel` com K Signal — visualmente impossível confundir os três;
- composer permanece sticky no fundo da zona central;
- `GovernanceGate` fica imediatamente acima das ações e mostra o próximo requisito;
- contexto agrupa “Confirmado”, “Inferido”, “Falta saber” e “Política”; bullets soltos viram seções com fonte/data quando disponíveis;
- score nunca é a maior informação do painel; próxima ação e lacuna têm maior prioridade;
- desktop mantém as três zonas; tablet transforma contexto em Sheet; mobile usa rotas/lista → conversa e Sheet de contexto.

### Hunter

Separar resultados em três tabs reais: **Contatáveis**, **Sinais públicos**, **Bloqueados**. Cada tipo recebe estrutura própria, não apenas badge diferente no mesmo card. “Sinal público” nunca exibe CTA visualmente equivalente a uma abordagem privada. Score, fonte, recência e motivo ficam escaneáveis em linhas; cards de 3 colunas são reservados à visão de exploração, com lista como padrão para maior volume.

### Pipeline

- colunas com header sticky e superfície quase plana;
- cards priorizam próxima ação e prazo; nome/estágio não competem com o trabalho a fazer;
- faixa de estágio usa o tom semântico, não arco-íris por coluna;
- view Lista usa o componente `Table`, densidade compacta e primeira coluna sticky quando necessário;
- mudar estágio oferece comando acessível e undo; drag é atalho opcional.

### Dossiê, integrações e configurações

- Dossiê: summary rail com SignalTrail, evidências com fonte/data, CTA “Preparar próxima ação”;  
- Integrações: marca do provedor é detalhe, enquanto saúde/permissões dominam; gradiente Instagram não colore o card inteiro;  
- Configurações: tabs/subnav lateral + formulário máximo 720 px + save bar sticky quando houver alterações; estados críticos mostram impacto antes de salvar.

## 12. Light, dark e acessibilidade

- landing é Noite Índigo por assinatura; app respeita `system` e oferece Claro/Escuro/Sistema;
- paridade funcional e semântica total entre temas;
- foco visível de 2 px + offset 2 px; em fundo primary, foco usa `primary-foreground`;
- contraste mínimo: 4,5:1 para texto normal, 3:1 para texto grande e componentes gráficos essenciais;
- touch targets de 44 px no mobile; zoom 200% e text scaling não podem cortar ações;
- `forced-colors`: signal edge, badges e selected row recebem borda explícita; não depender de background tint;
- tooltips nunca são a única fonte de instrução;
- banners usam `role=status` apenas para informação não urgente; falhas críticas usam `role=alert` com parcimônia;
- manter skip links, landmarks, `aria-current`, `aria-pressed`, `aria-live` e `prefers-reduced-motion` já previstos;
- gate final exige axe, teclado completo, NVDA + Chrome, zoom 200/400%, light/dark e 360/768/1024/1440 px.

## 13. Mapeamento implementável

| Arquivo/área | Mudança principal |
|---|---|
| `src/app/globals.css` | corrigir fonte circular; aplicar tokens, superfícies, motion e utilities Signal |
| `src/app/layout.tsx` | preservar variáveis Geist em `<html>`; integrar tema `system` sem flash |
| `src/components/auth-provider.tsx` | redesenhar demo bar responsiva e acessível |
| `src/components/marketing/landing-page.tsx` | K Signal, hero, preview em trilha, hierarquia e seções de governança |
| `src/components/app-shell/app-shell.tsx` | sidebar/rail, Command Search, saúde e mobile nav |
| `src/components/app-shell/page-header.tsx` | remover badge demo repetido, compactar altura e ações |
| `src/components/app-shell/inbox-workspace.tsx` | três zonas, IntelligencePanel, GovernanceGate e composer sticky |
| `src/components/app-shell/hunter-results.tsx` | tabs por permissão/tipo e hierarquia por ação permitida |
| `src/components/app-shell/pipeline-board.tsx` | próxima ação dominante, Table shadcn e cabeçalhos sticky |
| `src/components/ui/*` | variantes semânticas e foco; evitar wrappers ad hoc |

Novos componentes recomendados: `kiara-brand.tsx`, `signal-trail.tsx`, `intelligence-panel.tsx`, `governance-gate.tsx`, `next-action.tsx`, `status-badge.tsx`, `score-signal.tsx` e `demo-banner.tsx`.

## 14. Alvos before/after

| Dimensão | Agora | Alvo verificável |
|---|---|---|
| Tipografia | fallback serif observado por variável circular | Geist Sans computada em landing e app; Mono somente em dados |
| Marca | `Sparkles` + wordmark genérico | K Signal próprio em favicon, landing e shell |
| Cor | múltiplos acentos competindo | índigo para marca/IA, ciano para evento e cores semânticas exclusivas |
| Demo | faixa amarela domina e quebra em duas linhas | uma linha de 32 px desktop; variante mobile compacta com detalhe acessível |
| Navegação | item ativo é botão primary cheio | signal edge + surface tint; leitura mais calma |
| Cards | mesmo padrão em quase todas as telas | cards só para objetos; painéis operacionais por zonas/dividers |
| Inbox | IA, mensagem e aprovação pouco encadeadas | Trilha Kiara e três superfícies inequivocamente distintas |
| Dashboard | integração e KPIs antes do trabalho | próxima ação e prioridade na primeira região útil |
| Mobile Inbox | conteúdo operacional começa em ~278 px na evidência | primeira lista/ação útil começa até 220 px em 390 × 844 |
| Acima da dobra | hero forte, mas fonte errada e preview parcial | conteúdo completo + 75% da preview em 1440 × 900 |
| Motion | transições dispersas | quatro durações, sem loop decorativo, reduced motion completo |
| Acessibilidade | revisão parcial por código/captura | axe + teclado + NVDA + zoom + forced colors aprovados |
| Originalidade | aparência shadcn/AI familiar | K Signal, SignalTrail, GovernanceGate e IntelligencePanel reconhecíveis |

## 15. Critério de aceite visual

O redesign passa apenas quando:

1. fonte computada confirma Geist e não há fallback serifado;  
2. a marca pode ser reconhecida sem ler “Kiara”;  
3. mensagem humana, leitura da IA, aprovação e envio não podem ser confundidos;  
4. existe no máximo uma ação primária por região;  
5. light/dark preservam hierarquia e contraste;  
6. screenshots limpas, sem overlays de auditoria, cobrem landing desktop/mobile e todas as telas principais;  
7. UI Finish Gate, Accessibility Auditor e Evidence Collector validam a implementação;  
8. nenhum claim, métrica ou estado visual sugere integração real onde há somente demo.

## 16. Decisões de não alterar

- Não foi gerado logo bitmap: o K Signal deve ser SVG/CSS nativo, leve e escalável.
- Não foi adotada uma segunda família display: Geist é suficiente e a falha atual é de configuração, não falta de personalidade.
- Não foi escolhido o gradiente do Instagram como identidade: o canal é uma integração; a Kiara precisa de marca independente.
- Não foram alterados componentes ou páginas nesta onda, conforme o escopo de direção visual.
- Nenhuma validação com usuários ou conformidade WCAG completa é alegada a partir da revisão visual.
