# Correção de relevância dos leads — 13/11/2026

Os exemplos relatados expuseram falhas distintas: resultados históricos sem nova validação, ausência de filtro de nicho para Web/Maps, páginas editoriais e diretórios confundidos com negócios, e telefone comum apresentado como prontidão para contato no WhatsApp.

Agora o filtro exige correspondência explícita com o nicho; serviços específicos como pilates não são ampliados para todo o segmento fitness. Expressões no plural, como clínicas odontológicas, são reconhecidas por palavra. Dicionários, páginas de equipe, diretórios conhecidos e documentos não são identidades comerciais elegíveis. A adição manual ao CRM também passa pelos controles mínimos e de nicho.

Pesquisas concluídas são revalidadas ao consultar o histórico. Contatos antigos no CRM recebem `review_required` e motivos quando a evidência disponível não sustenta identidade, contato, localidade ou nicho. Essa revisão não apaga registros, não altera etapas comerciais e não sobrescreve o histórico. Novas inclusões preservam o trecho que sustenta a correspondência com o nicho.

A fila distingue revisão de dados, WhatsApp não confirmado e interesse não confirmado. Apenas telefone não confirma WhatsApp, nem intenção de compra. A prospecção pública não garante leads quentes.

Verificação: suíte principal de 210 testes aprovada, 1 teste de Postgres local ignorado; após os últimos ajustes de diretórios e nomes, 34 testes adicionais passaram, incluindo os novos casos. Cliente: 22 testes, ESLint e build aprovados. Ruff aprovado. Novos testes reproduzem dicionário, pub, instituto tributário, lancheria, diretório e título de SEO; cobrem histórico e CRM sem mutação de dados.

Amostras reais sem persistência: psicólogos em Porto Alegre RS, 3 contatos do Maps com telefone/localidade, 2 com link público de WhatsApp; pilates em Lajeado RS após o bloqueio de diretórios, 3 contatos do Maps com telefone/localidade e nenhum WhatsApp confirmado. Não houve comprovação de interesse de compra nessas amostras. Relatórios agregados em `evidence/leads-relevance-urgent/`.
