# Correção da qualidade dos leads — 13/11/2026 UTC

Telefones de links `tel:` agora são decodificados antes da normalização, sem concatenar parâmetros de ramal. URLs de perfis preservam IDs e caminhos na deduplicação da busca, filtros e CRM. Perfis numéricos do Facebook são consultados quando válidos.

Nomes extraídos de títulos da Web mantêm o título original e a procedência. A interface distingue página consultada de perfil conferido e exibe limitações das fontes mesmo em buscas concluídas.

Validação: 201 testes backend passaram, 1 foi ignorado por depender de Postgres local; 24 testes do cliente passaram. Ruff, ESLint e build de produção passaram.

Amostra real sem persistência: clínicas odontológicas em Porto Alegre RS, limite 2 por fonte. Maps: 2 leads aceitos; Web: 1 aceito e 3 candidatos incompletos descartados. Instagram e Facebook: índice público indisponível, sem leads confirmados. Relatórios sem dados de contato em `evidence/leads-quality-fix/`.

As correções se aplicam às novas consultas. Registros históricos não foram reescritos: telefones anteriormente corrompidos exigem nova consulta à fonte para recuperação confiável. A procedência pública não comprova titularidade atual de um telefone nem valida um nome comercial de forma independente.

Publicação: web `dpl_CUcgE69T6Pr73JReH4ZdGkatRK4j`; API `dpl_E49c1aVJFEMmJewWbszd3yau79CA`, ambas READY. Na API, os extras de navegador do Scrapling foram substituídos pelo parser base: o segundo driver Node excedia o disco temporário e causava erro 500 na inicialização. O fetch nativo protegido e o Playwright para CDP foram preservados. Após a correção, `/health/live` e `/health/ready` retornaram 200 e `/v1/hunter/searches` retornou 401 sem autenticação. O site retornou 200.
