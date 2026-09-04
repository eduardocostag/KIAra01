# Relatório de testes — API Instagram B2C

Data: 2026-09-04  
Responsável: API Tester  
Escopo: adaptador Graph, webhook inbound, qualificação B2C e governança de entrega.  
Restrição: validação totalmente local, com doubles; nenhuma chamada à Meta foi realizada.

## Resultado

**PASS para integração isolada e piloto assistido; NO-GO para produção real até validar credenciais, permissões, versão Graph, limites e webhook em ambiente Meta controlado.**

Execução focal:

```text
pytest -q tests/test_instagram_integration.py tests/test_instagram_b2c_flow.py \
  tests/test_instagram_governance.py tests/test_instagram_pilot.py
24 passed in 0.73s

ruff check <arquivos focais>
All checks passed!
```

## Cobertura e comportamento observado

| Área | Evidência | Resultado |
|---|---|---|
| Autenticação inbound | HMAC SHA-256 sobre bytes exatos; assinatura ausente, alterada ou inválida é rejeitada antes do pipeline | PASS |
| Contrato webhook | objeto/entry validados; JSON inválido vira erro de contrato; eventos incompletos e timestamps inválidos são ignorados com segurança | PASS |
| Eco e conteúdo não textual | não persistem pessoa, consentimento, touchpoint ou ação | PASS |
| Idempotência | redelivery do mesmo `mid` retorna `duplicate`, reutiliza a ação e não repete touchpoint/qualificação | PASS |
| Opt-out | bloqueia rascunho; supressão persistente cancela inclusive ação aprovada anteriormente | PASS |
| Qualificação | pedido de preço com pontuação (`preço?`) é reconhecido; dados do cliente permanecem evidência não confiável | PASS |
| Aprovação | envio exige aprovação humana nominal e kill switch habilitado; Kiara não autoaprova | PASS |
| Concorrência | duas instâncias concorrentes conseguem no máximo um claim de entrega | PASS |
| Erros/limites | HTTP 429 é classificado como retryable; 5xx já segue a mesma política; ausência de `message_id` falha fechada | PASS |
| Retry | tentativas limitadas, backoff e estado terminal `failed`; ação aprovada pode ser retomada após kill switch | PASS |
| Segredos/auditoria | token não é persistido pelo gate; auditoria não grava conteúdo nem identificador direto do destinatário | PASS |

## Correções realizadas durante QA

- Validação estrutural de `account_id`, sender, recipient e timestamp antes da normalização.
- Conversão de JSON malformado em `InstagramContractError` estável.
- Curto-circuito idempotente antes de repetir efeitos no banco de consumidores.
- Retomada de ações já aprovadas e em `retry_wait`, sem exigir nova aprovação impossível.
- Tokenização Unicode para detectar termos comerciais seguidos de pontuação.

## Riscos e gates restantes

- Não foram medidos p95, throughput, erro sob carga ou capacidade 10x: não existe endpoint/runtime implantado no escopo deste teste.
- A classificação retryable cobre transporte HTTP 429/5xx. Códigos Meta transitórios retornados com outro status devem ser confirmados contra a versão Graph efetivamente aprovada antes do go-live.
- O mapa destinatário/ação é intencionalmente apenas em memória. Após reinício, a entrega falha fechada como `recipient_unavailable`; é necessário um procedimento de reconciliação operacional.
- Validar em ambiente Meta controlado: handshake GET, assinatura POST real, permissões da conta profissional, janela de mensagens, expiração/rotação do token, rate limits e resposta de opt-out.
- Executar teste de carga somente em sandbox/ambiente autorizado, com limites acordados; nunca contra clientes reais.

## Recomendação de liberação

Liberar apenas um piloto assistido, com kill switch inicialmente desligado, aprovação humana por mensagem, observabilidade e rollback. Produção comercial permanece condicionada aos gates Meta e de desempenho acima.
