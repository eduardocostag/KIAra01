# Evidências da reformulação web

Data: 2026-09-08

## Escopo validado

- Landing comercial e dashboard em viewport desktop.
- Inbox Instagram em desktop com lista, conversa e qualificação simultâneas.
- Inbox Instagram em mobile no fluxo lista → conversa → painel de qualificação.
- Estrutura acessível exposta pelo navegador: skip link, navegação nomeada, regiões de lista/conversa, artigos de mensagem, headings e controles com nomes.
- Fechamento do painel por Escape e navegação sequencial por Tab.

## Evidências visuais

- `evidence/web-redesign-home-desktop.png`
- `evidence/web-redesign-dashboard-desktop.png`
- `evidence/web-redesign-inbox-desktop.png`
- `evidence/web-redesign-inbox-mobile-list.png`
- `evidence/web-redesign-inbox-mobile-thread.png`
- `evidence/web-redesign-inbox-mobile-qualification-fixed.png`

## Correção encontrada durante o gate

O painel lateral mobile de qualificação ficava abaixo da faixa fixa do modo demonstração. A camada do overlay e do conteúdo de `Sheet` foi elevada para que título, fechamento e conteúdo permaneçam integralmente visíveis. A captura `web-redesign-inbox-mobile-qualification-fixed.png` comprova o estado corrigido.

## Validação técnica

Executados em `apps/web`:

```text
npm run lint          PASS
npx tsc --noEmit      PASS
npm run build         PASS
```

O build Next.js 16.3.4 gerou 10 páginas estáticas e as rotas dinâmicas de Inbox, dossiê e autenticação. O navegador não reportou erros de console nas jornadas inspecionadas.

## Limites honestos

Esta evidência valida interface e comportamento local em modo demonstração. Ela não comprova Clerk, PostgreSQL, permissões Meta, webhook ou envio de mensagens reais em staging/produção. Testes manuais com leitor de tela, zoom 200/400%, forced colors e dispositivos reais ainda são recomendados antes do lançamento público.
