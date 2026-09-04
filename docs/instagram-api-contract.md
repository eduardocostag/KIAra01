# Contrato da Instagram Messaging API para a Kiara

Status: contrato isolado; **não conectado ao runtime/UI nem aprovado para produção**. Revisão:
2026-09-04.

## Decisão de plataforma

A Kiara usará somente a Instagram API oficial da Meta e webhooks oficiais. Scraping, automação de
navegador, compartilhamento de senha e simulação do app Instagram ficam fora do produto. O
lançamento B2C depende de conta profissional elegível, aplicativo Meta, permissões aprovadas e
conformidade com as políticas e janelas de mensagem vigentes.

Há duas jornadas de autenticação documentadas pela Meta. Para integração nova, este contrato adota
**Instagram API with Instagram Login** (`graph.instagram.com`) e não mistura tokens, permissões ou
endpoints da jornada baseada em Facebook Login. A versão Graph é configuração obrigatória (`vNN.0`),
nunca `latest`.

Fontes oficiais a revalidar na versão escolhida antes do go-live:

- [Messaging API](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api)
- [Instagram Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login)
- [Webhooks da Instagram Platform](https://developers.facebook.com/docs/instagram-platform/webhooks)
- [Webhooks da Graph API](https://developers.facebook.com/docs/graph-api/webhooks/getting-started)
- [Erros da Graph API](https://developers.facebook.com/docs/graph-api/guides/error-handling)

Nota de evidência: em 2026-09-04, a coleta automatizada dessas páginas recebeu HTTP 429 da Meta. Os
links são canônicos, mas permissões, versão, limites e políticas devem ser conferidos manualmente no
painel/documentação Meta antes da revisão do app e ativação do cliente.

## OAuth, token e permissões

- OAuth ocorre no backend; `client_secret` e tokens nunca entram em logs, conversas, UI ou instalador.
- `state` aleatório, de uso único e associado à sessão deve ser comparado de forma segura.
- Solicitar apenas `instagram_business_basic` e `instagram_business_manage_messages`; qualquer nova
  permissão exige revisão. Não misturar nomes da jornada Facebook Login.
- Guardar token em cofre/credential manager junto de conta, app, escopos, emissão/expiração e última
  validação. Revogação deve parar envios e produzir `reauth_required`.
- Operação real exige Live mode, nível de acesso/permissão e eventual App Review/Business Verification
  exigidos pela Meta; Development mode não equivale a disponibilidade para o cliente.

## Webhook

No GET, aceitar `hub.mode=subscribe`, comparar `hub.verify_token` e devolver `hub.challenge` como
corpo `200`; falha recebe `403`, sem ecoar o token. No POST, validar `X-Hub-Signature-256` como
`sha256=<HMAC-SHA256(app_secret, raw_body)>` sobre os bytes exatos, antes do JSON, com comparação
constante. Assinatura inválida recebe `401/403` e não é processada.

Persistir evento/deduplicação e responder `200` rapidamente; IA e replies pertencem a job/outbox.
Entrega é pelo menos uma vez e pode estar fora de ordem: deduplicar por
`(instagram_account_id, message.mid)`; eventos sem `mid`, pelo hash do envelope.

```json
{"object":"instagram","entry":[{"id":"<account-id>","time":1720000000,
"messaging":[{"sender":{"id":"<ig-scoped-id>"},"recipient":{"id":"<account-id>"},
"timestamp":1720000000000,"message":{"mid":"<message-id>","text":"Oi"}}]}]}
```

Campos desconhecidos ficam no evento bruto. `read`, delivery, postback, reação, anexos, referrals e
ecos não podem virar texto inbound por acidente. O parser inicial normaliza somente `message` e expõe
`is_echo`; o consumidor ainda deverá descartar ecos.

## Envio de texto

```http
POST https://graph.instagram.com/{graph-version}/{instagram-account-id}/messages
Authorization: Bearer <token>
Content-Type: application/json

{"recipient":{"id":"<ig-scoped-id>"},"message":{"text":"Olá"}}
```

Sucesso requer HTTP 2xx e `message_id`. O destinatário vem de interação autorizada/webhook, não de
enumeração. Aplicar as restrições vigentes de início de conversa, janela, conteúdo e elegibilidade;
não prometer cold outreach arbitrário pela API.

A Meta não é tratada como provedora de chave de idempotência nesse envio. Criar
`outbound_action_id` local e único antes do POST, usar outbox
`prepared -> approved -> sending -> sent|failed|unknown` e salvar `message_id`. Timeout após POST é
ambíguo: marcar `unknown` e reconciliar/pedir decisão, sem reenvio cego. O adaptador não transmite um
header `Idempotency-Key` não documentado.

## Erros, limites e retries

Preservar `error.code`, `error.error_subcode`, `error.message`, `error.fbtrace_id`, HTTP status e
request ID local, sem token/PII no log. `401/403` exige reautenticação/permissão; `400` costuma ser
terminal após validação; `429` e `5xx` admitem backoff exponencial com jitter e tentativas limitadas,
respeitando orientação/header Meta. Timeout de POST continua ambíguo.

Não fixar quota numérica: limites variam por produto, versão, acesso e conta. Capturar os headers de
uso retornados e reduzir consumo antes da saturação. `429` abre circuito temporário; nunca contornar
limites com vários tokens/contas.

## Gate de lançamento

O adaptador cobre handshake, assinatura, parsing básico, Send API de texto e erro. Faltam endpoint
TLS público, subscription real, OAuth/refresh/revogação, cofre, outbox/ledger, demais eventos,
observabilidade, retenção/exclusão LGPD e testes sandbox/E2E.

Para dizer “apta ao Instagram”: app e conta configurados; permissões aprovadas; webhook assinado
verificado ponta a ponta; inbound, deduplicação e reply testados com conta autorizada; kill switch;
aprovação humana por envio; auditoria; retenção/exclusão; e falhas de token, duplicata, ordem, 429,
5xx e timeout ambíguo comprovadas. Até lá: **contrato e adaptador local prontos para integração**, não
canal em produção.
