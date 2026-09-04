# Remediação local de dados

A importação CSV B2B usa somente regras locais e determinísticas. Nenhum payload, PII ou amostra é enviado a serviço externo ou modelo. Cada lote emite `LeadCsvService.last_reconciliation` e exige:

`linhas_fonte == linhas_importadas + linhas_em_quarentena`

São tratados: aliases conhecidos de cabeçalho; empresa ausente; score não inteiro ou fora de `0-100`; etapa desconhecida; e valores além do cabeçalho. Cada linha recebe um estado terminal antes do recibo de reconciliação.

"Quarentena" ainda é o conjunto de erros retornado pela API, não uma tabela persistente. O lote também não possui transação/undo: sucessos confirmados permanecem gravados se outra linha falhar. A garantia atual é de **zero linha silenciosamente perdida**, não de atomicidade integral.

A ingestão B2C já é local e fail-closed: limita envelope, profundidade e campos; rejeita dados sensíveis, menores, consentimento implícito, origem incompatível e timestamps sem fuso; e deriva idempotência SHA-256 de plataforma, origem e ID externo. Não se infere nem se "corrige" identidade ou consentimento.

Antes de GA ainda são necessários quarentena persistente, ID de lote, audit log por mudança, transação ou compensação, preview e testes de volume/arquivos malformados. Nenhum Ollama ou SLM foi ativado; eventual IA deve apenas sugerir regra revisável, nunca escrever dados diretamente.
