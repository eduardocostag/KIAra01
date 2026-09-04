# Evidência E2E — piloto Instagram B2C

Data: 2026-09-04  
Escopo: webhook → persistência → qualificação → rascunho → aprovação humana → envio simulado.

## Estratégia

A suíte `tests/test_instagram_e2e.py` usa os componentes reais de orquestração,
qualificação, governança e os bancos SQLite. Somente a fronteira HTTP da Meta é
substituída por `ClosedMetaTransport`, um objeto em memória que não importa nem abre
clientes de rede. Assim, nenhuma mensagem real pode ser enviada durante os testes.

Os cenários cobertos são:

- assinatura válida, persistência, qualificação, rascunho e entrega somente após
  aprovação humana nominal e habilitação explícita do kill switch;
- reinício entre rascunho e aprovação, comprovando fail-closed sem destinatário em memória;
- HTTP 429, 500 e 503, persistindo `retry_wait`, tentativa e próximo horário de retry;
- opt-out recebido depois do rascunho, cancelando a ação pendente antes do HTTP;
- assinatura forjada, sem persistência e sem chamada ao transporte.

## Critério de liberação

Execute:

```powershell
pytest -q tests/test_instagram_e2e.py
pytest -q tests/test_instagram_e2e.py --count=10
```

O segundo comando exige o plugin `pytest-repeat`; na ausência dele, execute o primeiro
comando dez vezes no pipeline. O gate é: todas as execuções verdes, zero retry de teste
e `ClosedMetaTransport.calls == []` em todos os caminhos bloqueados.

Este gate valida o piloto local e a política de não envio acidental. Ele não substitui
um teste de contrato em ambiente sandbox oficial da Meta, que deve usar conta de teste,
credenciais não produtivas e destinatários explicitamente autorizados.

## Resultado observado

Em 2026-09-04, a suíte passou **10 execuções consecutivas**, sem retry:

- 70 casos executados no total (7 cenários × 10 repetições);
- 70 aprovados, 0 falhas, 0 flakes observados;
- duração por execução entre 0,41 s e 0,58 s;
- nenhuma chamada de rede real: toda entrega ficou confinada ao transporte em memória.
