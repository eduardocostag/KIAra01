# Repositórios enviados: ações verificáveis na Kiara

Situação conferida em 13/11/2026 na API do Hunter (Vercel), olhando código, dependências instaladas e variáveis configuradas.

| Origem | Caminho executado no código | Em produção hoje |
| --- | --- | --- |
| D4Vinci/Scrapling | `_fetch_public_page` busca cada site e `parse_with_scrapling` extrai texto e links visíveis | **Ativo.** O parser roda na Vercel. Os fetchers do Scrapling exigem Patchright, que não cabe na Function; lá a busca usa `curl_cffi`, o mesmo motor HTTP do Scrapling, com assinatura de Chrome e checagem anti-SSRF a cada redirecionamento |
| gosom/google-maps-scraper | `maps_search` chama `native_maps_search` quando `KIARA_MAPS_SCRAPER_EXECUTABLE` existe; também é a skill `google-maps-scraper` do chat local | **Inativo na Vercel.** O binário só roda em máquina própria (Windows local ou o servidor Debian) |
| firecrawl/firecrawl | `firecrawl_search` (fonte Web) e `enrich_results` (Scrape v2) | **Inativo.** `FIRECRAWL_API_KEY` não está configurada |
| h4ckf0r0day/obscura | `maps_search` e `obscura_enrich_results` conectam via CDP | **Inativo.** Precisa de `OBSCURA_CDP_URL` apontando para um contêiner persistente (o Debian serve) |
| ScrapeGraphAI/Scrapegraph-ai | `semantic_enrich_results` chama `SmartScraperGraph` | **Inativo.** A biblioteca fica fora da Vercel (`requirements-semantic.txt`) e exige `KIARA_SCRAPEGRAPH_MODEL`; gera só dicas não verificadas |
| Browserbase | `maps_search` abre um Chrome remoto para ler fichas do Google Maps | **Ativo.** O navegador roda nos EUA; a busca é ancorada no Brasil (`maps_search_url`) |
| Exa | `exa_search` alimenta a fonte Web | **Ativo** (`EXA_API_KEY`) |
| Google Places API | `google_places_search`, primeira opção do Maps | **Inativo.** `GOOGLE_PLACES_API_KEY` não está configurada |
| google/skills | Skills de Google Ads, Data Manager e Analytics orientam as integrações; veja `google-growth-skills.md` | Não são SDK nem scraping; ações de Ads exigem OAuth e conta do cliente |
| Tanishq200307/postz-app | Nenhuma chamada | O endereço enviado não está acessível; não é seguro substituir por outro projeto sem confirmar a origem e a licença |

## Como as fontes trabalham juntas

1. **Descoberta na web:** Exa, Firecrawl e o índice público são consultados ao mesmo tempo (`public_search`). Os resultados se intercalam e URLs repetidas são descartadas. No Instagram e no Facebook entram também os links de perfil achados nos sites das empresas.
2. **Google Maps:** Places API e Google Maps Scraper rodam juntos. Se não chegarem à quantidade pedida, um navegador (Obscura, depois Browserbase, depois Chromium local) lê mais fichas. As fichas da mesma empresa viram uma só e uma fonte completa a outra (`merge_maps_rows`).
3. **Enriquecimento em camadas:** primeiro o coletor próprio (Scrapling), gratuito e para todos. O Firecrawl entra só nos leads ainda incompletos, depois o Obscura nas páginas que dependem de JavaScript, e por último o ScrapeGraphAI, que dá apenas dicas.
4. **Mesma empresa em fontes diferentes:** ficha do Maps, site e perfis são reunidos num único lead quando coincidem a ficha, o domínio próprio ou o telefone mais uma palavra do nome (`combine_same_business`). Plataformas compartilhadas (iFood, Linktree, Instagram...) nunca bastam para juntar empresas.

Fonte sem credencial falha na hora e é ignorada; ao cadastrar a chave, ela passa a participar sem mudar código.

Esta tabela distingue código presente, dependências necessárias e ação real em
produção. Um caminho opcional não deve ser anunciado como ativo sem prova de
configuração e execução. Nenhuma biblioteca pode garantir cobertura total de
qualquer nicho, rede social ou estado; o Hunter continua registrando falhas de
fonte e preservando resultados parciais.
