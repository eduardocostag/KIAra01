# Governança de DMs B2C no Instagram

## 1. Resumo do processo

- **Processo:** `Instagram DM inbound → qualificação → rascunho → preview → aprovação → envio`.
- **Objetivo:** responder e qualificar consumidores que iniciam contato no Instagram, sem permitir que a Kiara envie mensagens externas sem revisão humana.
- **Sistemas:** Instagram/Meta (canal e fonte do evento), Kiara (qualificação e rascunho), operador humano (aprovação) e SQLite local (estado/auditoria).
- **Fonte de verdade:** o Instagram é a fonte da mensagem e do resultado de entrega; a Kiara é a fonte do estado interno de aprovação. O conector deve reconciliar o resultado da API antes de marcar `sent`.

## 2. Avaliação de auditoria

- **Economia de tempo:** alta e recorrente na triagem, qualificação e composição. O ganho real deve ser medido no piloto.
- **Criticidade dos dados:** alta. Há dados pessoais, intenção de compra e comunicação em nome do cliente.
- **Risco de dependência:** médio/alto. API, permissões, webhooks, limites, indisponibilidade e políticas da Meta são dependências externas.
- **Escalabilidade 1×–100×:** aceitável apenas com event ID único, claim transacional, retry limitado, rate limiting e fila observável. SQLite atende piloto de instância única; multi-instância exige banco/fila compartilhados.

## 3. Veredito

**APPROVE AS PILOT** — autonomia nível 3. A Kiara observa, qualifica e prepara a ação; **checkpoint humano obrigatório por DM externa**. Envio autônomo permanece bloqueado.

## 4. Justificativa

O inbound B2C pelo Instagram tem valor comercial direto, mas a integração concentra risco externo, privacidade e reputação. Opt-out prevalece sobre aprovação anterior; kill switch e falhas de estado bloqueiam envio. A aprovação não equivale a sucesso: somente a confirmação da API encerra a ação como enviada.

## 5. Arquitetura recomendada

1. **Trigger:** webhook oficial da Meta, validado por assinatura e com `event_id` persistido.
2. **Validação:** conta permitida, evento suportado, timestamp aceitável, identidade e texto não vazios.
3. **Normalização:** handle convertido em hash; texto bruto fica no armazenamento de conversa sujeito à retenção, não no log de governança.
4. **Lógica:** detectar opt-out antes da qualificação; qualificar e gerar um rascunho vinculado ao evento.
5. **Preview/aprovação:** apresentar texto, destinatário, contexto e ação ao operador. Aprovação humana nominal e individual.
6. **Ação externa:** conector chama `claim_delivery`; só recebe trabalho se estiver aprovado, não suprimido, no tempo de retry e com kill switch habilitado.
7. **Validação:** reconciliar ID/status retornado pela Meta e então chamar `finish_delivery(success=True)`.
8. **Auditoria:** evento, action ID, transição, ator e timestamp; sem mensagem, handle ou token em claro.
9. **Erro:** até três tentativas para erros transitórios, backoff 30/60 s; erros permanentes falham sem retry.
10. **Fallback:** operador copia o rascunho e envia manualmente no Instagram, registrando reconciliação manual; em dúvida, não enviar.

Estados: `pending_approval → approved → sending → sent`; erro transitório usa `retry_wait`; erro terminal usa `failed`; opt-out usa `cancelled_opt_out`. Um evento cria no máximo uma ação e uma ação só pode ser reivindicada uma vez por tentativa.

## 6. Padrão de implementação

- **Workflow:** `PILOT-INSTAGRAM-InboundQualification-DraftApproval-v0.1`.
- **Owner de negócio:** gestor comercial B2C. **Owner técnico:** responsável pela Kiara/integração.
- **SOPs:** kill switch; aprovar/rejeitar; opt-out; recuperar `sending`; reconciliar envio manual; rotacionar token; incidente.
- **Log mínimo:** workflow/versão, timestamp, origem, IDs, estado, ator e classe curta do erro. Nunca token ou conteúdo da DM.
- **Testes:** caminho feliz, input inválido, falha Meta, evento duplicado, claims concorrentes, opt-out, kill switch, limite de tentativas, reinício e reconciliação.
- **Monitoramento:** backlog/idade por estado, duplicidade, falha/retry, opt-out, tempo de aprovação e confirmação.

## 7. Pré-condições e riscos

- Conta profissional, app Meta aprovado, permissões mínimas e webhook assinado.
- Aprovação do cliente para conta, operadores, janela de atendimento, retenção e conteúdo.
- Piloto em uma conta, poucos operadores e limite conservador; sem prospecção fria ou massa.
- Kill switch inicia **desligado** e só é habilitado após teste ponta a ponta em conta de teste.
- O gate é isolado: o conector ainda precisa chamá-lo antes de toda entrega. Sem wiring e evidência E2E, Instagram não está pronto para produção.
- Processo morto em `sending` exige reconciliação com a Meta antes de retry; nunca reenviar no escuro.
- Reauditar em mudanças da Meta, aumento de volume/erros ou correções manuais recorrentes.
