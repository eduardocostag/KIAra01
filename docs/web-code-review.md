# Revisão de código — `apps/web`

Data: 2026-09-05. Escopo: Next.js 16/React 19, autenticação, rotas, manutenção e UX funcional.

## Parecer

**NEEDS WORK para lançamento comercial.** A demo é navegável e os gates estáticos passam, mas o caminho autenticado ainda entrega fixtures e vários controles aparentam executar operações inexistentes. O artefato atual deve ser comunicado como demo web, não como SaaS operacional.

## Pontos positivos

- `src/proxy.ts` usa corretamente a convenção `proxy.ts` do Next.js 16.
- `src/app/(app)/app/leads/[leadId]/page.tsx:9` trata `params` como `Promise`, conforme o App Router atual.
- `src/lib/auth.ts:14-22` deriva o workspace exclusivamente do `orgId` verificado; não confia em tenant enviado pelo cliente.
- `src/lib/auth-config.ts:10-18` falha fechado para chaves Clerk parciais, produção sem auth e demo explicitamente marcada como produção.
- O envio Instagram permanece desabilitado na demo (`inbox-workspace.tsx:33`), preservando aprovação humana.

## 🔴 Bloqueadores

### 1. Usuário autenticado continua recebendo dados fictícios

`src/app/(app)/app/page.tsx:7-20`, `src/components/app-shell/inbox-workspace.tsx:11-41`, `pipeline-board.tsx:9-12`, `hunter-results.tsx:8-10`, `src/app/(app)/app/leads/[leadId]/page.tsx:7-12` importam `src/lib/mock-data.ts` sem condicionar ao modo demo.

**Risco:** login real não torna o produto operacional e dados fictícios podem ser interpretados como dados do cliente. O contexto multi-tenant existe, mas nenhuma DAL o usa.

**Correção:** impedir fixtures no grafo de produção; carregar DTOs server-side por uma DAL que chama `requireWorkspace()` e filtra pelo tenant. Testar isolamento entre dois `orgId`.

### 2. Ações críticas são inertes ou apenas locais

`inbox-workspace.tsx:33,41`, `hunter/page.tsx:5`, `hunter-results.tsx:10`, `pipeline/page.tsx:5`, `leads/[leadId]/page.tsx:11,14`, `integrations/page.tsx:6`, `app-shell.tsx:53-54` e `settings-form.tsx:9` exibem solicitar aprovação, registrar bloqueio, pesquisar, criar oportunidade, conectar/testar Instagram e salvar, mas não persistem nem tratam erros.

**Risco:** controles de consentimento e governança comunicam sucesso inexistente.

**Correção:** desabilitar/rotular honestamente enquanto não houver backend. Depois, implementar endpoints/Server Actions com autenticação no recurso, autorização, validação, idempotência, auditoria e estados pending/success/error.

### 3. Novo usuário Clerk sem organização cai em erro não tratado

`src/lib/auth.ts:19-22` lança `ActiveWorkspaceRequiredError`; `src/app/(app)/app/layout.tsx:4-6` não redireciona; `sign-up/.../page.tsx:6` promete criar/selecionar organização, mas esse onboarding não existe.

**Correção:** criar onboarding/seletor de organização e converter ausência de `orgId` em fluxo recuperável. Manter checks também na DAL e em cada mutação; o guia local do Next 16 alerta que layout não é fronteira suficiente de autorização.

## 🟡 Sugestões

1. **Modo demo inconsistente:** `auth-config.ts:1-6` aceita `1`, `true` e `yes`, mas `auth-provider.tsx:5` aceita apenas `"true"`. Com valor `1`, o servidor entra em demo e o cliente tenta montar Clerk sem chave. Unificar o parser e cobrir variações em testes.
2. **Conversa incorreta ao trocar lead:** `inbox-workspace.tsx:16-23,31-32` muda o contato, mas sempre renderiza o array global `demoMessages`. Indexar mensagens por `conversationId`.
3. **Origem das mensagens ignorada:** `inbox-workspace.tsx:32` não usa `message.from`; todas as bolhas parecem do mesmo remetente. Diferenciar semântica, rótulo e posição sem depender só de cor.
4. **Legibilidade:** páginas/componentes operacionais estão condensados em linhas únicas e JSX profundamente aninhado. Formatar e extrair unidades como `ConversationList`, `ConversationThread` e `ApprovalComposer`.
5. **Sem testes web:** `package.json:5-10` só possui dev/build/lint. Adicionar unitários de auth config, componentes de Inbox e E2E login→workspace→Inbox→rascunho→aprovação.
6. **Identidade hardcoded:** dashboard e shell fixam “Eduardo”, “Studio Aurora” e “EG”; em Clerk mode devem vir de DTO seguro.
7. **Documentação:** `README.md` ainda é o scaffold e não explica envs, modo demo, limitações nem produção.

## Evidência

Com `NEXT_PUBLIC_KIARA_DEMO_MODE=true`, em `apps/web`:

```text
npm run lint  -> PASS (exit 0)
npm run build -> PASS (exit 0)
Next.js 16.3.4 / TypeScript / 10 páginas geradas
```

Isso prova compatibilidade estática do modo demo; não valida Clerk real, onboarding, backend, Meta, persistência ou isolamento de tenant.
