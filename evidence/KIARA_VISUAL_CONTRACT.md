# Contrato visual e UX — Kiara Desktop

Status: especificação verificável para implementação em PySide6/Qt. A referência visual é a imagem fornecida pelo usuário; o comportamento funcional existente é a fonte de verdade. Este contrato não autoriza controles decorativos sem ação real.

## 1. Princípios e hierarquia

1. A janela principal deve comunicar, nesta ordem: identidade/estado da Kiara, navegação, conversa ou painel ativo, entrada/ação primária e privacidade/estado operacional.
2. Os seis painéis existentes devem permanecer acessíveis por navegação primária, nesta ordem e com estes nomes: **Conversa**, **Automações**, **Memória**, **Agentes**, **Auditoria**, **Permissões**.
3. O painel Conversa é o destino inicial. Nenhum painel pode ser removido quando o serviço correspondente estiver indisponível; deve exibir estado vazio/indisponível explicativo. Em especial, Auditoria não deve desaparecer silenciosamente.
4. Ações destrutivas ou sensíveis continuam usando confirmação Qt nativa e nunca podem ser reduzidas a ícones sem rótulo acessível.
5. Informações da barra lateral direita são resumos acionáveis dos dados reais. Contagens, agentes e eventos fictícios do mockup não devem ser reproduzidos.

## 2. Arquitetura da janela

### Desktop amplo (largura >= 980 px)

- Janela central: alvo de 1080 × 720 px; mínimo recomendado de 860 × 600 px.
- Estrutura vertical: cabeçalho 52 px; navegação 48 px; conteúdo flexível; compositor 64 px; rodapé 28 px.
- Área de conteúdo em grid: coluna principal `minmax(520px, 2fr)`, lateral `minmax(260px, 0.9fr)`, gap 12 px.
- Margem interna da janela: 14–16 px. Espaçamento base: múltiplos de 4 px; sequência 4, 8, 12, 16, 24, 32.
- A conversa ocupa a coluna principal. A lateral mostra, no máximo, três cards: Voz, Memória/Contexto e Atividade/Agentes. Conteúdo que não couber rola dentro da lateral, sem comprimir o compositor.

### Intermediário (720–979 px)

- A lateral direita é recolhida; seus cards aparecem abaixo do conteúdo principal ou em drawer acionado por “Resumo”.
- Navegação permanece horizontal com rolagem ou distribuição compacta; nenhum nome deve ser truncado sem tooltip.
- O compositor permanece fixado ao fim do layout visível do painel Conversa.

### Compacto (< 720 px ou próximo ao mínimo atual 440 px)

- Um único fluxo vertical.
- Navegação primária vira menu/rail compacto acessível por teclado, mantendo os seis destinos.
- Rótulos dos botões críticos permanecem visíveis: Enviar/Falar, Parar ações e confirmações.
- Cards auxiliares ficam recolhidos por padrão. Não há sobreposição entre histórico, campo de texto e controles.

## 3. Componentes

### Cabeçalho

- À esquerda: símbolo/orbe Kiara, nome “Kiara” e indicador de estado real.
- À direita: manter somente ações implementadas (por exemplo, fixar/sempre no topo se existir, menu, minimizar, maximizar, fechar). Ícones devem ter tooltip, `accessibleName` e alvo mínimo de 32 × 32 px.
- Se a moldura nativa do Windows for preservada, os controles de janela customizados do mockup devem ser omitidos; duplicá-los é proibido.

### Navegação

- Estado ativo: fundo azul-petróleo discreto, texto ciano claro e marcador inferior/contorno luminoso de 1 px.
- Hover: aumento de contraste sem deslocamento geométrico. Foco: anel de 2 px claramente visível.
- A seleção deve continuar baseada no `QTabWidget` ou equivalente semanticamente navegável, com `accessibleName="Painéis da Kiara"`.

### Conversa

- Cabeçalho contextual: saudação curta e estado (“Pronta”, “Pensando…”, “Ouvindo…”, “Falando…”, “Erro”).
- Mensagens são cards/balões empilhados; autor, conteúdo e horário têm hierarquia distinta. Largura máxima 100% da coluna e padding 12–16 px.
- Mensagem do usuário: tom azul levemente mais claro. Mensagem da Kiara: superfície escura com acento ciano no avatar. Eventos do sistema: compactos, sem se passar por fala da Kiara.
- O histórico preserva seleção/cópia, rolagem, limite existente e escape de HTML.
- Compositor: botão opcional de anexo apenas se houver função real; campo expansível quando suportado; Enviar e Falar como ações separadas; `Enter` envia e `Shift+Enter` cria linha somente quando o campo aceitar múltiplas linhas. Enquanto o código usar `QLineEdit`, a dica de Shift+Enter deve ser omitida.
- “Parar ações” permanece sempre alcançável. Pode migrar para o cabeçalho/rodapé, mas precisa manter texto, `Escape`, estado de emergência e contraste de perigo.

### Painéis administrativos

- **Automações:** lista + editor/prévia; em telas estreitas, empilhar. Criar, ativar/desativar e excluir permanecem explicitamente rotulados.
- **Memória:** separar “Memórias locais” e “Base de conhecimento”; apresentar estados vazios e confirmações atuais.
- **Agentes:** transformar o snapshot atual em lista/card real, sem inventar status “ativo/pronto”. Se não houver telemetria, usar “Disponível” ou omitir status.
- **Auditoria:** timeline legível e exportação redigida; JSON bruto pode existir em uma visão de detalhes, não como única apresentação visual.
- **Permissões:** autonomia, ferramentas, kill switch, provedor e autostart organizados por seção; níveis de risco usam texto + cor, nunca somente cor.

### Sidebar/resumo

- Existe apenas no painel Conversa e somente em largura ampla.
- Cards devem refletir recursos disponíveis. Exemplos válidos: estado da voz e microfone; contagens reais de memória; últimos eventos redigidos; agentes reais.
- Links “Ver tudo/Gerenciar” devem navegar para o painel correspondente. Se a navegação não estiver implementada, o link não aparece.
- Atualização deve ser explícita ou reativa a eventos reais; não usar animações de atividade simulada.

### Orbe/overlay flutuante

- Evolução visual do `StatusOverlay`, não uma segunda instância funcional da Kiara.
- Forma circular, alvo visual 56–68 px e alvo de clique mínimo 44 px; sempre no topo somente após opt-in existente (“Mostrar overlay”).
- Um clique abre/restaura a janela principal. Menu de contexto oferece Abrir Kiara, Parar ações e Ocultar overlay. Arrastar reposiciona; a posição deve ser limitada à área útil da tela.
- Estados: pronta (ciano suave), ouvindo (pulso lento), pensando (arco rotativo discreto), falando (onda/halo), erro/interrompida (âmbar/vermelho). Animações param quando `prefers-reduced-motion` equivalente/configuração de movimento reduzido estiver ativa.
- O overlay não captura tela, áudio ou foco por estar visível. Tooltip e nome acessível devem anunciar “Kiara — {estado}”. Não expandir automaticamente; a expansão para a janela principal exige ação do usuário.

## 4. Tokens visuais

Tema escuro é o padrão da referência. A implementação deve centralizar tokens em uma única folha QSS/paleta, sem cores espalhadas pelos widgets. Deve existir escolha **Escuro / Claro / Sistema** persistida; até o tema claro ser concluído com contraste validado, “Sistema” pode resolver para escuro, mas não deve alegar suporte claro completo.

| Token | Escuro de referência | Uso |
|---|---:|---|
| `bg.canvas` | `#071522` | fundo externo/janela |
| `bg.window` | `#0A1826` | superfície principal |
| `bg.surface` | `#102131` | cards e mensagens |
| `bg.surfaceRaised` | `#142839` | hover/seleção |
| `border.subtle` | `#1E3546` | divisores e contornos |
| `border.active` | `#21D7E4` | foco/seleção |
| `text.primary` | `#E8F3F7` | títulos e corpo |
| `text.secondary` | `#9CB0BC` | metadados |
| `accent.cyan` | `#27DCE7` | marca e ação primária |
| `accent.blue` | `#388BFF` | usuário/links |
| `state.success` | `#35D07F` | disponível/concluído |
| `state.warning` | `#F2B84B` | atenção |
| `state.danger` | `#FF6577` | erro/parada |

- Tipografia: Segoe UI Variable/Segoe UI, fallback sans-serif do sistema. Corpo 13–14 px, metadado 11–12 px, título de seção 18–22 px, nome do app 18 px; altura de linha mínima 1,4.
- Raios: janela/cards 10–12 px; controles 8–10 px; pills/orbe totalmente arredondados.
- Sombras e glow são discretos e não substituem bordas. Evitar blur/transparência intensa se comprometer desempenho, legibilidade ou compatibilidade do Qt/Windows.

## 5. Estados obrigatórios

- Cada ação assíncrona apresenta: padrão, hover, foco, pressionado, desabilitado e ocupado.
- Conversa: pronta, enviando/pensando, resposta, falha recuperável e ações interrompidas.
- Voz: desativada por configuração, hardware indisponível, pronta, ouvindo, transcrevendo, falando e erro. A waveform só anima com áudio/estado real; representação estática é aceitável como ícone.
- Listas: carregando, vazia, preenchida, item selecionado e erro de carregamento.
- Painéis/sidecards indisponíveis explicam a causa e a ação possível; não somem nem mostram números zero enganosos.

## 6. Acessibilidade e comportamento

- WCAG 2.2 AA como alvo: contraste de texto normal >= 4,5:1; texto grande e componentes >= 3:1.
- Tab order segue cabeçalho → navegação → conteúdo → compositor → rodapé. Foco nunca fica preso na lateral ou no overlay.
- Todos os controles por ícone têm nome acessível e tooltip; estados são anunciados por texto e, quando possível, região acessível/alteração de nome.
- Alvos interativos mínimos de 32 px no desktop e 44 px no overlay/controles essenciais.
- Não depender apenas de ciano/verde/vermelho. Incluir ícone, rótulo ou descrição.
- Reduzir/parar pulsos, glow e transições com movimento reduzido. Transições normais entre 120–220 ms; nenhuma animação bloqueia ações.
- Escala de interface deve permanecer utilizável em 125%, 150% e 200% de DPI no Windows, sem tamanhos fixos que cortem texto.

## 7. Diferenças aceitáveis da referência

- Moldura nativa do Windows no lugar da barra customizada.
- Ícones Qt/recursos próprios equivalentes, desde que consistentes e licenciados; não é exigida cópia pixel a pixel.
- Sem fundo fotográfico, blur/acrílico ou glow pesado quando houver custo de desempenho/acessibilidade.
- Sidebar recolhida em janelas menores e omitida em painéis administrativos.
- Waveform simplificada ou estática quando não houver amplitude real disponível.
- Ausência de anexos, pin, links “Ver tudo” e status de agentes enquanto as ações/dados correspondentes não existirem.
- Controles e diálogos nativos para arquivos, confirmação, instalação e segurança.
- Conteúdo, horários, contagens e nomes exibidos devem vir do sistema real, mesmo que isso torne a tela menos preenchida que o mockup.

Não são aceitáveis: remover qualquer um dos seis painéis; esconder “Parar ações”; inventar telemetria; declarar captura/voz ativa sem estado real; sacrificar teclado, leitor de tela ou contraste para imitar a imagem.

## 8. Critérios de aceite verificáveis

1. Os seis destinos aparecem e podem ser alcançados por mouse e teclado em uma sessão com todos os serviços disponíveis; indisponibilidade produz estado explicativo, não remoção.
2. Em 440 × 420, 720 × 600, 1080 × 720 e com DPI 150%, não há sobreposição nem corte dos controles críticos.
3. O painel Conversa em >= 980 px apresenta grid principal + lateral; abaixo disso, a lateral recolhe sem perda de função.
4. Enviar, Falar, Modo conversa e Parar ações refletem os estados reais existentes; controles indisponíveis explicam o motivo em tooltip/texto.
5. Overlay é opt-in, anuncia estado real, abre a mesma janela principal e permite parada/ocultação; não inicia sensores.
6. Todos os ícones acionáveis possuem tooltip e nome acessível; navegação e ações críticas funcionam sem mouse.
7. Cores vêm dos tokens centralizados; contraste é medido e atende aos limites acima nos temas efetivamente oferecidos.
8. Nenhum dado fictício da referência aparece em screenshots de evidência.
9. A implementação passa pelos testes funcionais existentes e por inspeção visual nos quatro tamanhos/DPI definidos, com screenshots armazenadas em `evidence/`.

