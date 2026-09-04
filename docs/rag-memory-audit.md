# Auditoria de RAG e memória — Kiara

Data: 2026-09-04  
Responsável: `rag-pipeline-engineer`

## Veredito

O produto possui uma base local de recuperação útil para piloto assistido, mas ainda
não possui evidência para ser chamado de RAG de produção. Conhecimento combina FTS5,
sobreposição lexical e embeddings opcionais; memória combina termos, importância,
recência e embeddings opcionais. Ambos retornam explicações ou proveniência suficientes
para depuração inicial. Não existe, porém, conjunto dourado, medição de recall/precisão,
filtro de escopo comercial na consulta ou telemetria de latência e relevância.

Portanto, o gate atual é: **adequado para contexto local revisável; não aprovado para
respostas comerciais autônomas nem para isolamento multi-tenant**.

## Baseline observado

| Dimensão | Implementação atual | Avaliação |
|---|---|---|
| Chunking | Janela por caracteres (1.200/150), com corte preferencial em parágrafo ou frase | Determinístico, mas não preserva hierarquia de Markdown nem página de PDF por chunk |
| Busca de conhecimento | FTS5/BM25 + overlap de termos + cosseno opcional, pesos fixos 0,65/0,35 | Híbrida, mas sem ablação que justifique pesos ou limiar |
| Busca de memória | lexical 0,55 + importância 0,20 + recência 0,15 + semântica 0,10 | Explicável; pode trazer item irrelevante só por importância/recência, pois não há limiar |
| Diversidade | deduplica conteúdo e limita chunks por fonte | Boa proteção contra contexto monopolizado |
| Proveniência | conhecimento expõe fonte, chunk e página opcional; memória expõe perfil, versão, origem e componentes do score | Boa base, embora origem documental seja caminho local e não uma identidade/versionamento estável |
| Montagem de contexto | até 5 resultados, teto agregado de caracteres, conteúdo marcado como não confiável | Limita tokens e prompt injection; truncamento pode cortar evidência sem respeitar sentença |
| Escopo | perfil opcional existe na memória; conhecimento não filtra metadata; `ContextManager` não fornece perfil/conta/lead | Bloqueador para multiusuário, conta ou negociação |
| Escala | varredura de todos os candidatos e vetores em Python | O(n); apropriado apenas enquanto o corpus local for pequeno |

## Contexto comercial

Hoje a consulta usa somente a mensagem do usuário. Ela não restringe resultados por
`workspace_id`, `account_id`, `lead_id`, funil, permissão, idioma, validade ou tipo de
documento. Assim, uma política geral, uma nota de outra conta e uma memória pessoal podem
competir no mesmo ranking. A presença de `MemoryProfile` não resolve isso porque
`ContextManager.assemble()` não seleciona o perfil.

Antes de usar recuperação para redigir contato, qualificar lead ou recomendar próxima
ação, o contrato deve exigir filtros pré-ranking: `workspace_id`, `profile`,
`account_id/lead_id` quando aplicável, `document_type`, `language`, `valid_from/to` e
classificação de sensibilidade. Dados sem escopo explícito devem ficar fora de ações
autônomas.

## Plano de avaliação

1. Criar 50–100 consultas representativas, separadas em política, produto, lead,
   preferência, histórico e pergunta sem resposta. Cada caso deve registrar chunks
   relevantes, escopo permitido e resposta esperada ou abstinência.
2. Medir `recall@5`, `MRR@5`, `precision@5`, taxa de vazamento entre escopos e taxa de
   falso contexto nas perguntas sem resposta. Para geração, medir fidelidade e citação.
3. Comparar, uma variável por vez: chunks 600/80, 900/120 e 1.200/150; lexical puro;
   embeddings locais; fusão por ranking; limiares. Não adicionar re-ranker antes disso.
4. Registrar p50/p95 de busca e throughput de ingestão nos tamanhos reais do corpus.
5. Gate inicial: recall@5 >= 0,75, precision@5 >= 0,80, vazamento de escopo = 0,
   fidelidade >= 0,85 e p95 local < 200 ms. Mudanças só entram com comparação
   antes/depois no conjunto dourado versionado.

## Sequência recomendada

Primeiro implementar filtro estruturado de metadata/perfil e propagar o escopo pelo
`ContextManager`. Depois criar o harness determinístico de retrieval e instrumentar
latência, IDs, scores e fontes (sem armazenar PII ou texto integral por padrão). Em
seguida avaliar chunking estrutural para Markdown e metadata de página para PDF. Somente
se precision continuar baixa e houver orçamento de latência deve-se testar re-ranking.

Nenhuma alteração de ranking foi feita nesta auditoria: sem baseline mensurável, trocar
pesos ou chunk size seria uma otimização sem evidência.
