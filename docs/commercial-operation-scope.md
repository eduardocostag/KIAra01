# Kiara: operação comercial integrada

Implementação e deploy realizados: veja [a publicação e a ativação dos canais](commercial-release.md).
O diagnóstico abaixo registra o ponto de partida que orientou essa implementação.

## Resultado esperado

A Kiara encontra oportunidades, organiza o CRM, faz prospecção pelos canais
configurados, atende clientes com IA e concentra a operação no próprio site.
As integrações devem alimentar essa jornada e compartilhar contato, histórico,
classificação e próxima ação.

Decisão do usuário: usar o WhatsApp Web já conectado no Chrome, em modo experimental.
O executor deve preservar essa sessão. O processamento de conversas parte do Ollama
local existente; trocar o modelo ou enviar esses dados a outro serviço é outra configuração.

## Capacidades e critérios de conclusão

| Capacidade | Comportamento esperado | Evidência de conclusão |
| --- | --- | --- |
| Captar leads | Buscar por oferta, nicho, região e perfil em Maps, web e fontes sociais conectadas | Resultado real com fonte, contato verificado quando possível e motivo de aderência |
| Organizar leads | Remover duplicatas, manter origem, responsável, histórico e próxima ação | Reimportar o mesmo contato atualiza sua ficha e preserva histórico |
| Classificar leads | Separar temperatura frio/morno/quente de etapa do funil e prioridade de atendimento | Classificação explicável muda quando chegam novos sinais; score fixo não atende |
| Prospectar em vários canais | Preparar e executar abordagens e follow-ups dos contatos incluídos na operação | Envio rastreável, estado confirmado ou incerto, pausa respeitada e sem duplicação automática |
| Atender no WhatsApp | Receber mensagens, contextualizar, responder e atualizar CRM autonomamente quando habilitado | Conversa completa realizada na mesma sessão Chrome, com registro na Kiara e transferência ao humano |
| Centralizar mensagens | Exibir WhatsApp, Instagram e demais canais conectados numa caixa de atendimento da Kiara | Receber e responder pelo site, mantendo canal, conversa e vínculo com lead corretos |
| Operar Instagram | Preparar conteúdo, organizar calendário e publicar automaticamente o que estiver autorizado; tratar interações suportadas | Agendamento executado no canal real com identificador de publicação; simulação não conta |

Temperatura comercial e etapa do funil são informações diferentes. Um lead quente pode
estar em negociação; um contato novo pode ter prioridade alta por pedir orçamento.
Também devem existir estados de cliente, sem interesse e atendimento humano.

## Jornada principal

1. Configurar oferta, público, regiões, canais, conhecimento comercial e limites.
2. Pesquisar oportunidades e revisar qualidade/origem dos contatos.
3. Inserir ou atualizar o lead no CRM, sem duplicar sua identidade.
4. Preparar a abordagem conforme o contexto e o canal.
5. Executar o contato dentro da operação habilitada e registrar o resultado.
6. Receber a resposta na caixa unificada, atualizar temperatura e próxima ação.
7. A IA atende com base no catálogo, preços, condições e orientações cadastradas.
8. Solicitação de humano, falta de informação ou caso fora do escopo transfere a conversa.
9. Uma resposta nova cancela follow-up obsoleto; conversa assumida por humano pausa o bot.

Autonomia deve ser habilitada por operação/canal, sem exigir aprovação em cada resposta
rotineira depois dessa configuração. Devem existir pausa geral, pausa por contato,
histórico das decisões e confirmação de envio. Resultado incerto não deve causar reenvio
automático. A IA não inventa preço, prazo, disponibilidade ou compromisso comercial.

## Estado encontrado antes da implementação

| Área | Base existente | Trabalho ainda necessário |
| --- | --- | --- |
| Captação | Hunter e fontes web/Maps/Instagram/Facebook; importação CRM | Integrar a jornada com acompanhamento e qualidade por fonte |
| CRM | Pipeline, histórico e próximas ações | Unificar classificação comercial do desktop e do site; atualizar contatos existentes |
| WhatsApp Chrome | Extensão e executor leem conversas visíveis e importam leads | Recepção contínua, envio controlado na sessão existente e sincronização bidirecional |
| Agente WhatsApp | Motor local tem fila, IA, pausa e transferência em um caminho de piloto | Conectá-lo ao executor Chrome atual e à inbox; remover a limitação de piloto apenas após validar esse fluxo |
| Caixa de entrada | Componentes de conversas e API Chatwoot | Ingestão e sincronização reais entre canais, CRM e interface única |
| Instagram | Skills, utilitários, rascunhos e integração Postiz administrativa | Disponibilizar operação por workspace, conectar publicação real ao calendário e tratar interações suportadas |

Evidências principais da inspeção:

- `app/whatsapp/browser.py`: navegador da extensão declara `read_only=True`.
- `app/whatsapp/engine.py`: o ciclo retorna antes de respostas nesse modo.
- `services/api/kiara_api/whatsapp_web.py`: análise ignora contatos já existentes por telefone,
  em vez de atualizar sua qualificação continuamente.
- `services/api/kiara_api/adapters/postgres.py`: qualificação de thread ainda usa score 50 e
  temperatura warm fixos nesse caminho.
- `apps/web/src/app/(app)/app/inbox/page.tsx`: a rota principal carrega pipeline e mostra
  leads; isso ainda não constitui uma caixa omnichannel sincronizada.
- `services/api/kiara_api/chatwoot.py`: leitura/envio por API, sem ingestão de eventos para
  o CRM/inbox da Kiara.
- `services/api/kiara_api/social.py`: publicação desse caminho é assistida/simulada.
- `apps/web/src/lib/postiz/admin.ts`: integração Postiz existente é administrativa;
  não representa uma operação social pronta para todo workspace.

## Ordem de implementação

### 1. Fechar o ciclo WhatsApp e CRM

Usar a sessão Chrome existente para receber, identificar o contato, atualizar sua ficha,
classificar o lead, responder pelo agente local e registrar o resultado no site.
Validar primeiro uma conversa real de teste ponta a ponta, com pausa e intervenção humana.
Depois ampliar contatos, prospecção e follow-ups dentro dos limites configurados.

### 2. Entregar a caixa unificada

Modelar identidade e origem por canal, ingerir eventos, deduplicar mensagens e sincronizar
o histórico com a interface da Kiara. Adicionar Instagram ao mesmo fluxo. Chatwoot pode
ser usado como infraestrutura, mas a operação do usuário permanece centralizada na Kiara.

### 3. Unificar captação, qualificação e cadências

Conectar Hunter, score explicável, estágio, inbox e próximas ações. Distinguir primeiro
contato, resposta de atendimento e follow-up; cada um precisa de estado e execução próprios.

### 4. Automatizar conteúdo e interações do Instagram

Conectar conta/canal por workspace, calendário, mídia, publicação e confirmação no provedor.
Adicionar respostas e outras ações conforme as capacidades efetivamente disponíveis no canal.
Skills de conteúdo ajudam a preparar as peças, mas não substituem o executor/publicador.

## Limite desta consolidação

Este documento registra o escopo e o diagnóstico inicial. A implementação subsequente e
as evidências estão em [commercial-release.md](commercial-release.md). A ativação de contas,
do executor e da política continua necessária; deploy não habilita envios por si só.
