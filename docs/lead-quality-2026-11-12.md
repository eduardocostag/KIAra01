# Qualidade de leads — 12/11/2026

## Correções

- Scrapling exclui scripts, estilos, templates e conteúdo oculto da extração de texto e links; texto diretamente no body é preservado.
- Seleção manual no Hunter continua exigindo nome, contato público, localização comprovada e URL de origem antes de inserir no CRM.
- Perfis Facebook com `profile.php?id=...` usam o ID correto; a deduplicação preserva parâmetros de identidade e a capitalização de caminhos.
- Publicações e artigos não são tratados como identidade de contato na promoção ao CRM, inclusive resultados antigos sem `content_kind`.
- CRM mantém evidências de endereço e inspeção e utiliza dados normalizados.
- Alternativas OR na consulta são agrupadas para aplicar a região a todas elas.
- Interface apresenta o resumo da fonte com quebra de linhas, informa evidências ausentes e bloqueia a inclusão de publicações ou resultados explicitamente incompletos.

## Verificações desta sessão

- 184 testes Python aprovados e 1 ignorado (exige PostgreSQL de teste configurado), registrados em `evidence/hunter-quality-tests-2026-11-12.xml`.
- 13 testes Node do cliente Hunter aprovados; build Next.js com TypeScript, ESLint dos arquivos Web alterados e Ruff dos módulos Python alterados aprovados.
- Consulta real, sem persistência, clínicas odontológicas em Porto Alegre: 2 resultados Maps aceitos, ambos com contato e localização comprovados. Três candidatos incompletos excluídos. `evidence/hunter-quality-live-2026-11-12.json`.
- Consulta real, sem persistência, dentistas em Curitiba: 1 resultado Web aceito de um máximo solicitado de 2; três candidatos incompletos excluídos. `evidence/hunter-quality-web-live-2026-11-12.json`.
- Testes específicos de Maps/parser/adaptadores: 44 aprovados; testes do browser-worker Instagram: 24 aprovados.
- Revisão estática independente sem bloqueadores identificados.

## Limites

As consultas reais usam a configuração local disponível e não comprovam credenciais, quotas ou funcionamento completo das integrações em produção. Instagram/Facebook e ScrapeGraphAI foram examinados por código/testes; não houve validação de coleta real dessas fontes nesta sessão. Os repositórios oficiais Scrapling, Google Maps Scraper e ScrapeGraphAI estavam acessíveis.

Os testes não enviaram mensagens nem persistiram novos leads. Nenhum saneamento de registros históricos foi executado: identidades antigas já misturadas exigem auditoria antes de separar contatos. A presença de telefone ou WhatsApp público não comprova consentimento, disponibilidade do destinatário ou potencial de conversão.
