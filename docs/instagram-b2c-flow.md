# Fluxo B2C inbound pelo Instagram

## Objetivo de lançamento

A Kiara recebe eventos previamente autenticados por uma integração oficial do
Instagram, registra a pessoa e sua mensagem, qualifica conservadoramente e prepara
uma resposta para revisão humana. Este fluxo **não envia mensagens**.

## Contrato da aplicação

`InstagramB2CFlow.process()` recebe o envelope normalizado esperado pelo
`MetaLeadAdapter`, com `origin=instagram_inbound`. O evento precisa conter:

- ID escopado do remetente e identidade social;
- data/hora com fuso;
- consentimento explicitamente booleano, anterior à captura;
- origem, finalidade e canal `instagram` do consentimento;
- mensagem inbound e, quando aplicável, campanha.

O handler da integração é responsável por validar assinatura, autenticidade,
tenant/conta e replay antes de chamar este serviço. Payloads de curtida, follow ou
scraping público não pertencem a este caminho.

## Sequência

1. Validar limites, origem, maioridade, identidade e consentimento.
2. Exigir autorização específica para Instagram.
3. Deduplicar a pessoa pelo ID escopado e persistir consentimento e touchpoint.
4. Detectar opt-out explícito; se presente, revogar imediatamente o consentimento.
5. Qualificar via `ConsumerIntelligenceService`.
6. Gerar somente `InstagramDraft`, marcado `requires_human_approval=True` e
   `sent=False`.

## Fatos, inferências e desconhecidos

A mensagem autenticada é registrada como fato atribuído ao evento
`instagram://inbound/{external_id}`. Pedido de preço ou DM iniciada alimenta apenas
uma inferência de intenção; não prova necessidade, urgência ou capacidade. Campos
comerciais ausentes continuam desconhecidos e o rascunho padrão pergunta pelo
primeiro deles. A classificação não inventa score nem transforma uma DM em SQL.

## Opt-out e entrega

Mensagens como “pare”, “não quero”, “sair” e “unsubscribe” gravam a revogação,
classificam a pessoa como desqualificada e impedem a chamada ao gerador de texto.
Uma futura entrega real deve existir fora deste módulo e, imediatamente antes do
envio, revalidar consentimento, supressão, aprovação, kill switch e idempotência.

## Evidência local

Os testes em `tests/test_instagram_b2c_flow.py` cobrem o percurso autorizado com
mock do gerador, separação fato/inferência, persistência inbound, canal incorreto e
opt-out sem geração nem envio. Eles não validam a API real da Meta.
