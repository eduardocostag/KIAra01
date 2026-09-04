# Revisão AppSec — piloto B2C Instagram

Data: 2026-09-04. Escopo: boundary de webhook, parsing, replay, qualificação, aprovação e
conector isolado. Nenhuma chamada real à Meta foi executada.

## Resultado

O fluxo isolado está adequado para sandbox e piloto assistido depois das correções abaixo. Ele
não está aprovado para produção até fechar os gates residuais. Mensagens do Instagram são dados
não confiáveis: não concedem permissão, não aprovam envio e não alteram o kill switch.

## Correções verificáveis

- HMAC-SHA256 sobre os bytes exatos, comparação constante, formato hexadecimal estrito e corpo
  limitado a 64 KiB antes do JSON.
- Limites de entries, eventos e texto; IDs de plataforma, timestamp, remetente e destinatário são
  validados. JSON inválido falha sem persistência.
- O account ID e o recipient do evento devem coincidir com a conta configurada. Isso impede que um
  webhook autenticado de outra conta contamine o tenant local.
- A chave de replay passou a ser `account_id:message_id`; uma reentrega não repete qualificação
  nem cria novo rascunho.
- O endpoint de envio é construído internamente com host fixo `graph.instagram.com`; nenhum URL do
  webhook chega ao cliente HTTP, removendo o sink de SSRF nesse fluxo.
- Destinatários ficam fora do audit/governance DB e o audit não grava mensagem, token ou PII; usa
  somente fingerprint e metadados de estado.
- Envio continua fail-closed: aprovação humana nominal, kill switch desligado por padrão,
  supressão revalidada no claim e aprovação expira em 15 minutos.
- `CustomerRoom.to_prompt_payload()` separa instruções de `untrusted_data`; o draft padrão não
  executa nem ecoa instruções da DM. Qualquer futuro gerador LLM deve consumir exclusivamente esse
  envelope e retornar schema validado.

## Ameaças e requisitos

| Ameaça | Controle | Evidência |
|---|---|---|
| Spoofing/tampering do webhook | HMAC antes do parse e vínculo à conta | testes de assinatura e conta errada |
| DoS por payload | tetos de bytes/coleções/texto | testes de 64 KiB, 101 entries e texto longo |
| Replay/duplicidade | chave composta e ledger único | teste de redelivery sem nova qualificação |
| Prompt injection | dado isolado, gate fora do modelo | contrato do payload e aprovação persistente |
| Vazamento de PII/segredo | audit sem conteúdo/token, IDs em memória | schema e `_audit` |
| SSRF | host/rota fixos | teste do endpoint oficial versionado |
| Envio indevido | approval TTL, opt-out, claim transacional, kill switch | testes de governança |

## Gates bloqueantes antes de produção

1. Autenticar o operador e derivar `actor` de uma sessão confiável; hoje uma string nominal não
   prova identidade nem papel. Fix-before-production, CWE-306/CWE-862.
2. Usar secrets manager/Windows Credential Manager e rotação; `.env.example` é apenas contrato
   sem valores. Confirmar que logs do transporte redigem headers e bodies.
3. Implementar endpoint HTTPS com limite também no proxy, rate limiting, timeout e métricas; esta
   camada de transporte ainda não existe no runtime.
4. Resolver recovery do recipient após restart com armazenamento cifrado e retenção curta, ou
   manter a reconciliação manual fail-closed documentada.
5. Testar ponta a ponta em conta Meta autorizada, incluindo janela de mensageria, opt-out concorrente,
   kill switch durante I/O e resposta ambígua/timeout. Um kill switch não cancela bytes já aceitos
   pela API; reconciliação continua obrigatória.
6. Criar retenção/exclusão LGPD para touchpoints contendo a mensagem e restringir acesso ao banco
   local. O audit é minimizado, mas o ConsumerStore guarda conteúdo por necessidade funcional.

## Validação local

`pytest -q tests/test_instagram_integration.py tests/test_instagram_pilot.py
tests/test_instagram_governance.py tests/test_instagram_b2c_flow.py` → **25 passed**.

`ruff check app/integrations/instagram.py app/consumers/instagram_pilot.py
app/automation/instagram_governance.py tests/test_instagram_integration.py
tests/test_instagram_pilot.py tests/test_instagram_governance.py` → **aprovado**.
