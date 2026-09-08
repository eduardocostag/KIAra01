# Contrato da API web — Kiara Lead Intelligence

Status: **baseline v1 para implementação; não comprova backend implantado**  
Responsável: `api-platform-engineer`  
Data: 2026-09-05

`packages/contracts/openapi.yaml` é a fonte de verdade OpenAPI 3.1 para health, identidade, inbox, detalhe, rascunho, aprovação humana, qualificação e pipeline. Implementação, referência e cliente TypeScript devem ser gerados ou validados contra ele.

## Convenções congeladas em v1

- `/v1`, JSON UTF-8, `snake_case`, RFC 3339 UTC e IDs opacos;
- bearer JWT; apenas `/health/*` é público;
- organização derivada da identidade e membership verificadas; nunca aceitar `organization_id` do cliente;
- paginação por cursor opaco;
- erro único: `error.code`, `error.message`, `error.request_id` e `error.details` opcional;
- comandos repetíveis exigem `Idempotency-Key` tenant-scoped por ao menos 24 horas; retry idêntico devolve o resultado original e payload diferente com a mesma chave retorna `409`;
- mutações versionadas usam `ETag` e `If-Match`; versão divergente retorna `412`, header ausente retorna `428`;
- `429` inclui `Retry-After` e `X-RateLimit-*`.

Recurso de outro tenant responde `404`. Leitura exige `viewer+`, rascunho/qualificação/pipeline `operator+`, e aprovação `outbound.approve`. Aprovar registra ator, versão e hash; não envia mensagem.

## Compatibilidade

Endpoints e campos opcionais novos são aditivos em v1. Remover/renomear campo, mudar tipo, tornar entrada obrigatória, retirar enum ou mudar semântica HTTP exige `/v2`, guia, headers `Deprecation`/`Sunset`, janela pública recomendada de 6–12 meses e medição de uso. Capabilities são extensíveis; demais enums são fechados e exigem revisão de SDK antes de crescer.

## Gates seguintes

1. lint e referências OpenAPI em CI;
2. conformidade request/response no ASGI;
3. diff automático bloqueando breaking changes;
4. geração determinística do cliente TypeScript;
5. testes cross-tenant, replay idempotente e concorrência `If-Match`;
6. quickstart executável antes da exposição externa.

OAuth, webhook Meta, envio e consulta de jobs ficam fora deste recorte mínimo e devem entrar apenas como mudanças aditivas coerentes.
