# Repositórios enviados: ações verificáveis na Kiara

| Origem | Caminho executado no código | Condição atual |
| --- | --- | --- |
| D4Vinci/Scrapling | `parse_with_scrapling` é chamado por `_fetch_public_page` no enriquecimento nativo do Hunter | Parser incluído na API; fetchers com browser não são instalados |
| ScrapeGraphAI/Scrapegraph-ai | `semantic_enrich_results` chama `SmartScraperGraph` por `analyze_with_scrapegraph` | Exige biblioteca e modelo LLM; resultados são dicas não verificadas, não contatos do CRM |
| firecrawl/firecrawl | `firecrawl_search` e `enrich_results` chamam Search/Scrape v2 | Exige a chave já cadastrada na API |
| h4ckf0r0day/obscura | `maps_search` e `obscura_enrich_results` conectam via CDP | Exige endpoint de navegador persistente; não é executável na Function |
| google/skills | Skills de Google Ads, Data Manager e Analytics orientam as integrações; veja `google-growth-skills.md` | Não são um SDK nem fluxo de scraping; ações de Ads exigem OAuth e conta do cliente |
| Tanishq200307/postz-app | Nenhuma chamada | O endereço enviado não está acessível; não é seguro substituir por outro projeto sem confirmar a origem e a licença |

Esta tabela distingue código presente, dependências necessárias e ação real em
produção. Um caminho opcional não deve ser anunciado como ativo sem prova de
configuração e execução. Nenhuma biblioteca pode garantir cobertura total de
qualquer nicho, rede social ou estado; o Hunter continua registrando falhas de
fonte e preservando resultados parciais.
