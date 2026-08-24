# Contrato de experiência de voz — Kiara (pt-BR)

## Objetivo

A voz deve transmitir calma, proximidade e competência, sem imitar uma pessoa real nem
prometer naturalidade absoluta. A aceitação combina métricas técnicas e avaliação humana;
nenhum motor deve ser declarado “perfeito” apenas por funcionar.

## Perfil sonoro

- Variante: português brasileiro neutro, sem caricatura regional.
- Timbre: adulto, acolhedor, claro e sem excesso de brilho, sussurro ou teatralidade.
- Ritmo conversacional alvo: 145–170 palavras por minuto em respostas comuns.
- Instruções de risco, confirmações e números críticos: 125–145 palavras por minuto.
- Variação de prosódia: frases afirmativas encerram com queda leve; perguntas têm elevação
  discreta. Evitar cadência idêntica em todas as frases.
- Pausas: 120–220 ms em vírgulas, 250–450 ms entre frases e 450–700 ms antes de uma
  confirmação sensível. Não verbalizar Markdown, emojis ou marcadores decorativos.
- Volume padrão confortável, ajustável pelo usuário; nunca normalizar com ganho que cause
  clipping.

## Preparação do texto falado

- Respostas longas: oferecer primeiro um resumo falado de até 45 palavras. Acima de 90
  palavras, perguntar se o usuário quer ouvir o restante; o texto completo permanece na tela.
- Listas: anunciar a quantidade e falar no máximo cinco itens por bloco, com pausas curtas.
- Números: usar leitura cardinal no contexto comum; telefone, CPF, códigos e tokens devem ser
  lidos em grupos curtos. Valores monetários e datas devem usar a forma natural de pt-BR.
- Siglas: usar pronúncia consagrada quando existir (por exemplo, “Nasa”) e soletrar siglas
  desconhecidas com pausa breve entre letras. Permitir dicionário de pronúncia local.
- URLs e caminhos: falar domínio e finalidade, não a sequência inteira por padrão. Oferecer
  “posso soletrar” sob demanda. Nunca falar segredo, token ou parâmetro sensível.
- Mensagens técnicas: expandir abreviações que soam artificiais e remover vestígios de
  Markdown/código. Blocos de código não são lidos automaticamente.
- Pontuação e símbolos: converter `%`, `R$`, unidades e horários para formas naturais antes
  da síntese; preservar o texto visual original.

## Turnos e interrupção

- Qualquer acionamento de “Falar”, `Esc` ou fala detectada durante a resposta deve iniciar o
  cancelamento em até 200 ms e impedir áudio residual perceptível após 350 ms.
- Após interrupção, não reiniciar nem repetir automaticamente. Mostrar “Interrompida” e ficar
  pronta para o próximo turno.
- A Kiara deve começar a falar em até 800 ms após a resposta estar disponível localmente
  (p95), podendo sinalizar processamento antes disso.
- O modo contínuo deve indicar visualmente quando o microfone está ouvindo. Wake word e
  consentimento existentes continuam obrigatórios conforme a política configurada.
- Notificações proativas não devem interromper o usuário nem falar automaticamente durante
  outra mídia, reunião ou modo silencioso; nesses casos, permanecem visuais.

## Preferências e acessibilidade

Expor, com prévia “Olá, eu sou a Kiara. Esta é minha voz”, as preferências:

- voz instalada/provedor selecionado;
- velocidade (Lenta, Natural, Rápida e ajuste fino);
- volume e modo silencioso;
- respostas faladas: Sempre, Apenas quando iniciado por voz, Nunca;
- falar notificações proativas (desligado por padrão);
- nível de concisão falada;
- dicionário de pronúncia editável e restauração dos padrões.

Os controles precisam de nomes acessíveis, navegação por teclado e anúncio de estado por
leitor de tela. Usuários com baixa audição devem receber sempre transcrição equivalente; não
usar apenas áudio para alertas ou confirmações. Usuários sensíveis a som precisam de modo
silencioso persistente e volume independente.

## Critérios de aceitação

### Testes automatizados

1. Normalização cobre datas, horários, moeda, porcentagens, unidades, siglas, URL, caminho,
   Markdown e texto com segredo redigido.
2. Texto visual original não é modificado; apenas uma cópia sanitizada segue ao sintetizador.
3. Respostas acima de 90 palavras são resumidas/segmentadas conforme a preferência.
4. Cancelamento é idempotente e impede o reinício automático do trecho interrompido.
5. Modo silencioso e “apenas quando iniciado por voz” bloqueiam síntese proativa.
6. Preferências inválidas são limitadas a faixas seguras e persistidas sem credenciais.

### Avaliação humana

Executar teste cego com pelo menos 8 falantes de pt-BR, incluindo diversidade etária,
regional e ao menos 2 participantes que usem recursos de acessibilidade. Roteiro mínimo:
saudação, conversa curta, instrução, data/hora, moeda, sigla, URL, erro, confirmação sensível,
resposta longa e interrupção.

Metas:

- naturalidade média ≥ 4,2/5;
- suavidade/conforto ≥ 4,3/5;
- inteligibilidade ≥ 95% das frases;
- pronúncia correta ≥ 97% dos itens do roteiro;
- nenhum participante relata volume doloroso, segredo falado ou impossibilidade de
  interromper;
- preferência pela voz candidata contra o SAPI padrão em pelo menos 70% das comparações.

Se as metas humanas não forem atingidas, a voz permanece “experimental”, mesmo com os
testes automatizados aprovados.
