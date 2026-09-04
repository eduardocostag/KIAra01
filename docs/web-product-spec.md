# Especificação de produto — Kiara Web SaaS para Instagram B2C

**Status:** aprovado para implementação de MVP; não equivale a aprovação de produção  
**Responsável:** Product Manager  
**Data:** 2026-09-04  
**Prioridade:** cliente B2C que prospecta, conversa e qualifica pelo Instagram

## Press release

A Kiara Web ajuda pequenas operações B2C a transformar mensagens recebidas no Instagram em oportunidades qualificadas e acompanháveis, sem instalar software. O operador conecta uma conta profissional autorizada, recebe conversas em um workspace protegido, entende a priorização, revisa a resposta preparada pela Kiara e acompanha a próxima ação. A primeira entrega é um copiloto web inbound assistido: a Kiara organiza, qualifica e prepara; uma pessoa aprova cada mensagem externa.

## Problema e hipótese

O cliente de lançamento opera dentro do Instagram. A instalação Windows adiciona fricção, depende de uma máquina ligada e não é base confiável para webhooks contínuos. O SaaS deve remover essa dependência sem perder consentimento, opt-out, aprovação e auditoria.

A prioridade é sustentada pelo direcionamento explícito de um cliente e pelos contratos/testes locais existentes, mas ainda não por entrevistas amplas ou uso real do SaaS. Metas são hipóteses de piloto; produção depende de conta Meta real e gates técnicos. O desktop permanece suportado durante a transição.

## Personas e RBAC mínimo

- **Operador comercial social:** atende DMs, identifica intenção, coleta lacunas e programa retorno.
- **Owner/gestor:** configura oferta, conecta a conta, gerencia pessoas e acompanha qualidade e auditoria.
- **Suporte Kiara:** diagnostica infraestrutura com acesso temporal e auditado, sem leitura padrão de conteúdo.

| Papel | Permissões no MVP |
|---|---|
| Owner | Workspace, membros, integração, políticas e operação comercial. |
| Manager | Todas as conversas/leads, correção, aprovação e auditoria; sem excluir o workspace. |
| Operator | Inbox atribuída, rascunho, aprovação conforme política e próxima ação. |
| Platform support | Elevação temporal, escopada, justificada e auditada. |

Um usuário pode integrar vários workspaces, sempre com contexto escolhido explicitamente.

## Contrato de tenancy

O tenant é o **workspace da empresa cliente**, não o usuário ou a conta social. Cada membro, conta conectada, evento, conversa, consumidor, consentimento, score, rascunho, aprovação, entrega, oportunidade e auditoria pertence a exatamente um `workspace_id`.

1. Autenticação identifica o usuário; o servidor valida associação, papel e workspace em toda operação.
2. IDs do navegador nunca autorizam sozinhos; consultas/comandos recebem o tenant da sessão autorizada.
3. No MVP, um workspace conecta uma conta profissional; uma conta não pode ficar ativa em dois workspaces.
4. Eventos são roteados pelo ID da conta. Evento sem vínculo único é rejeitado/quarentenado.
5. Buscas, métricas, exports, caches, filas, arquivos e logs preservam escopo de tenant.
6. Segredos Meta ficam em cofre por tenant e nunca chegam ao browser, logs ou exports.
7. Acesso de suporte entre tenants exige elevação temporal, motivo e trilha de auditoria.
8. Dados desktop não são copiados automaticamente para a nuvem.

## Jornada e critérios de aceite

### 1. Login e workspace

O usuário autentica, cria/escolhe o workspace e entra no onboarding retomável.

**Aceite:** expiração de sessão não apaga rascunho persistido; trocar workspace limpa contexto/cache; uma rota de outro tenant não revela que o recurso existe.

### 2. Onboarding B2C

Coleta empresa, oferta, preço, região, público, critérios, tom, responsáveis, horário, aprovação e retenção. Autonomia padrão: nível 3.

**Aceite:** salva por etapa, valida campos com acessibilidade, identifica demonstração e conduz à conexão do Instagram.

### 3. Instagram oficial

Owner inicia OAuth/Instagram Login, escolhe a conta profissional e confirma permissões. Estados: não conectado, conectando, conectado, ação necessária, erro e revogado.

**Aceite:** token não aparece no browser/log; callback é ligado à sessão e ao tenant; duplicidade é bloqueada; “saudável” exige teste verificável; desconectar interrompe ingestão/envio.

### 4. Inbox e triagem

Eventos autenticados criam/atualizam conversa e consumidor uma vez. A inbox separa não lidas, aguardando resposta, aguardando cliente, bloqueadas e concluídas.

**Aceite:** atualização sem refresh; duplicata/eco não duplica inbound nem efeitos de IA; falha tem recuperação; lista e detalhe funcionam por teclado e mobile.

### 5. Hunter

O detalhe mostra mensagem, resumo, intenção, temperatura, score/fatores, fatos, inferências, desconhecidos, consentimento, opt-out, perguntas e próxima ação. Correções guardam autoria.

**Aceite:** DM é conteúdo não confiável; ausência não vira fato; score é explicado e datado; sinal isolado não cria SQL; opt-out bloqueia geração e entrega.

### 6. Rascunho, aprovação e envio

Geração, edição, aprovação e envio são comandos distintos. Imediatamente antes do envio, revalidar tenant, canal, consentimento/supressão, aprovação, validade, kill switch e idempotência.

**Aceite:** gerar nunca envia; aprovação registra pessoa, hash do conteúdo, horário e expiração; editar invalida aprovação; clique duplo/retry entrega no máximo uma vez; 429/5xx gera retry limitado e visível; sucesso só após confirmação real.

### 7. Pipeline

Conversa qualificada cria/associa oportunidade B2C com etapa, responsável, próxima ação e prazo.

**Aceite:** transição persiste e é auditada; última mudança elegível pode ser desfeita; conversa e oportunidade permanecem ligadas; métricas respeitam tenant, período e vazio.

## Arquitetura de informação web

1. **Hoje:** prioridades, aprovações, follow-ups e saúde.
2. **Inbox:** conversas Instagram e qualificação.
3. **Pipeline:** oportunidades B2C e próximas ações.
4. **Aprovações:** pendentes, expiradas, aprovadas e falhas.
5. **Desempenho:** volume, primeira resposta, qualificação e funil.
6. **Configurações:** operação, membros, Instagram, autonomia, privacidade e auditoria.

Hunter é uma capacidade de Inbox/Pipeline. B2B, multicanal e copiloto genérico não ocupam a navegação do MVP.

## Now — primeira entrega

- Web responsiva por URL, autenticação, sessão, workspace e RBAC.
- Onboarding B2C retomável e uma conta profissional Instagram por workspace.
- Webhook seguro, ingestão idempotente e inbox em tempo próximo do real.
- Hunter explicável, correção humana, consentimento e opt-out.
- Rascunho, aprovação humana, envio governado e auditoria.
- Pipeline B2C, responsável, etapa, próxima ação, prazo e undo seguro.
- Métricas reais básicas, kill switches, observabilidade, backup/restore e suporte mínimo.
- Interface pt-BR responsiva, acessível por teclado, com estados completos.

## Cortes explícitos

- Scraping, lista de seguidores/curtidas, DM fria ou em massa.
- Resposta totalmente autônoma, cadências e autonomia acima do nível 3.
- B2B web, WhatsApp, e-mail, voz, CRM, calendário ou múltiplas contas Instagram.
- Billing self-service, marketplace, white-label ou domínio customizado.
- App móvel nativo, offline-first ou paridade total com desktop.
- Migração automática local e sincronização bidirecional desktop-web.
- Analytics/predição avançados, pipeline livre e permissões por campo.

Esses cortes preservam o caminho crítico: login → conectar → receber DM → qualificar → aprovar → responder → acompanhar.

## Metas do piloto

Baseline é desconhecido; analytics não devem coletar texto da DM ou PII desnecessária.

| Resultado | Meta inicial | Janela |
|---|---:|---|
| Onboarding + conexão concluídos | ≥70% dos workspaces | 24 h |
| Primeira DM ingerida e triada | mediana ≤15 min após conexão | primeiro uso |
| DMs inbound sem duplicação | 100% na amostra auditada | contínuo |
| Tempo até primeira resposta humana | redução ≥30% contra baseline | 14 dias |
| Qualificações aceitas sem correção material | ≥75% | 14 dias |
| Envios sem aprovação válida | 0 | contínuo |
| Tentativas após opt-out | 0 | contínuo |
| Disponibilidade inbox/webhook | ≥99,5% | mensal |
| Operadores ativos em 4 de 7 dias | ≥50% | primeira semana |

Eventos mínimos: onboarding, conexão, webhook aceito/rejeitado/deduplicado, conversa aberta, qualificação revisada/corrigida, rascunho, aprovação, envio, opt-out, mudança de etapa e kill switch. Sem conteúdo bruto nos eventos analíticos.

## Gates não funcionais

- **Segurança:** isolamento adversarial de tenant, MFA para Owner, sessão/cookies seguros, CSRF quando aplicável, rate limit, cofre de segredos e revisão AppSec.
- **Privacidade:** minimização, finalidade, retenção configurável, DSAR/exclusão rastreável e política publicada.
- **Confiabilidade:** webhook persiste antes de confirmar, jobs idempotentes com retry, backup/restore ensaiado e nenhuma perda em falha do provedor.
- **Performance:** p75 de navegação ≤2 s; novo inbound visível ≤5 s após processamento, excluída indisponibilidade Meta.
- **Acessibilidade:** alvo WCAG 2.2 AA; teclado, foco, nomes e estados que não dependem só de cor.
- **Responsividade:** caminho crítico de 360 px a desktop; mobile prioriza inbox, edição e aprovação.
- **Operação:** SLOs, alertas, runbooks, rollback e estado da integração antes do piloto não supervisionado.

## Lançamento

1. **Staging:** fluxo completo com Meta simulada, testes adversariais de tenancy, estados visuais e nenhum P0/P1.
2. **Design partner:** um workspace, uma conta Meta real, operadores nomeados e suporte síncrono; provar inbound→resposta, sem cruzamento de tenant, envio indevido ou contato após opt-out.
3. **Piloto fechado:** até cinco workspaces, on-call/rollback, restore, termos e métricas; erro crítico de entrega abaixo de 1%, excluindo indisponibilidade Meta comprovada.

Não é GA até haver evidência de isolamento, Meta real, recuperação, observabilidade, segurança, privacidade, acessibilidade e três pilotos. Acabamento visual é requisito de confiança, mas não substitui esses gates.

## Decisões abertas

| Decisão | Dono | Gate |
|---|---|---|
| Identidade e MFA | Arquitetura + Segurança | antes de implementar auth |
| Backend Python, workers e banco | Arquitetura + DevOps | antes do deploy |
| Aprovação de todo envio ou por papel | Produto + cliente | antes do design partner; padrão: todo envio |
| Retenção de conteúdo/anexos | Privacidade + cliente | antes de dados reais |
| Preço do SaaS | Produto + FinOps + Billing | antes do piloto fechado |
| Estratégia desktop/web futura | Produto + Arquitetura | após o design partner |

## Definição de pronto

Um operador novo consegue, em navegador suportado, autenticar, configurar a operação, conectar conta autorizada, receber uma DM, compreender/corrigir a qualificação, editar rascunho, obter aprovação, enviar uma única resposta e registrar a próxima ação; um gestor audita o percurso; e testes provam que outro workspace não lê nem altera nenhuma parte do fluxo.
