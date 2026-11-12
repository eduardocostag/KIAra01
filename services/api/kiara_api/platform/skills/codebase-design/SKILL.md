---
name: codebase-design
description: Vocabulário e princípios de design para construir módulos profundos e código manutenível na Kiara. Use para desenhar interfaces limpas, planejar refatorações de arquitetura e isolar pontos de integração e testes.
---

# Design de Código e Módulos Profundos (Codebase Design)

Esta skill define as diretrizes fundamentais de arquitetura de software para o código escrito e refatorado pela Kiara. O objetivo é maximizar a alavancagem para os chamadores e a localidade de manutenção para a equipe.

## 1. Módulos Profundos vs. Módulos Rasos

- **Módulo Profundo (Deep Module)**: Interface pública compacta e simples ocultando uma implementação rica e complexa.
  - Oferece alto valor por unidade de interface que o chamador precisa aprender.
  - Reduz acoplamento cognitivo no sistema.
- **Módulo Raso (Shallow Module)**: Interface grande com pouca lógica subjacente (mera camada de repasse ou delegação). Evite criar camadas ou classes intermediárias que apenas repassam parâmetros sem adicionar valor ou transformação real.

## 2. Princípios de Arquitetura

1. **Teste de Deleção**: Se deletar um módulo faz com que complexidade desapareça, o módulo era um mero pass-through (raso). Se a complexidade reaparecer espalhada em múltiplos chamadores, o módulo era profundo e estava cumprindo seu papel.
2. **A Interface é a Superfície de Teste**: Callers e testes devem interagir pela mesma superfície pública. Se for necessário expor dados internos apenas para viabilizar um teste, o design do módulo precisa ser ajustado.
3. **Regra dos Dois Adaptadores**: Uma interface abstrata só se justifica quando houver pelo menos dois adaptadores concretos reais (ex.: Postgres e InMemory/Mock). Um único adaptador representa um seam hipotético e prematuro.

## 3. Diretrizes para Testabilidade e Baixo Acoplamento

- **Receber dependências, não instanciá-las internamente**: Passe conexões, clientes e repositórios por injeção/argumento nos pontos de inicialização.
- **Preferir retorno de valores a efeitos colaterais ocultos**: Funções que recebem dados e retornam novos estados ou resultados são mais fáceis de testar e refatorar do que métodos que alteram estado global ou variáveis de ambiente.
- **Superfície de parâmetros simples**: Quanto menos parâmetros obrigatórios uma função exigir, menor será o custo de montagem de fixtures e cenários de teste.
