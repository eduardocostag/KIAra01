---
name: pr-guidelines
description: Padrão para elaboração de descrições de Pull Requests e relatórios de entrega de código na Kiara. Use para resumir alterações, evidenciar testes e calcular impacto e risco de mesclagem.
---

# Diretrizes para Pull Requests e Entregas de Código (PR Guidelines)

Esta skill orienta a Kiara na formatação de resumos de alterações, mensagens de pull request e relatórios de entrega de código, garantindo clareza e transparência técnica.

## 1. Estrutura Padrão de Pull Request

Toda descrição de entrega ou PR deve conter três blocos fundamentais:

```markdown
## Resumo
<Diagrama de fluxo, árvore de arquivos alterados ou pseudocódigo resumindo o escopo da mudança>

## Evidências
- **Antes:** <Saída de erro, teste falhando ou comportamento anterior>
- **Depois:** <Saída de sucesso, testes passando e logs de validação>

## Risco de Mesclagem (Merge Danger)
- **Porta:** <Porta de uma via (difícil reversão) ou Porta de duas vias (reversão simples via rollback)>
- **Raio de Alcance (Blast Radius):** <Extensão do impacto potencial em outros módulos da plataforma>
```

## 2. Tipos de Evidências Aceitas

- **Nível A (Execução)**: Resultado da execução de suítes de testes (`pytest`, `npm test`), logs de build (`npm run build`) ou verificações estáticas (`tsc`, linter).
- **Nível B (Contratos)**: Comparação de payloads e validação de schemas em endpoints alterados.
- **Visual**: Screenshots ou descrições detalhadas da interface de usuário em casos de frontend.

## 3. Avaliação de Risco

- **Porta de Duas Vias**: Alterações de código puro, rotas novas com fallback seguro ou novas skills somente leitura que podem ser revertidas com um simples `git revert`.
- **Porta de Uma Via**: Migrações de banco de dados destrutivas, deleção de colunas ou alterações de contrato com quebra de compatibilidade externa.
