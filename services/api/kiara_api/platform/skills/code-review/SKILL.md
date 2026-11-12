---
name: code-review
description: Revisão rigorosa de código em dois eixos (Padrões de Engenharia e Conformidade com a Especificação). Use antes de concluir alterações, pull requests ou refatorações de código no ecossistema Kiara.
---

# Revisão de Código em Dois Eixos (Code Review)

Esta skill orienta a Kiara a realizar revisões de código estruturadas e imparciais. Toda revisão analisa a alteração através de dois eixos independentes:

1. **Eixo 1: Padrões de Código (Standards & Code Smells)**: O código segue os padrões do repositório e evita code smells clássicos?
2. **Eixo 2: Especificação (Spec Fidelity & Scope)**: O código implementa fielmente o que foi solicitado sem omitir requisitos e sem gerar escopo excessivo (scope creep)?

Separar os eixos impede que a conformidade cosmética esconda erros lógicos, ou que a funcionalidade aparente mas mal estruturada passe sem revisão.

## Eixo 1: Padrões e Linha de Base de Code Smells (Fowler)

Ao inspecionar diffs, avalie contra a seguinte linha de base de smells:

- **Nomes Misteriosos (Mysterious Name)**: Variáveis, funções ou classes cujos nomes não comunicam claramente intenção e responsabilidade.
- **Código Duplicado (Duplicated Code)**: Mesma lógica repetida em diferentes funções ou módulos. Extraia a forma compartilhada.
- **Inveja de Recursos (Feature Envy)**: Métodos que acessam intensamente os dados de outro objeto mais do que os seus próprios. Mova o método para junto dos dados.
- **Aglomeração de Dados (Data Clumps)**: Três ou mais parâmetros que sempre viajam juntos em assinaturas de funções. Agrupe-os em um schema ou dataclass dedicado.
- **Obsessão por Primitivos (Primitive Obsession)**: Uso de strings ou números crus para representar entidades ricas de domínio que deveriam ter tipos fortes.
- **Cirurgia com Espingarda (Shotgun Surgery)**: Uma única alteração lógica que exige pequenas mudanças espalhadas por dezenas de arquivos diferentes.
- **Generalidade Especulativa (Speculative Generality)**: Abstrações, flags ou hooks criados para cenários que o requisito atual não pediu. Remova código antecipado e desnecessário.
- **Homem do Meio (Middle Man)**: Classes ou funções que apenas delegam chamadas para outro objeto sem adicionar lógica.

## Eixo 2: Fidelidade à Especificação e Escopo

- **Requisitos Faltantes**: Verifique se cada item solicitado pelo prompt/issue foi completamente entregue e testado.
- **Escopo Excessivo (Scope Creep)**: Verifique se foram alterados arquivos ou regras não relacionados à tarefa.
- **Comportamento Incorreto**: Casos de borda (edge cases), tratamentos de erro e validações de esquema.

## Formato de Conclusão da Revisão

Estruture o resultado da revisão de forma concisa:
- `## Padrões`: Lista de violações de convenção e possíveis smells identificados com o arquivo e linha correspondentes.
- `## Especificação`: Avaliação ponto a ponto do atendimento aos requisitos da tarefa.
- `## Veredito`: Resumo executivo aprovando ou indicando os ajustes pontuais necessários antes da entrega.
