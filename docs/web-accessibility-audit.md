# Auditoria de acessibilidade web

**Escopo:** `apps/web`, com revisão do código e das evidências `evidence/web-home.png` e `evidence/web-inbox-mobile.png`  
**Padrão:** WCAG 2.2, nível AA  
**Data:** 2026-09-05  
**Auditor:** Accessibility Auditor

## Metodologia e limite da evidência

Foram revisados landmarks, títulos, nomes acessíveis, estados dinâmicos, navegação por teclado inferível no código, tabela, foco visível, redução de movimento e reflow nas capturas. O ESLint foi executado. Não havia nesta sessão integração de axe, NVDA, JAWS ou Voice Control; portanto, não se declara teste real com tecnologia assistiva nem conformidade WCAG completa.

## Resumo

- 4 problemas claros corrigidos: 2 sérios e 2 moderados.
- Conformidade: **parcial**, pendente de varredura automatizada e teste manual com NVDA/teclado/zoom.
- As capturas mostram reflow móvel funcional no Inbox, mas não comprovam ordem de foco, anúncios ou contraste calculado.

## Achados e correções

### 1. Buscas sem nome acessível — corrigido

**WCAG:** 3.3.2 Labels or Instructions (A); 4.1.2 Name, Role, Value (A)  
**Severidade:** séria  
**Local:** Hunter e Pipeline  
**Impacto:** leitores de tela poderiam anunciar o campo sem identificar seu propósito.  
**Correção:** `aria-label` nos campos e `aria-hidden` nos ícones decorativos.

### 2. Filtros e seletor sem estado/agrupamento — corrigido

**WCAG:** 1.3.1 Info and Relationships (A); 4.1.2 Name, Role, Value (A)  
**Severidade:** séria  
**Local:** Inbox, Hunter e Pipeline  
**Impacto:** o contexto do conjunto e a opção ativa não eram expostos programaticamente.  
**Correção:** grupos nomeados e botões toggle com `aria-pressed`.

### 3. Estado de aprovação não anunciado — corrigido

**WCAG:** 4.1.3 Status Messages (AA)  
**Severidade:** moderada  
**Local:** Inbox  
**Correção:** status envolvido por região `aria-live="polite"`.

### 4. Tabela sem descrição e escopo explícito — corrigido

**WCAG:** 1.3.1 Info and Relationships (A)  
**Severidade:** moderada  
**Local:** Pipeline em Lista  
**Correção:** `caption` visualmente oculto e `scope="col"` nos cabeçalhos.

## Padrões positivos preservados

- Links de salto para conteúdo.
- Um `h1` descritivo por tela principal, compatível com o anunciador de rotas do Next.js.
- Navegação nomeada e página ativa com `aria-current="page"`.
- Alvos principais com 44 px e foco visível.
- Regra global para `prefers-reduced-motion`.
- Sheet/Dialog baseados em primitivas Radix.

## Pendências antes do lançamento

1. Executar axe-core nas rotas principais.
2. Completar fluxos críticos por teclado e com NVDA + Chrome no Windows.
3. Testar zoom 200%/400%, forced colors e contraste calculado em fundos translúcidos.
4. Confirmar anúncios de mudança de rota e filtro sem verbosidade excessiva.

## Verificação

- `npm run lint`: passou.
- `npx tsc --noEmit`: bloqueado por erro concorrente fora deste diff em `src/app/layout.tsx`: `AuthProvider` exige a prop `mode`.
