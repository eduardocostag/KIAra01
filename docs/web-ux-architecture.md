# Arquitetura de informação e jornadas web — Kiara Lead Intelligence

**Status:** contrato de UX implementável; não representa interface construída nem validação com usuários.  
**Data:** 2026-09-04  
**Prioridade de lançamento:** operação B2C que recebe, qualifica e responde DMs pelo Instagram oficial, com aprovação humana.

## 1. Resultado pretendido

A versão web deve permitir que um cliente entre por URL, autentique-se, conecte sua conta profissional do Instagram e opere a jornada completa sem instalar software. O primeiro valor é: **ver uma conversa inbound, entender intenção e qualificação, revisar a resposta sugerida e responder com segurança**.

Princípios vinculantes:

1. A caixa de entrada é o centro operacional do lançamento, não um apêndice de “Integrações”.
2. Gerar rascunho, aprovar e enviar são comandos e estados diferentes.
3. Origem, consentimento, canal, janela aplicável e bloqueio acompanham toda ação B2C.
4. Fatos, inferências e lacunas permanecem rotulados e rastreáveis.
5. A interface nunca promete conexão, envio ou atualização que o backend não confirmou.
6. Organização e usuário ativos estão sempre identificáveis; toda rota e mutação são isoladas por tenant no servidor.
7. Tema **Claro / Escuro / Sistema** fica disponível no menu do usuário e persiste por conta; o primeiro acesso respeita a preferência do sistema.

## 2. Mapa do produto

### Rotas públicas

| Rota | Objetivo |
|---|---|
| `/` | Proposta de valor, segurança, demonstração e entrada para login. |
| `/login` | Login, recuperação e retorno seguro ao destino solicitado. |
| `/invite/:token` | Aceitar convite, confirmar identidade e entrar na organização correta. |
| `/privacy`, `/terms`, `/status` | Transparência legal e operacional. |

### Rotas autenticadas

| Destino global | Rota | Função |
|---|---|---|
| Visão geral | `/app` | Saúde da operação, prioridades e ativação. |
| Inbox | `/app/inbox` | DMs Instagram, triagem, qualificação e resposta governada. |
| Hunter | `/app/hunter` | Sinais e oportunidades pesquisáveis, separados de pessoas contatáveis. |
| Pipeline | `/app/pipeline` | Oportunidades por estágio, responsável e próxima ação. |
| Integrações | `/app/integrations` | Conectar, testar, reconectar e limitar provedores. |
| Configurações | `/app/settings/*` | Operação, equipe, autonomia, privacidade, IA e aparência. |

O **Dossiê** é rota contextual `/app/leads/:leadId`, aberta a partir de Inbox, Hunter, Pipeline ou Visão geral. Voltar restaura rota de origem, consulta, filtros, scroll, item selecionado e página. O onboarding usa `/onboarding/:step` e não aparece como destino global após concluído; configurações permitem revisitar cada seção.

### Navegação global

Ordem para o lançamento B2C: **Visão geral, Inbox, Hunter, Pipeline, Integrações**. Configurações, ajuda, tema e sair ficam no menu de conta; alertas, atividade e seletor de organização ficam no cabeçalho global. “Parar ações” permanece descobrível no cabeçalho quando houver execução cancelável e no Centro de atividade em todos os estados.

Evitar uma navegação principal com mais de cinco destinos no MVP. Campanhas e Conversas separadas só entram quando houver capacidade real; no lançamento, a conversa pertence à Inbox e resultados pertencem à Visão geral/Pipeline.

## 3. Shell responsivo

| Viewport | Navegação | Conteúdo |
|---|---|---|
| `>=1280 px` | Sidebar 248 px, ícone + rótulo | Lista e detalhe simultâneos na Inbox; Dossiê com índice lateral. |
| `1024–1279 px` | Rail 72 px expansível | Lista/detalhe conforme espaço; painéis secundários viram drawer. |
| `768–1023 px` | Barra superior + drawer | Uma região primária; lista abre detalhe como rota. |
| `<768 px` | Barra superior + drawer e navegação inferior opcional para Visão geral/Inbox/Pipeline | Fluxo em coluna única; ações persistentes respeitam teclado e safe areas. |

Container operacional usa a largura disponível, com margens de 16/20/24 px. Conteúdo editorial e formulários têm máximo de 720 px; tabelas, Inbox e Pipeline não são forçados a esse limite. Alvos interativos têm no mínimo 44×44 px no touch. Nenhum recurso crítico depende de hover, arrastar ou clique direito.

No mobile, selecionar conversa abre `/app/inbox/:conversationId`; voltar retorna à mesma posição. O Kanban oferece uma **Lista por estágio** equivalente por teclado e touch. Arrastar um card é apenas atalho; “Alterar etapa” é a operação canônica.

## 4. Jornadas principais

### 4.1 Login e sessão

1. Usuário informa e-mail e usa o método de autenticação configurado.
2. A interface mostra erro específico e recuperável sem revelar se uma conta alheia existe.
3. Havendo uma organização, entra no último destino permitido; havendo várias, seleciona workspace.
4. Sem organização/configuração, segue para onboarding.
5. Sessão expirada preserva rascunho local cifrado quando aplicável, pede reautenticação e retoma a ação sem repeti-la automaticamente.

Estados obrigatórios: carregando sessão, credencial inválida, conta bloqueada, convite expirado, organização indisponível, sem permissão, sessão expirada e falha de rede. A troca de organização limpa seleções e cache sensível antes de buscar o novo tenant.

### 4.2 Onboarding B2C Instagram

Fluxo persistente, retomável e com “Etapa X de 6”:

1. **Negócio e oferta:** nome, segmento, região, produto/serviço, ticket e proposta de valor.
2. **Qualificação:** público, intenções, perguntas, critérios positivos/eliminatórios e handoff humano.
3. **Instagram:** explicar pré-requisitos, iniciar OAuth oficial, escolher conta profissional e confirmar webhook/saúde sem exibir segredos.
4. **Atendimento:** tom, horário, responsável, SLA interno e regras para respostas fora de escopo.
5. **Controle:** autonomia padrão 3, aprovação obrigatória, limites, opt-out, retenção e kill switch.
6. **Revisão:** resumo, lacunas, termos e teste read-only; finalizar leva à Inbox.

Conectar Instagram pode ser adiado, mas o dashboard permanece em estado de ativação honesto. “Testar conexão” nunca envia DM. Falha de OAuth preserva as etapas preenchidas e oferece retomar. A interface deve explicar claramente que perfis públicos e sinais isolados não autorizam DM fria.

### 4.3 Inbox Instagram — caminho crítico

Estrutura ampla: lista de conversas (320–380 px), conversa flexível e painel de contexto (320–400 px). Em telas menores, cada região vira rota/drawer preservando estado.

Fluxo:

1. Evento inbound validado aparece como **Nova**, com data, conta, identidade minimizada permitida e status de entrega.
2. Seleção abre histórico e resumo de intenção; conteúdo não confiável é tratado como mensagem, nunca instrução de sistema.
3. Painel contextual mostra fatos, inferências, lacunas, score explicado, consentimento/canal, responsável e próxima ação.
4. **Preparar resposta** gera rascunho marcado “Ainda não enviado”.
5. Operador edita; qualquer edição invalida aprovação anterior.
6. **Solicitar aprovação** ou **Aprovar** registra ator, payload e validade conforme papel.
7. **Enviar pelo Instagram** exibe prévia final, destinatário/conta, conteúdo, política e estado do kill switch.
8. Backend revalida imediatamente antes do I/O. Resultado é `Enviado`, `Falhou`, `Estado desconhecido` ou `Bloqueado`; somente confirmação do provedor aparece como sucesso.

Ações adjacentes: atribuir responsável, marcar como aguardando, registrar opt-out, bloquear, abrir Dossiê e criar/mover oportunidade. Opt-out interrompe novos rascunhos/envios e permanece visível. Retry de envio exige estado seguro/idempotente ou revisão humana; nunca é silencioso.

Filtros padrão: Novas, Minhas, Aguardando aprovação, Aguardando cliente, Bloqueadas e Todas. Busca e filtros entram na URL para restauração e compartilhamento autorizado. Badge de não lidas não pode ser a única indicação de prioridade.

### 4.4 Hunter

Hunter separa estruturalmente:

- **Oportunidades contatáveis:** originadas de fonte autorizada e com canal/finalidade válidos.
- **Sinais públicos:** fatos/sinais para revisão ou resposta pública permitida; não viram automaticamente consumidor contatável.
- **Bloqueados:** opt-out, retenção, canal, política ou confiança insuficiente, sempre com motivo e remediação.

Cada resultado mostra tipo antes do nome, origem/data, intenção, recência, score e fatores, nível de confiança, canal permitido e ação recomendada. “Adicionar ao pipeline” abre preview e deduplicação; “Preparar abordagem privada” só existe quando a policy permite. Busca longa roda como job observável com progresso real, cancelar, retomar e resultados incrementais.

### 4.5 Pipeline

Views **Quadro** e **Lista** compartilham filtros e dados. Estágios B2C iniciais: Novo, Em qualificação, Qualificado, Em conversa, Proposta, Ganho, Perdido/Bloqueado, ajustáveis somente após validação do produto.

Card/linha: pessoa/oportunidade, origem Instagram, intenção, score + confiança, responsável, última interação, próxima ação e prazo. Abrir não altera estágio. Mudança de estágio mostra origem/destino; estados terminais exigem motivo. Após persistir, snackbar oferece desfazer por pelo menos 8 segundos e cria evento compensatório auditável. Falha parcial em lote identifica os itens afetados.

### 4.6 Dossiê do lead

Cabeçalho persistente: identidade permitida, origem, estágio, score/confiança, responsável, atualização, consentimento/canal e bloqueios. CTA dominante: **Preparar próxima ação**; enviar nunca é a ação primária do Dossiê.

Seções: resumo executivo; evidências verificadas; hipóteses; lacunas e riscos; qualificação explicada; histórico/consentimento; kit comercial. Toda evidência inclui fonte e data. Seções vazias dizem o que falta e como obter, sem texto inventado. A linha do tempo une mensagem recebida, análise, mudança, aprovação, tentativa e resultado com ator e correlação, sem expor segredo.

### 4.7 Integrações e configurações

Integrações usa cards com estado real: Não configurada, Conectando, Saudável, Degradada, Autorização necessária, Limitada e Indisponível. Cada detalhe mostra capacidades concedidas, conta conectada, última verificação, última falha sanitizada, limites conhecidos e ações Conectar/Reautorizar/Testar/Desconectar. Desconectar exige explicar efeitos em jobs, inbox e dados históricos.

Configurações possui subrotas:

- Operação e oferta;
- Qualificação/Hunter;
- Atendimento e templates;
- Equipe e papéis;
- Autonomia e aprovações;
- Privacidade e retenção;
- IA e limites de uso;
- Aparência (Claro/Escuro/Sistema);
- Auditoria e exportação.

Mudanças críticas exibem impacto antes de salvar. Segredos nunca são retornados após gravação; UI mostra apenas configuração presente, escopo e rotação. Permissão é validada no servidor — esconder botão não é autorização.

## 5. Visão geral e ativação

A Visão geral responde primeiro: “o que requer atenção agora?”. Ordem:

1. Banner de ativação/saúde Instagram e última atualização.
2. Fila operacional: novas DMs, aprovações, bloqueios e entregas desconhecidas.
3. Próximas ações com motivo, prazo e responsável.
4. Funil e métricas reais do período, rotulando dados demo.
5. Riscos de consentimento, integração, SLA e dados incompletos.

Estado vazio nunca apresenta métricas decorativas. Sem Instagram: **Conectar Instagram**. Conectado sem DM: instruções e status do webhook. Com filtro vazio: **Limpar filtros**. Falha preserva último snapshot com “Atualizado em…” e oferece tentar novamente.

## 6. Sistema visual web

Reutilizar a identidade do contrato atual, com tokens CSS semânticos e variantes equivalentes claras:

- grafite/azul-noite como assinatura do tema escuro;
- cobalto/violeta apenas para ação primária, seleção e IA;
- ciano/verde/âmbar/rosa reservados a estados operacionais;
- escala espacial de 4, 8, 12, 16, 20, 24, 32 e 48 px;
- raios de 8 px em controles, 12 px em cards e 16 px em painéis;
- tipografia web: Geist Sans ou Segoe UI Variable; mono apenas para IDs/telemetria;
- foco de 2 px com offset, contraste WCAG AA e preferência `prefers-reduced-motion`.

Claro, Escuro e Sistema precisam ter paridade funcional. Tema não codifica tenant nem estado; estados usam texto/ícone além de cor. Transições duram 120–200 ms e não bloqueiam interação. Skeleton só representa geometria conhecida; jobs usam progresso real ou atividade indeterminada explicitamente rotulada.

## 7. Componentes e estados obrigatórios

| Componente | Estados essenciais |
|---|---|
| App shell | carregando sessão, ativo, offline/reconectando, sem permissão, tenant trocado |
| Inbox list | carregando, vazia por causa, parcial, erro+retry, nova atualização sem roubar foco |
| Conversation | recebida, rascunho, editada, aprovação pendente/aprovada/expirada, enviando, enviada, falhou, desconhecida, bloqueada |
| Policy badge | permitido, revisão necessária, bloqueado + motivo textual |
| Score | calculado, desatualizado, não calculado; fatores, ausentes, confiança e data |
| Job bar | na fila, executando, cancelando, cancelado, parcial, falhou, concluído, needs review |
| Integration card | não configurada, saudável, degradada, auth necessária, limitada, indisponível |
| Protected action | preview, aprovação, revalidação, execução, reconciliação e resultado |
| Toast/snackbar | sucesso confirmado, aviso, erro persistente e desfazer com temporizador acessível |

Erros inline pertencem ao campo; banners pertencem à região; Centro de atividade agrega jobs e falhas; modal fica restrito a decisão obrigatória ou risco irreversível. Atualizações usam live regions moderadas, sem mover foco. Toda ação assíncrona bloqueia duplicação e mantém chave idempotente.

## 8. Acessibilidade, localização e segurança percebida

- HTML semântico, landmarks e um H1 por rota; skip link no início.
- Ordem de foco: navegação → cabeçalho/filtros → lista → conteúdo/detalhe → ações.
- Drawer/modal aprisiona foco, fecha com Escape e o devolve ao acionador.
- Toda função da Inbox, Pipeline, aprovação e bloqueio funciona por teclado.
- Novas mensagens são anunciadas sem interromper leitura; usuário escolhe se quer auto-scroll.
- Textos e datas em pt-BR; horários mostram fuso da organização; números e moeda seguem locale.
- Identificadores e conteúdo sensível são minimizados em listas, notificações, logs visuais e URLs.
- Links externos e troca de conta informam destino; nenhuma credencial aparece no DOM após conexão.

## 9. Critérios de aceite UX web

1. Um novo cliente conclui login, onboarding e conexão oficial do Instagram e chega à Inbox, podendo retomar após interrupção.
2. Do recebimento da DM ao rascunho aprovado e envio governado, cada estado é distinguível e o sucesso depende de confirmação do backend/provedor.
3. Nenhuma DM privada pode ser preparada/enviada para sinal público isolado ou após opt-out.
4. Em 360, 768, 1024, 1280 e 1440 px, todos os destinos e ações críticas permanecem acessíveis sem sobreposição.
5. Inbox, Hunter, Pipeline e Dossiê funcionam integralmente por teclado; foco é visível e restaurado.
6. Voltar do detalhe restaura lista, filtros, scroll e seleção.
7. Tema Claro/Escuro/Sistema persiste, respeita preferência do SO e mantém contraste AA.
8. Carregamento, vazio, parcial, erro, retry, offline, sessão expirada, cancelamento e estado desconhecido têm recuperação explícita.
9. Alterar estágio possui alternativa ao drag, persiste, anuncia origem/destino e oferece undo idempotente.
10. Troca de organização não mistura cache, busca, notificações, rascunhos ou dados entre tenants.

## 10. Sequência de implementação

1. Shell autenticado, tenant ativo, rotas, temas e autorização server-side.
2. Onboarding retomável e conexão oficial do Instagram.
3. Inbox responsiva com estados de conversa e painel de contexto.
4. Rascunho → aprovação → envio → reconciliação com kill switch.
5. Dossiê contextual e qualificação explicável.
6. Pipeline Lista/Quadro com histórico e undo.
7. Hunter com separação contatável/sinal/bloqueado e jobs observáveis.
8. Dashboard real, configurações, auditoria e acabamento acessível.
9. Testes com usuários e browser matrix antes de alegar prontidão comercial.

## 11. Decisões e limites

- A IA e regras Python existentes podem alimentar a web, mas este contrato não escolhe framework nem declara APIs, autenticação, banco multi-tenant ou workers implementados.
- A experiência prioriza Instagram inbound B2C; prospecção fria automatizada, scraping e disparo em massa permanecem fora do produto.
- Aplicação web exige backend sempre disponível, armazenamento remoto isolado, sessões seguras, jobs duráveis, observabilidade, backup/restore e operação de suporte. Uma UI publicada sem essas garantias não é SaaS pronto.
- Validação visual, acessibilidade com tecnologia assistiva, Meta real ponta a ponta e testes multi-tenant continuam gates independentes.
