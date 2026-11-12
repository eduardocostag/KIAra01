---
name: writing-docs
description: Diretrizes para documentação de arquitetura, referências técnicas e manuais de contexto da Kiara. Use ao criar documentações de serviços, contratos de API, guias de desenvolvimento e ADRs.
---

# Redação de Documentação Técnica e Referências

Esta skill instrui a Kiara sobre como escrever documentações técnicas que sejam úteis tanto para desenvolvedores humanos quanto para modelos de inteligência artificial navegarem pela base de código.

## 1. Princípios de Documentação

- **Fonte Única da Verdade**: Documente decisões e regras de negócio no local de maior autoridade (ex.: contratos de esquema, ADRs ou comentários em classes de domínio). Não duplique a mesma explicação em múltiplos arquivos Markdown.
- **Divulgação Progressiva**: Estruture documentos começando com o resumo executivo e a visão geral, progredindo para os detalhes técnicos e tabelas de referência.
- **Evitar Proibições Negativas sem Direcionamento**: Em vez de apenas proibir ("Não faça X"), aponte explicitamente a prática correta e o padrão esperado ("Use Y para persistência e Z para chamadas HTTP").

## 2. Estrutura de Documentos Técnicos na KIARA

Ao redigir documentação para módulos ou APIs da Kiara, siga a estrutura:
1. **Objetivo e Escopo**: O que o componente faz e quais problemas ele resolve.
2. **Arquitetura e Fronteiras**: Quais módulos ele consome e quem consome seus serviços.
3. **Contratos e Tipos**: Tipos de dados, modelos Pydantic/TypeScript e códigos de erro conhecidos.
4. **Instruções de Execução e Testes**: Comandos para rodar a suíte de testes relevante e validar localmente.
5. **Decisões Notáveis (ADRs)**: Contexto e justificativa para opções de design tomadas.

## 3. Co-localização e Clareza

- Agrupe conceitos correlatos sob o mesmo tópico para que a leitura forneça o contexto completo sem exigir saltos excessivos entre múltiplos documentos.
- Mantenha exemplos de código concisos, testáveis e atualizados com a versão real das dependências do projeto.
