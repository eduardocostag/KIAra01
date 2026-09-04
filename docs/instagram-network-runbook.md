# Runbook de rede — piloto B2C Instagram

Data da revisão: 2026-09-04. Escopo: webhook HTTPS, DNS, TLS, proxy, timeouts,
limites, observabilidade e rollback. Este documento não autoriza deploy nem chamadas reais.

## Decisão e estado de prontidão

**Não publicar o desktop da Kiara na Internet.** Não criar port forwarding no roteador, regra
inbound no Windows Firewall, DMZ residencial, DDNS apontando para a estação ou túnel que entregue
requisições públicas diretamente ao processo desktop.

O código atual valida `X-Hub-Signature-256` sobre os bytes exatos e rejeita corpos acima de 64 KiB,
mas não contém listener HTTP público, fila durável nem supervisor de serviço. Assim, a topologia
aprovável para o piloto é:

```text
Meta Webhooks
  -> DNS público dedicado
  -> edge/WAF HTTPS gerenciado
  -> relay stateless e isolado (validação HMAC + persistência idempotente)
  -> fila/outbox durável
  <- conexão TLS de saída iniciada pela Kiara
  -> processamento local, rascunho e aprovação humana
  -> Graph API por HTTPS de saída (somente após aprovação)
```

O relay não qualifica leads, não gera mensagens e não envia DMs. Ele autentica o webhook usando o
corpo bruto, valida conta e tamanho, grava de forma idempotente e responde rapidamente. O desktop
faz apenas conexões de saída em TCP/443 para buscar eventos e confirmar processamento. Uma fila
gerenciada ou banco transacional pequeno pode cumprir a fronteira durável, desde que tenha
criptografia, retenção curta, controle de acesso e operação na região aprovada pelo responsável
por privacidade.

Até relay, fila, worker e credenciais estarem implantados e testados ponta a ponta com uma conta
Meta autorizada, o status é **NO-GO para produção; sandbox/dry-run apenas**.

## DNS e TLS

- Usar nome exclusivo, por exemplo `instagram-webhook.<dominio-do-cliente>`. Não reutilizar o host
  do site ou expor IP residencial/da estação.
- Publicar `A/AAAA` ou `CNAME` somente para o provedor do edge. Se IPv6 não estiver efetivamente
  servido e filtrado, não publicar `AAAA`.
- TTL sugerido no corte: 300 s; depois de estabilizar, 3600 s. CAA deve autorizar a CA usada pelo
  edge. DNSSEC é recomendado quando suportado pelo registrador/provedor.
- Certificado público válido, cadeia completa e renovação automática. Permitir TLS 1.2 e 1.3;
  desabilitar TLS legado, cifras fracas e renegociação insegura. Redirecionamento HTTP não substitui
  HTTPS: a callback cadastrada na Meta deve ser a URL HTTPS final.
- O edge termina TLS e usa TLS autenticado também até o relay. Nunca usar HTTP em rede pública ou
  compartilhar `app secret`, verify token ou access token com o proxy por logs/headers auxiliares.

## Rotas e política de borda

Expor somente:

- `GET /webhooks/instagram` para o handshake `hub.mode`, `hub.verify_token` e `hub.challenge`;
- `POST /webhooks/instagram` para eventos, exigindo `Content-Type: application/json` e
  `X-Hub-Signature-256`.

Todos os demais métodos e caminhos retornam `404/405`. O proxy deve preservar o corpo bruto sem
descompressão, reserialização JSON ou transformação antes do HMAC. Remover headers de cliente que
possam simular identidade interna e gerar um request ID no edge. Não registrar query string do GET,
pois ela contém o verify token.

Não depender de allowlist fixa de IPs da Meta sem uma fonte oficial e processo de atualização:
endereços podem mudar. A autenticação primária do POST é o HMAC; WAF, proteção DDoS, limites de
conexão e anomalia são camadas adicionais. O relay aceita somente o `instagram_account_id`
configurado para o tenant.

Política da estação:

- inbound da Internet: nenhum;
- outbound DNS apenas pelo resolvedor corporativo/local autorizado;
- outbound TCP/443 apenas para o relay/fila, `graph.instagram.com`, endpoints de autenticação
  estritamente necessários e serviços operacionais aprovados;
- proxy corporativo, se houver, não pode fazer inspeção TLS que quebre validação de certificado;
  suas CA e exceções devem ser administradas, nunca desabilitar verificação TLS no cliente.

## Orçamento de tempo, capacidade e falhas

Valores abaixo são limites internos defensivos, não quotas declaradas pela Meta:

| Trecho | Limite inicial | Comportamento |
|---|---:|---|
| leitura de headers | 5 s | fechar conexão lenta |
| corpo do webhook | 64 KiB | rejeitar antes de JSON; coerente com o adaptador |
| persistência + ACK | alvo < 2 s, máximo 5 s | responder `200` somente após gravação durável |
| conexão relay/fila pelo worker | 3 s | retry com jitter |
| chamada Graph: conexão | 3 s | erro transitório antes do envio |
| chamada Graph: resposta | 10 s; total 15 s | timeout após POST vira `unknown`, sem reenvio cego |

Configurar no edge limite de corpo igual a 64 KiB, máximo de headers de 16 KiB, no máximo 100
conexões simultâneas por instância e proteção adaptativa contra rajadas. Começar alertando, e não
bloqueando por uma quota estreita arbitrária, até medir tráfego legítimo. Uma salvaguarda inicial
de aplicação pode aceitar rajada de 100 eventos por conta e sustentar 10 eventos/s por conta;
excesso deve ser enfileirado ou receber `429` com `Retry-After`, nunca descartado silenciosamente.
Revisar esses valores após o primeiro dia de tráfego e teste de redelivery.

Para saída Graph, `429` e `5xx` recebem backoff exponencial com jitter e tentativas limitadas,
respeitando `Retry-After` e headers oficiais de uso. `401/403` abre incidente de credencial e bloqueia
envios. O circuit breaker deve impedir avalanche de retries. Falha da fila ou incerteza de
persistência faz o webhook falhar fechado; falha do desktop não perde evento, apenas acumula backlog.

## Segredos e logs

- App secret, verify token e access token ficam em secret manager; nunca em imagem, Git, query de
  log, linha de comando, crash dump ou banco em texto claro.
- Relay recebe somente app secret e verify token. O token de envio fica no componente outbound,
  com privilégio mínimo. Rotação deve aceitar uma janela controlada de segredo anterior/novo quando
  a plataforma permitir, seguida de revogação e teste.
- Logs contêm request ID, horário, status, latência, tamanho, hash/id do evento e conta
  pseudonimizada; nunca corpo, texto da DM, assinatura completa, token ou identificador do usuário.
- Alertas: taxa de 4xx/5xx, HMAC inválido, latência de ACK, idade/profundidade da fila, duplicatas,
  worker offline, certificado a 30/14/7 dias, DNS divergente, `429`, falhas TLS e envios `unknown`.

## Implantação guardada para o piloto

### Pré-checks

1. Confirmar domínio, owner, região de dados, conta profissional, app em modo correto e permissões.
2. Criar backup/export da configuração do edge, DNS e secrets; registrar o valor DNS anterior.
3. Verificar que não há NAT/port-forward, listener público ou regra inbound para a estação.
4. Executar testes locais de HMAC, corpo máximo, duplicata, eco, opt-out, kill switch e timeout.
5. Implantar relay e fila com envio desativado; validar health check privado e acesso mínimo.

### Ativação

1. Publicar DNS com TTL 300 e validar resolução por ao menos dois resolvedores externos.
2. Validar certificado, cadeia, hostname e TLS 1.2/1.3 de fora da rede do cliente.
3. Executar handshake usando credenciais de teste; confirmar que token/query não apareceu nos logs.
4. Enviar payload sintético assinado e assinatura inválida; comprovar ACK/persistência e rejeição.
5. Cadastrar callback na Meta e testar uma DM real entre contas autorizadas, mantendo kill switch
   desligado e resposta apenas como rascunho.
6. Habilitar worker para consumo, validar deduplicação/redelivery e somente então habilitar envios
   aprovados por uma janela assistida.

### Validação separada

- Controle: DNS correto; certificado válido; handshake `200`; segredo errado `403`; health privado.
- Dados: assinatura válida chega uma vez à fila; duplicata não repete efeitos; corpo alterado falha;
  backlog sobrevive a reinício do desktop; ACK ocorre após persistência.
- Saída: DNS/TLS para Graph; `401/403`, `429`, `5xx` e timeout simulados; nenhum retry cego de POST;
  kill switch bloqueia envio e aprovação nominal aparece na auditoria.
- Estação: varredura externa não encontra porta Kiara; Windows Firewall não possui nova regra inbound;
  conexões observadas são somente de saída.

### Rollback e gatilhos

Gatilhos: HMAC inválido aceito, perda/duplicação com efeito, PII/segredo em log, ACK p95 acima de 5 s,
fila sem durabilidade, certificado inválido, conta errada, envio sem aprovação ou taxa anormal de
erros.

1. Desligar o kill switch de envio imediatamente (estado seguro é desabilitado).
2. Pausar o worker, preservando fila e auditoria; não apagar eventos.
3. Remover/desabilitar a subscription do webhook na Meta ou trocar o DNS para a configuração
   anterior registrada. Reduzir tráfego no edge sem expor fallback local.
4. Revogar/rotacionar credenciais se houver suspeita; invalidar sessões e tokens afetados.
5. Exportar IDs/estado do backlog, classificar `unknown` e reconciliar manualmente antes de retomar.
6. Restaurar a versão anterior do relay/configuração, repetir validação e reativar gradualmente.

## Gate de hoje

Só declarar o canal apto para piloto assistido após evidência dos quatro caminhos: handshake real,
inbound assinado real, redelivery idempotente e resposta aprovada real. Para operação comercial,
também são obrigatórios monitoramento durante a janela, operador nomeado, rollback ensaiado e
reconciliação do backlog. Qualquer item ausente mantém **NO-GO** e o atendimento deve ocorrer
manualmente no Instagram, registrando a reconciliação na Kiara.
