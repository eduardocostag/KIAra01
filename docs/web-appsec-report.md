# Gate AppSec — Kiara Web

Data: 2026-09-05  
Escopo: `apps/web`, Clerk v7, Next.js 16, isolamento de workspace, modo demo e fronteira frontend/backend.

## Resultado

**Aprovado apenas para protótipo local. Não aprovado para produção.** A autenticação server-side e a derivação de tenant estão estruturadas corretamente, mas a API Python multi-tenant, RLS, verificação de token entre serviços e integração Clerk/Meta reais ainda não existem neste scaffold.

## Correções aplicadas

1. **Modo demo fail-open em produção self-hosted — corrigido.** Antes, somente `VERCEL_ENV` ou `KIARA_DEPLOYMENT_ENV` identificavam produção; um servidor com apenas `NODE_ENV=production` poderia aceitar demo. Agora runtime de produção também bloqueia demo, preservando apenas a fase de compilação local (`NEXT_PHASE=phase-production-build`).
2. **Divergência cliente/servidor no modo demo — corrigida.** O servidor aceitava `1`, `true` e `yes`, mas o provider cliente somente `true`. O modo é resolvido uma vez no Server Component e apenas o enum não sensível é passado ao cliente.
3. **Headers básicos ausentes — corrigido.** Removido `X-Powered-By`; adicionados `nosniff`, anti-framing, Referrer Policy, Permissions Policy e isolamento cross-origin.

## Controles confirmados

- `requireWorkspace()` exige sessão e organização Clerk no servidor.
- O identificador de workspace vem exclusivamente de `auth().orgId`; não há confiança em `workspaceId` vindo de query, formulário ou body.
- Configuração Clerk parcial e ausência total de autenticação falham fechado.
- Não foi encontrado `dangerouslySetInnerHTML`, manipulação de `innerHTML`, segredo hardcoded ou persistência de token em storage/cookie manual.
- O layout `/app/**` executa autorização no recurso, coerente com a recomendação local do Clerk v7 de não depender apenas de path matching no proxy.
- O modo demo é explícito, rotulado e usa identidade/tenant sintéticos fixos; não deve ter acesso a backend ou dados reais.

## Requisitos bloqueadores de produção

1. Toda rota/API/Server Action deve chamar `requireWorkspace()` (ou guard equivalente) e ignorar qualquer tenant fornecido pelo cliente.
2. O backend Python deve validar JWT Clerk por issuer, audience, assinatura e expiração; derivar `orgId` das claims verificadas; aplicar RLS com contexto por transação e teste negativo cross-tenant.
3. Separar completamente storage/demo fixtures de conexões reais. Demo nunca pode receber credenciais Meta nem alcançar endpoints de envio.
4. Adicionar CSP compatível com os domínios efetivamente usados pelo Clerk, inicialmente em report-only, antes de enforcement. Não foi adicionada uma allowlist especulativa que poderia quebrar login/CAPTCHA.
5. Aplicar HSTS no edge somente após HTTPS estar garantido em todos os ambientes e subdomínios.
6. Mutação externa continua exigindo autorização por recurso, validação de schema, proteção CSRF/origin quando aplicável, idempotência e ledger de aprovação humana.
7. Executar teste de integração com duas organizações provando negação cross-tenant e teste de produção provando que demo causa falha de inicialização.

## Validação

- Revisão manual das superfícies de auth, proxy, providers, layouts e configuração.
- Busca estática focal por sinks XSS, variáveis públicas, armazenamento de token, URLs e identificadores de tenant.
- `npm run lint` e `npm run build` devem ser executados pelo coordenador após estabilização das edições paralelas.

