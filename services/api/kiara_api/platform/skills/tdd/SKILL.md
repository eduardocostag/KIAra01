---
name: tdd
description: Desenvolvimento guiado por testes (Test-Driven Development). Use quando a Kiara for implementar novas funcionalidades, corrigir bugs test-first, ou quando o usuário solicitar ciclo red-green-refactor e testes automatizados.
---

# Desenvolvimento Guiado por Testes (TDD) na KIARA

O TDD é o ciclo estrito **Red → Green → Refactor**. Esta skill orienta a Kiara a produzir testes sustentáveis e código de alta qualidade, garantindo que todo código escrito tenha especificação clara e cobertura confiável.

## 1. O que é um Bom Teste na KIARA

- **Testar comportamento, não detalhes de implementação**: Verifique contratos públicos, entradas e saídas esperadas. Testes não devem quebrar quando a estrutura interna for refatorada mantendo o mesmo comportamento.
- **Valores independentes**: Assertivas devem comparar contra fontes independentes de verdade (casos concretos, fixtures explícitas, especificações), nunca recomputar a mesma lógica da implementação (`assert add(a, b) == a + b` é tautológico e proibido).
- **Fatiamento vertical**: Não implemente todos os testes de uma vez para depois tentar fazer passar em bloco. Adicione um teste focado por fatia vertical (um cenário/comportamento), implemente o estritamente necessário para passar e avance.

## 2. Pontos de Corte (Seams)

Um **ponto de corte (seam)** é o limite público onde o comportamento é observado sem invadir a privacidade do módulo:
- Endpoints HTTP e rotas de API (FastAPI / Next.js)
- Métodos públicos de serviços e classes de domínio
- Adaptadores de persistência e repositórios

**Regra**: Não escreva testes acoplados a métodos privados ou com mocks excessivos de dependências internas.

## 3. Regras do Ciclo TDD

1. **Red (Falha)**: Escreva primeiro o teste mínimo que falha comprovando a ausência do recurso ou a presença do bug. Execute o runner de testes e confirme que o teste falhou pelo motivo esperado.
2. **Green (Passou)**: Escreva apenas a quantidade mínima de código necessária para fazer o teste passar. Não adicione abstrações especulativas neste momento.
3. **Refactor (Limpeza)**: Com o teste passando no verde, limpe o código, elimine duplicações e adeque a nomes limpos, preservando todos os testes verdes.

## 4. Anti-Padrões a Evitar

- **Testes Tautológicos**: O teste repete o cálculo do código sob teste.
- **Mocking Exagerado**: Mockar cada função utilitária intermediária em vez de testar a entrada e saída do componente no seam.
- **Fatiamento Horizontal**: Escrever 20 testes antes de tocar na implementação. Mantenha o ciclo vertical e incremental.
