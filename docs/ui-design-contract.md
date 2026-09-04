# Contrato de UI premium — Kiara Lead Intelligence

**Status:** contrato de implementação para a interface PySide6 atual. **Data:** 2026-09-04.  
**Escopo auditado:** `app/ui/theme.py`, `desktop.py`, `sdr_cockpit.py`, `consumer_cockpit.py`, `chat_widgets.py`, `dashboard_widgets.py`, `commercial_settings.py`, `panels.py`, `overlay.py` e testes de UI/acessibilidade existentes.

## 1. Direção visual e regra de verdade

A Kiara deve parecer um cockpit comercial premium, sóbrio e confiável: base grafite quase preta, superfícies azul-noite, acento principal cobalto e acento secundário violeta. Ciano, verde, âmbar e rosa são reservados a significado operacional. A interface não deve imitar um dashboard genérico nem preencher espaços com telemetria fictícia.

Todo texto, métrica, estado, fonte, etapa e recomendação exibidos deve vir do estado real. Um recurso indisponível apresenta causa e próxima ação; não simula disponibilidade. Ações externas continuam explicitando aprovação humana.

## 2. Diagnóstico vinculante do código atual

- A arquitetura principal já está organizada em três workspaces no `workspaceStack`: cockpit B2B, conversa/copiloto e inteligência B2C. O cockpit contém Visão geral, Pipeline e Resultados/Campanhas.
- A janela tem mínimo real de **900 × 680 px**. Este contrato não exige suporte abaixo desse tamanho enquanto o cockpit completo permanecer na mesma janela.
- A sidebar de 210 px aparece a partir de **1020 px**; o inspetor contextual de 310–380 px aparece somente no Copiloto a partir de **1180 px**. O B2C troca o splitter horizontal por vertical abaixo de **980 px**. Esses limites são preservados.
- O Kanban possui largura mínima de 1380 px dentro de área rolável; é um canvas horizontal deliberado, não um grid que deve ser comprimido.
- `theme.py` possui cerca de 733 linhas e sucessivas camadas QSS que redefinem os mesmos seletores. A implementação deve convergir para uma única camada canônica de tokens e componentes, mantendo os `objectName` existentes como contrato técnico.
- Acessibilidade já tem boa base: nomes acessíveis, atalhos `Alt+E`, `Alt+F` e `Esc`, histórico limitado, navegação por teclado em cards e contraste básico testado. O acabamento deve ampliar essa base, não substituí-la.
- Há controles críticos hoje ocultos (`Parar ações`, modo de voz) e símbolos textuais usados como ícones. A apresentação comercial só pode ocultar uma ação quando houver outro acesso inequívoco e documentado; o kill switch precisa permanecer descobrível.

## 3. Tokens canônicos

Os nomes abaixo são semânticos. Na implementação PySide, podem ser constantes Python que geram QSS e `QPalette`; não devem ser cores copiadas widget a widget.

| Token | Valor | Uso permitido |
|---|---:|---|
| `canvas` | `#070A12` | fundo da janela |
| `surface.base` | `#0A0F1C` | workspace principal |
| `surface.1` | `#0D1424` | sidebar e painéis |
| `surface.2` | `#10192B` | cards e campos |
| `surface.3` | `#142038` | item elevado/hover |
| `border.subtle` | `#263755` | divisores |
| `border.strong` | `#3B527D` | controle/seleção |
| `text.primary` | `#F7F9FF` | títulos e valores |
| `text.body` | `#D6DEED` | corpo |
| `text.secondary` | `#A9B5CE` | metadados |
| `text.muted` | `#8290A8` | ajuda não crítica |
| `accent.primary` | `#6E67F2` | ação primária/seleção |
| `accent.primaryHover` | `#8079FF` | hover primário |
| `accent.cobalt` | `#5B7CFA` | dados B2B e links |
| `accent.violet` | `#A78BFA` | IA/conversa |
| `state.info` | `#67E8F9` | informação/voz |
| `state.success` | `#43D697` | pronto/concluído |
| `state.warning` | `#F2B84B` | atenção/aguardando |
| `state.danger` | `#FB7185` | erro/interrupção |
| `focus.ring` | `#B8C5FF` | foco visível |

Gradiente é permitido apenas em ação primária, avatar/orbe e seleção principal: `#5B7CFA → #8B5CF6`. Cards de conteúdo usam cor sólida. Sombras não são requisito no Qt; profundidade vem de superfície + borda. Glow contínuo é proibido.

### Tipografia, espaço e forma

- Família: `Segoe UI Variable Text`, fallback `Segoe UI`; números e IDs podem usar `Cascadia Mono` quando disponível.
- Escala: 10 px eyebrow, 11 px metadado, 13 px corpo, 16 px título de card, 22 px título de página e 28–30 px título executivo. Corpo com altura visual equivalente a 1,4.
- Pesos: 400 corpo, 600 controles, 700 títulos, 800 somente números-chave/eyebrow.
- Espaçamento: base 4 px; escala **4, 8, 12, 16, 20, 24, 32**. Margens de página: 24 px amplo, 20 px intermediário, 16 px compacto.
- Raios: 8 px controles, 11 px cards internos, 15–16 px painéis/dossiês, pill apenas para badge/status.
- Alvos: mínimo 36 × 36 px; ações principais e navegação 42 px; rail 48 × 48 px; overlay 56–68 px.

## 4. Arquitetura responsiva compatível

| Faixa | Contrato |
|---|---|
| `900–979` compacto | sem sidebar e sem inspetor; B2C vertical; conteúdo crítico rola; cabeçalhos podem quebrar em duas linhas |
| `980–1019` intermediário | B2C horizontal; navegação ainda sem sidebar; Copiloto em coluna única |
| `1020–1179` desktop | sidebar 210 px visível; Copiloto sem inspetor; corpo recebe todo o restante |
| `>=1180` amplo | sidebar 210 px + Copiloto flexível + inspetor 310–380 px |

Regras invariantes:

- Não reduzir o mínimo da janela sem redesenhar e retestar tabelas, dossiês e ações.
- Nenhum botão crítico pode ser cortado, sobreposto ou depender de hover para ser descoberto.
- Tabelas preservam cabeçalho e seleção; quando não couberem, usam scroll ou splitter, nunca fonte menor que 11 px.
- O Kanban mantém colunas de no mínimo 210 px em scroll horizontal. Drag-and-drop também deve funcionar por teclado via ação alternativa de mudança de etapa.
- O diálogo comercial hoje exige 720 × 600 px; deve rolar verticalmente se o espaço útil do sistema for menor ou houver escala de 200%.

## 5. Contrato dos componentes

### Navegação

Sidebar é o padrão a partir de 1020 px. Cada item tem ícone consistente, rótulo e área mínima de 42 px. Estado ativo combina fundo violeta escuro, borda esquerda de 3 px e texto claro. Hover não altera geometria. Foco usa anel de 2 px e nunca é representado apenas pela mesma borda do ativo. Rail compacto continua permitido como variante futura, mas não pode usar `01`, `02`, `AI`, `B2C` sem tooltip e nome acessível.

### Cabeçalhos

Ordem: eyebrow opcional, título, descrição curta e ações à direita. Título não compete com métricas. Status real usa texto + ponto/ícone; “Online” só aparece quando o estado operacional justificar. Cabeçalhos não usam gradiente de fundo.

### Botões

- **Primário:** gradiente cobalto-violeta, texto branco, uma ação dominante por região.
- **Secundário:** `surface.2`, borda `border.strong`, texto primário.
- **Terciário:** transparente; somente para baixa ênfase.
- **Perigo:** fundo `#3A1C28`, borda `#98475E`, texto `#FFB1BD`; confirmação para efeito destrutivo.
- Ícone isolado só com `accessibleName`, tooltip e alvo mínimo. O botão Enviar circular pode manter ícone, pois seu nome acessível e atalho já existem.

Estados obrigatórios: default, hover, foco, pressed, disabled e busy. Busy desabilita reenvio sem alterar dimensões; o rótulo/estado anuncia progresso.

### Campos e filtros

Altura mínima 36 px, rótulo persistente em formulários, placeholder apenas como exemplo. Foco usa `focus.ring`; erro usa borda perigo + mensagem textual. Combos devem manter indicação visual de expansão. Valores inválidos não desaparecem ao perder foco.

### Cards e métricas

Card padrão: `surface.2`, borda sutil, raio 11–14 px, padding 12–16 px. Hover somente quando o card for interativo. Métrica contém rótulo, valor e contexto/período; cor do valor não é o único portador de significado. Cards tonais (cobalto, violeta, ciano, esmeralda e âmbar) são permitidos somente na visão geral e precisam manter contraste AA.

### Tabelas, Kanban e dossiê

Tabelas têm cabeçalho 11 px/700, linhas de pelo menos 40 px, seleção com fundo + borda e estado vazio separado da grade. Números alinham à direita; texto e estágio à esquerda. Dossiê apresenta badge de prontidão, evidências, riscos, próxima ação e proveniência em seções; recomendações não devem parecer fatos. No Kanban, card exibe empresa/pessoa, score, próxima ação e etapa; hover não substitui seleção.

### Conversa

Histórico preserva seleção de texto, rolagem e limite de 500 cards. Usuário alinha à direita em superfície cobalto; Kiara à esquerda em superfície neutra com assinatura violeta; aviso/sistema usa card compacto sem avatar humano. Autor e horário continuam acessíveis. O composer permanece estável durante streaming. Como o campo atual é `QLineEdit`, Enter envia; não exibir instrução de `Shift+Enter`.

O estado deve distinguir: pronta, pensando, gerando, ouvindo, transcrevendo, falando, erro recuperável e interrompida. “Parar ações” deve estar visível durante qualquer execução/escuta e disponível por `Esc`; fora desses estados pode recolher, mas precisa existir em menu/área de segurança claramente identificada.

### Estados vazios, loading e erro

Cada lista/painel suporta: carregando, vazio, preenchido, indisponível e erro. Estado vazio inclui título, explicação honesta e ação útil quando existente. Loading usa skeleton discreto ou texto; animação não pode simular progresso determinístico. Erro preserva os dados já carregados e oferece tentar novamente quando seguro.

### Overlay e voz

Overlay é opt-in e representa a mesma Kiara. Deve anunciar “Kiara — {estado}”, abrir/restaurar a janela, permitir ocultar e manter parada de emergência. Cores de voz refletem eventos reais; visibilidade nunca significa captura ativa. Pulso/rotação é pausável e não excede uma animação simultânea. Botões rápidos atuais de 34 px devem crescer para 44 px se forem essenciais ao toque.

## 6. Acessibilidade e internacionalização

- Alvo: WCAG 2.2 AA — texto normal ≥ 4,5:1; texto grande, bordas de foco e componentes ≥ 3:1.
- Foco visível de 2 px em todos os controles. A ordem segue navegação → cabeçalho → conteúdo → ação principal; painéis ocultos não recebem foco.
- Cor sempre acompanha texto, ícone, padrão ou posição. Scores e riscos possuem rótulo explícito.
- Teclado: `Alt+E` enviar, `Alt+F` falar e `Esc` parar permanecem; cards clicáveis respondem a Enter/Espaço; mudança de etapa possui alternativa ao drag.
- Texto suporta Windows em 125%, 150% e 200% sem corte. Evitar `setFixedHeight` em campos com labels; preferir mínimo + layout/scroll.
- Animações respeitam configuração de movimento reduzido da aplicação; duração recomendada 120–180 ms.
- Textos ficam em português do Brasil consistente, UTF-8, com pontuação e acentos corretos. Símbolos quebrados por encoding são defeito bloqueante de acabamento.

## 7. Critérios de aceite e gate visual

1. `theme.py` expõe uma camada canônica; seletores legados conflitantes são removidos ou marcados para depreciação, sem mudar `objectName` usados pelos testes.
2. Screenshots em **900×680**, **1020×720**, **1180×760** e **1440×900**, mais DPI **150% e 200%**, não apresentam corte ou sobreposição.
3. Sidebar e inspetor obedecem exatamente aos breakpoints; B2C alterna splitter em 980 px sem perda de seleção/ação.
4. Estados default, hover, foco, pressed, disabled, busy, vazio e erro são evidenciados nos componentes aplicáveis.
5. Todos os controles por ícone têm tooltip/nome acessível; todo fluxo crítico funciona sem mouse.
6. Contrastes dos pares usados são medidos, não inferidos visualmente, e atendem AA.
7. Nenhuma fonte, integração, contagem, status ou recomendação fictícia aparece na evidência comercial.
8. “Parar ações” fica visível durante processamento/voz e funciona por clique e `Esc`.
9. A suíte funcional existente passa; testes visuais acrescentam asserts de breakpoint, foco, dimensões mínimas e estados.
10. O gate final compara implementação contra este contrato e registra divergências justificadas em `evidence/`; “parece premium” sem evidência não aprova release.

## 8. Ordem recomendada de implementação

1. Consolidar tokens/QPalette e eliminar cascata conflitante do QSS.
2. Normalizar estados de botões, campos, foco, tabelas e cards.
3. Corrigir visibilidade da parada, status operacional e símbolos/ícones inconsistentes.
4. Validar os quatro breakpoints, DPI e diálogo comercial.
5. Capturar evidências de teclado, contraste, estados vazios/erro e fluxo B2B/B2C/Copiloto.

Este contrato substitui escolhas cromáticas divergentes em documentos visuais anteriores, mas preserva seus princípios funcionais: dados reais, segurança explícita, acessibilidade e ausência de controles decorativos.
