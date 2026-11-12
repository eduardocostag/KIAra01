---
name: diagnosing-bugs
description: Ciclo disciplinado de diagnóstico e resolução de bugs complexos e regressões. Use quando encontrar testes quebrados, comportamentos inesperados ou lentidão em APIs e fluxos da Kiara.
---

# Diagnóstico de Bugs e Regressões

Esta skill estabelece uma abordagem sistemática para investigar e corrigir falhas sem adivinhações ("vibe coding"). O princípio central é construir primeiro um circuito de feedback que prove a falha antes de alterar qualquer código de produção.

## Princípio Fundamental: Feedback Loop Estrito (Red-Capable)

Não elabore hipóteses ou teorias lendo código passivamente. Tudo começa com a criação de um teste ou comando reproduzível que fique **vermelho (red)** comprovando o sintoma exato.

### Tipos de Loops de Feedback
1. **Teste automatizado focado**: Adicionar um teste unitário ou de integração que exerça a rota ou método afetado e falhe de forma determinística.
2. **Script ou chamada HTTP/curl**: Invocar o endpoint ou função com o payload exato que causou a falha e validar o status/resposta.
3. **Reprodução com fixture isolada**: Carregar os dados mínimos necessários para acionar o erro sem depender de serviços externos instáveis.

### Critérios de Conclusão da Fase 1 (Loop Pronto)
O circuito de feedback deve ser:
- **Capaz de falhar**: Aciona exatamente o sintoma reportado, falhando antes da correção e passando após ela.
- **Determinístico**: Apresenta o mesmo resultado em todas as execuções.
- **Rápido**: Executa em poucos segundos para viabilizar iterações ágeis.

## Fase 2: Minimização e Isolamento da Causa Raiz

Com o teste falhando de forma determinística:
1. Reduza o caso de teste ao menor payload ou conjunto de parâmetros possível que ainda reproduza o erro.
2. Inspecione o stack trace e isole o componente exato onde a premissa de execução foi violada.
3. Identifique se o erro provém de dados de entrada inválidos, estado não inicializado ou concorrência.

## Fase 3: Correção Cirúrgica e Validação de Regressão

1. Implemente a menor alteração no código de produção que faça o teste passar (verde).
2. Execute a suíte de testes existente ao redor do módulo para garantir que nenhuma regressão foi introduzida.
3. Verifique se o código adicionado respeita as convenções de tipagem e tratamento de erros do projeto.
