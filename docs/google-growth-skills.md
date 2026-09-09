# Kiara Google Growth — base de skills

## Origem auditada

- Repositório: `google/skills`
- Commit incorporado: `a407c6bf560f6e308eb69325a4662817b2624bdb`
- Licença: Apache-2.0
- Estratégia: seleção mínima; o repositório completo não é copiado para a aplicação.

## Skills selecionadas

| Skill | Papel futuro na Kiara | Fase inicial |
| --- | --- | --- |
| `google-ads-api-quickstart` | Conectar contas Google Ads com credenciais oficiais | Setup |
| `google-ads-api-mcp-setup` | Acesso assistido a dados via servidor MCP oficial | Setup |
| `google-ads-api-account-diagnostics` | Diagnóstico de performance, conversão, ranking e orçamento | Somente leitura |
| `data-manager-api-setup` | Preparar ingestão server-side com autenticação correta | Setup |
| `data-manager-api-event-ingestion` | Enviar eventos e conversões consentidos | Aprovação obrigatória |
| `data-manager-api-audience-ingestion` | Criar e atualizar audiências consentidas | Aprovação obrigatória |
| `google-analytics-admin-api-basics` | Administrar propriedades, streams e links | Aprovação obrigatória |
| `google-analytics-data-api-basics` | Ler relatórios e alimentar dashboards | Somente leitura |

As skills de Google Mobile Ads e IMA ficaram fora do escopo: elas monetizam apps e vídeos, enquanto a Kiara precisa gerir aquisição de clientes e campanhas.

## Fronteira de segurança

1. Conexão OAuth por organização, com menor escopo possível e tokens somente no servidor.
2. Primeira entrega limitada a leitura, diagnóstico e recomendações.
3. Toda mutação deve produzir preview estruturado com conta, campanha, mudança, impacto e custo máximo.
4. Publicação, audiências, segmentação e orçamento exigem aprovação humana explícita.
5. Aplicar teto de gasto por conta, idempotência, trilha de auditoria, rollback e kill switch.
6. Dados pessoais e audiências só podem ser enviados com base legal e sinal de consentimento registrado.

## Sequência de produto

1. **Conectar:** OAuth Google, escolha de conta gerente/cliente e validação de permissões.
2. **Observar:** campanhas, gasto, conversões, GA4 e qualidade de tracking em um painel unificado.
3. **Recomendar:** oportunidades priorizadas com justificativa, impacto estimado e nível de confiança.
4. **Preparar:** gerar alterações em modo rascunho, nunca publicadas automaticamente.
5. **Executar com aprovação:** aplicar mudanças autorizadas, confirmar estado final e registrar evidências.

## Limite desta incorporação

Esta etapa adiciona conhecimento operacional, escopo e interface de prontidão. Ela não equivale a uma conexão ativa com contas Google. O próximo marco requer aplicativo OAuth, credenciais Google Ads API, modelo multi-tenant, endpoints de callback e cofre de tokens.
