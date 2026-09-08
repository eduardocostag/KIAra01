# Autenticação e tenancy web

A Kiara Web usa Clerk v7 com sessões em cookies seguros. As rotas `/app/**` e `/api/**` passam pelo `src/proxy.ts`; serviços e handlers devem também chamar `requireWorkspace()` no servidor, pois o proxy não substitui autorização no recurso.

## Modelo de confiança

- `userId`, `orgId` e papel vêm exclusivamente da sessão Clerk verificada.
- `orgId` é o identificador canônico do workspace/tenant. Nunca aceite tenant de query, body ou header do cliente.
- Usuário autenticado sem organização ativa falha fechado com `ActiveWorkspaceRequiredError`; a UI deve encaminhá-lo à criação/seleção de organização.
- Admin é apenas `org:admin`; demais papéis são tratados como membro. Toda permissão sensível continua validada no servidor.

## Configuração

Copie `apps/web/.env.example` para `.env.local` e preencha o par de chaves Clerk. A ausência de uma das chaves falha imediatamente. Produção sem Clerk também falha imediatamente.

Para desenvolvimento visual ou build local sem credenciais, defina explicitamente `NEXT_PUBLIC_KIARA_DEMO_MODE=true`. O modo usa IDs fixos não produtivos, injeta o header diagnóstico `x-kiara-auth-mode: demo` e mantém um banner visível. É proibido quando `VERCEL_ENV=production` ou `KIARA_DEPLOYMENT_ENV=production`.

O layout raiz precisa envolver seu conteúdo com `<AuthProvider>` dentro de `<body>` (compatível com Cache Components). Essa integração ficou com o responsável pelo layout para evitar conflito com a reconstrução visual concorrente.

## Threat model resumido

- Cross-tenant: mitigado ao derivar workspace somente da sessão e exigir escopo também na camada de dados/RLS.
- Bypass de UI/proxy: mitigado exigindo `requireWorkspace()` em cada handler e Server Action.
- Configuração insegura: chaves parciais, produção sem chaves e demo em produção falham fechado.
- XSS/token theft: tokens não são armazenados em `localStorage`; a sessão é gerida pelo Clerk.

Pendentes antes de produção: configurar redirects exatos no Clerk, MFA conforme política, fluxo visual de seleção de organização, eventos de login/role change no audit log e testes cross-tenant contra o banco com RLS.
