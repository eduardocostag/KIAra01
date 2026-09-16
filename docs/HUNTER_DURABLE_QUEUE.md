# Fila durável do Hunter

O Hunter registra cada pesquisa confirmada em `jobs` (payload protegido por RLS)
e em `hunter_work_queue` (índice operacional contendo apenas IDs e horários).
Resultados, histórico e credenciais nunca saem do contexto da organização.

## Ativação

1. Aplique `services/api/migrations/0007_hunter_durable_queue.sql` no PostgreSQL.
2. Configure `CRON_SECRET` no projeto da API da Vercel. Como alternativa para
   um worker próprio, configure `KIARA_WORKER_TOKEN`.
3. Publique a API usando `services/api/vercel.json`; o cron chama o worker a
   cada minuto.

## Comportamento

- confirmação retorna rapidamente e não depende da duração do scraping;
- cada execução recebe lease de quatro minutos;
- leases vencidos podem ser retomados depois de queda do processo;
- falhas transitórias usam até 12 tentativas, com backoff de 15 segundos até
  15 minutos;
- `FOR UPDATE SKIP LOCKED` permite vários workers sem reivindicar o mesmo item;
- a interface também pode acelerar e retomar a pesquisa enquanto estiver aberta.

Escalar workers aumenta vazão, mas não remove limites impostos pelas próprias
fontes. A fila garante que a solicitação seja preservada e retomada; ela não
autoriza contornar bloqueios, login, CAPTCHA ou termos de serviço.
