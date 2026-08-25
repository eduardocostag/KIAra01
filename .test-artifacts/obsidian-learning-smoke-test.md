---
tags: [kiara, aprendizado-aprovado]
source: feedback-explicito
created_at: 2026-08-25T19:43:21.364134+00:00
---

# Explique com rigor mas de forma clara por

## Solicitação

Explique, com rigor mas de forma clara, por que um sistema distribuído pode ter consistência eventual e ainda assim preservar invariantes financeiros. Dê um exemplo com idempotência, ledger de dupla entrada e reconciliação.

## Resposta e processo aprovado

## Consistência Eventual e Invariantes Financeiros: Por Que Funcionam Juntos

A ideia central é separar **consistência de *estado* (eventual)** de **consistência de *invariantes* (forte, por construção)**. Um sistema distribuído abre mão de visibilidade instantânea global para ganhar disponibilidade e latência, mas **não abre mão da correção contábil**. Isso é possível porque cada mutação financeira é desenhada para ser **autocontida, repetível sem efeito colateral e verificável globalmente** — três propriedades que, combinadas, garantem que "ativos = passivos + patrimônio líquido" valha a todo momento, mesmo quando réplicas discordam temporariamente.

---

### Os Três Pilares Mecânicos

| Pilar | O que garante | Onde atua |
|-------|---------------|-----------|
| **Idempotência** | Reprocessar a mesma operação não altera o resultado final | Camada de entrada (gateway, API) |
| **Partida dobrada (double-entry)** | Toda mutação de saldo é par (débito + crédito = 0) → soma global invariante | Camada de domínio / ledger local |
| **Reconciliação** | Detecta e corrige divergências entre visões parciais antes que afetem saldos expostos | Processo assíncrono (job, stream, CDC) |

---

### Exemplo Concreto: Transferência entre Shards/DC Diferentes

**Cenário**  
- **Shard A (DC-1)**: conta `1001` (origem, saldo R$ 1.000)  
- **Shard B (DC-2)**: conta `2002` (destino, saldo R$ 500)  
- Transferência de **R$ 200** iniciada pelo cliente.  
- Rede particiona no meio do processo.

#### 1. Idempotência na Entrada
O cliente envia:
```json
{
  "transfer_id": "txn-777",
  "idempotency_key": "client-abc-20260825-001",
  "from": "1001",
  "to": "2002",
  "amount": 200
}
```
O gateway **desduplica** pela `idempotency_key` antes de persistir. Se o cliente reenvia (timeout, retry), o sistema ignora duplicatas → **exatamente uma entrada no ledger**.

#### 2. Escrita Local com Partida Dobrada (em cada shard)
Cada shard valida **localmente** que a soma dos lançamentos da transação é zero. Se o shard remoto estiver indisponível, o shard local **não commita** — a transação fica *pendente* num *transactional outbox*.

**Shard A (origem) — commit atômico:**
| entry_id | account | debit | credit | transfer_id |
|----------|---------|-------|--------|-------------|
| e1 | 1001 | 200 | 0 | txn-777 |
| e2 | 9999 (suspense/clearing) | 0 | 200 | txn-777 |

**Shard B (destino) — commit atômico (quando mensagem chega):**
| entry_id | account | debit | credit | transfer_id |
|----------|---------|-------|--------|-------------|
| e3 | 9999 (suspense/clearing) | 200 | 0 | txn-777 |
| e4 | 2002 | 0 | 200 | txn-777 |

> **Invariante local**: Em *cada* ledger, Σ(débito) = Σ(crédito) para o mesmo `transfer_id`.  
> **Invariante global**: A conta *suspense/clearing* (9999) atua como **ponte contábil** — seu saldo líquido deve ser zero quando a transferência completa.

#### 3. Consistência Eventual Ocorre Aqui
Entre o commit no Shard A e o commit no Shard B, a **visão agregada está inconsistente** (conta 9999 tem –200 num lado, +200 no outro).  
**Mas nenhuma invariante financeira foi violada**: nenhum dinheiro foi criado ou destruído; apenas a *liquidação* está em trânsito. O ledger já registra a intenção imutável.

#### 4. Reconciliação Fecha o Ciclo
Um job periódico (ou CDC + stream processor) compara visões consolidadas:

```sql
-- Visão global por transferência
SELECT transfer_id,
       SUM(CASE WHEN shard='A' THEN debit - credit ELSE 0 END) AS net_a,
       SUM(CASE WHEN shard='B' THEN debit - credit ELSE 0 END) AS net_b
FROM ledger_entries
GROUP BY transfer_id
HAVING net_a + net_b <> 0;  -- divergência detectada
```

- **Resultado não nulo** = divergência (mensagem perdida, bug, fraude).  
- **Ação automática**: reexecuta o lado faltante (idempotente — `txn-777:in` já existe ou é aplicado uma vez).  
- **Falha irreversível** (ex.: conta destino encerrada): emite alerta para investigação manual + estorno compensatório (nova transferência idempotente inversa).

---

### Por Que os Invariantes Financeiros Não Quebram

| Invariante Financeiro | Garantia no Modelo |
|------------------------|---------------------|
| **Conservação de valor** (entradas = saídas) | Partida dobrada *local* por transação + soma global = 0 |
| **Não criação/destruição de dinheiro** | Idempotência impede duplicação; reconciliação impede perda |
| **Saldo nunca negativo sem autorização** | Validação *local* no shard de origem antes de emitir evento |
| **Auditoria completa** | Log imutável (append-only) de comandos + eventos + journals por shard |
| **Recuperabilidade** | Reconciliação detecta *qualquer* desvio, mesmo meses depois |

---

### Onde a Consistência Forte Ainda É Necessária (Ressalvas Importantes)

1. **Limite de crédito / cheque especial** — decisão *síncrona* no shard de origem (não pode depender de réplica remota).  
2. **Regra "conta não pode fechar com saldo ≠ 0"** — validação no momento do fechamento (lock na conta).  
3. **Saldos disponíveis para saque** (overdraft protection) — exige leitura *strongly-consistent* ou reserva pessimista.  
4. **Limites regulatórios em tempo real** (LCR, large exposure) — agregações que não toleram janela de inconsistência.  
5. **Liquidação final (settlement)** — o momento em que a conta suspense zera *deve* ser atomicamente consistente.

---

### Resumo em Uma Frase

> **Consistência eventual no *estado* não viola invariantes financeiros quando cada mutação local respeita a partida dobrada, a entrada é idempotente e a reconciliação garante convergência global — o sistema troca latência por disponibilidade sem abrir mão de correção contábil.**

---

### Incertezas Declaradas (conforme análises dos especialistas)

- O exemplo assume *message broker* com **at-least-once + ordenação por chave de partição** (`transfer_id`). Se o broker não garante ordenação, a reconciliação precisa de *vector clocks* ou *sequence numbers* por conta — o princípio permanece, a implementação fica mais complexa.  
- A latência da reconciliação define a **janela de exposição** a saldos "desatualizados" para o usuário; SLAs de negócio ditam se job noturno basta ou se CDC near-real-time é obrigatório.  
- Testes de caos (injeção de falhas de rede, crash de shard, duplicação de mensagens) são indispensáveis para validar que a reconciliação *de fato* corrige todos os cenários de borda.
