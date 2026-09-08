# Contrato visual — Kiara Web

**Fase:** landing pública e fundação visual web — 2026-09-05

## Direção

A interface adota uma linguagem de sala de operações: superfícies azul-noite, tipografia editorial de alta legibilidade e cobalto reservado à ação principal e à inteligência assistida. O produto não usa métricas fictícias, depoimentos inventados ou alegações de automação irrestrita.

## Fundação

- Tokens semânticos em OKLCH, com paridade claro/escuro para o produto autenticado.
- Landing deliberadamente escura para assinatura de marca, sem depender da preferência de tema.
- Escala espacial baseada em 4 px; controles de toque com pelo menos 44 px.
- Raios de 8 px em controles, 12 px em cards e 16–24 px em painéis de destaque.
- Foco visível, landmarks semânticos, skip link e suporte a `prefers-reduced-motion`.

## Mensagem comercial

A landing comunica apenas capacidades compatíveis com o MVP: organização de DMs inbound do Instagram oficial, leitura explicável de intenção, preparação de resposta, aprovação humana e acompanhamento da oportunidade. A prévia do produto é rotulada como ilustrativa.

## Componentes públicos

- Cabeçalho compacto com marca e entradas para autenticação.
- Hero editorial com proposta específica para B2C Instagram.
- Console ilustrativo de inbox, qualificação e gate humano.
- Fluxo em três etapas e chamada final para criação de workspace.

## Gate

Validar em navegador nos viewports 360, 768, 1024, 1280 e 1440 px; conferir contraste WCAG AA, zoom a 200%, navegação por teclado, modo de alto contraste e ausência de overflow horizontal. Os links de autenticação dependem das rotas `/sign-in` e `/sign-up` fornecidas pela camada de identidade.
