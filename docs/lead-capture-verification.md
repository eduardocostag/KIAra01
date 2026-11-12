# Correções e verificação de captação — 11/11/2026

As alterações estão no workspace local; esta verificação não publicou uma nova
versão do site, não enviou mensagens e não alterou leads de clientes.

## Comportamento corrigido

- Enriquecimento preserva telefone/WhatsApp já observados quando outra página não
  contém esses dados. Os três enriquecedores usam a mesma regra de preservação.
- Web extrai endereço de texto efetivamente inspecionado, com URL e trecho da
  evidência. Consulta de busca e snippet não servem como comprovação de endereço.
- Web e Maps verificam a cidade/região pedida. Endereços de outra cidade, nomes
  de ruas e cidades com nomes apenas parcialmente coincidentes não passam.
- Navegadores Windows usam um loop Proactor isolado; o banco permanece no
  Selector exigido pelo psycopg. Cancelamento se propaga ao navegador.
- Falhas opcionais de Obscura e análise semântica não interrompem os resultados
  nativos. Detalhes remotos de Maps não verificados acionam uma tentativa local.
- Maps usa três abas de detalhes, espera de hidratação de até 12 segundos e
  prazo global de 50 segundos. Fichas não verificadas são excluídas com aviso.
- Desktop recorre ao navegador se a CLI upstream Maps falhar ou devolver CSV
  vazio. O diagnóstico original é preservado e o kill switch continua ativo.
- Roteamento de skills reconhece acentos em português. O contrato OpenAPI agora
  inclui as operações já implementadas de Instagram e WhatsApp.
- Scrapling recebeu as dependências HTTP ausentes. ScrapeGraphAI está instalado
  no ambiente local e recebe conteúdo público limitado, sem iniciar outro
  navegador incompatível com o loop do banco.

## Evidência real

| Verificação | Resultado |
| --- | --- |
| Maps, clínicas odontológicas em Porto Alegre–RS, limite 3 | 3 aceitos, todos com telefone e localização comprovada; 2 links públicos de WhatsApp; sem avisos |
| Web, dentistas em Curitiba–PR, limite 3 | 1 aceito com telefone/endereço; candidatos incompletos descartados |
| Quatro fontes juntas | Resultados Web preservados; Facebook indisponível e Instagram sem bio verificável foram explicitamente sinalizados |
| Desktop, dentistas em Curitiba, limite 2 | 2 fichas pelo navegador após falha da CLI upstream |
| Scrapling HTTP | Consulta pública a example.com retornou 200 e texto extraído |
| ScrapeGraphAI + Ollama local | Execução real em example.com concluída; valida transporte/execução, não qualidade geral do modelo |
| FreeLLMAPI | Instância isolada: painel 200, modelos exigem autenticação; sem chamada de inferência |

Os resultados variam entre consultas: a verificação encontrou execuções Maps com
detalhes incompletos antes do ajuste de espera/concorrência. Um limite solicitado
é um máximo; não é uma promessa de quantidade ou de conversão comercial.

Artefatos sem dados pessoais:

- `evidence/hunter-maps-live-2026-11-11.json`
- `evidence/hunter-web-live-2026-11-11.json`
- `evidence/hunter-all-sources-live-2026-11-11.json`
- `evidence/scrapegraph-live-2026-11-11.json`
- `evidence/kiara-lead-fixes-tests-2026-11-11.xml`

Verificação final automatizada: **539 testes Python aprovados, 1 ignorado**;
**23 testes do cliente Web** e **9 testes Node upstream Maps** aprovados. Ruff
passou nos arquivos Python alterados. A verificação de dependências confirmou
compatibilidade dos 226 pacotes instalados no ambiente local.

## Dependências ainda pendentes

| Integração | Pendência comprovada |
| --- | --- |
| CLI gosom Maps | Coletor upstream retorna `unexpected page type` e CSV vazio nesta máquina; fallback funcional evita interromper a captação |
| FreeLLMAPI | Chave unificada e cadastro de provedores não disponíveis no ambiente verificado |
| Chatwoot | Token de conta ausente; Docker engine não responde corretamente (consulta fora do sandbox retornou HTTP 500) |
| Obscura | Endpoint CDP não configurado; comportamento de falha/fallback coberto por testes |
| Firecrawl | Chave não configurada neste ambiente; integração e fallback cobertos por testes |
| Instagram/Facebook | Leitura pública depende de disponibilidade e conteúdo verificável; nenhuma conexão de conta, publicação ou mensagem validada |
| Skills Google Ads/Analytics/Data Manager | Referências incorporadas não substituem OAuth, contas e permissões dos serviços |
| postz-app | Repositório original indisponível conforme auditoria anterior; sem integração executável validada |

Não há evidência para afirmar funcionamento de 100% dessas integrações. Para a
matriz de recursos incorporados, consulte `operational-integrations.md` e
`repository-integration-audit.md`.

## Repetir a verificação

```powershell
.\.venv\Scripts\python.exe scripts/verify_hunter_live.py "clinicas odontologicas" --location "Porto Alegre RS" --sources google_maps --limit 3
.\.venv\Scripts\python.exe scripts/verify_operational_integrations.py --smoke-freellmapi
```

O primeiro comando usa provedores reais e não salva leads. `passed` indica que
houve resultados válidos; `all_sources_succeeded` e `requested_limit_reached`
informam separadamente falhas parciais e quantidade. ScrapeGraphAI continua
opcional, exigindo `KIARA_SCRAPEGRAPH_MODEL`; não foi ativado globalmente.
