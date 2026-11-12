# Integrações operacionais da Kiara

As integrações estão implementadas no workspace. O fluxo comercial integrado foi
publicado conforme [o registro de release](commercial-release.md).

| Integração | Uso na Kiara | Estado local |
| --- | --- | --- |
| Google Maps Scraper | Pesquisa comercial desktop e backend Hunter opt-in | CLI instalada e hash verificado; coleta upstream falha; fallback desktop comprovado com duas fichas em 11/11/2026 |
| FreeLLMAPI | Provider opcional do runtime Python, com fallback e proteção de contexto | Smoke local 200/401 comprovado em 11/11/2026; inferência exige provedores e chave unificada |
| Instagram Agent Skill | 13 skills e 6 utilitários locais de conteúdo; endpoints autenticados na API | Recursos incorporados e testes offline executados |
| Chatwoot | Central de atendimento via Application API, comandos desktop e endpoints por organização | Adapter e skill incorporados; Docker CLI presente, engine inacessível nesta sessão; conta/token não configurados no ambiente |

## Descoberta e execução

### Verificação e correções em 11/11/2026

- O desktop agora usa a pesquisa pelo navegador existente quando a CLI Maps falha
  ou retorna nenhuma ficha. O diagnóstico da CLI é preservado em `warnings`, e
  `backend` identifica a fonte que entregou o resultado. Kill switch e cancelamento
  impedem iniciar ou aproveitar uma pesquisa alternativa após interrupção.
- Uma consulta real `dentistas em Curitiba`, limite 2, retornou duas fichas pelo
  navegador alternativo após a CLI produzir um CSV de zero bytes. Uma segunda
  execução com diagnóstico local confirmou `unexpected page type` no coletor
  upstream, sem ausência do navegador: não se trata de mudança de colunas rejeitada
  pelo parser da Kiara. Arquivos vazios agora recebem diagnóstico próprio de falha
  de coleta. Isso comprova o fallback nessa consulta; não comprova a CLI upstream.
- O roteamento de skills normaliza os acentos antes de comparar termos em português:
  `prospecção` e `captação` agora selecionam Google Maps corretamente.
- As sete suítes Python de integrações passaram com **133 testes**, incluindo
  regressões do fallback e cancelamento. Os scripts Node upstream do Maps passaram
  com **9 testes**. As 13 skills Instagram e seus seis utilitários locais estão
  cobertos por essas suítes; publicação e envio não foram exercitados.
- O smoke FreeLLMAPI iniciou uma instância isolada, confirmou painel HTTP 200 e
  autenticação obrigatória em `/v1/models`, e encerrou a instância. Não há chave
  unificada no ambiente desta verificação e não foi comprovada inferência.
- O executável Docker está presente, mas a consulta somente leitura ao engine
  falhou por acesso negado no contexto de execução. O diagnóstico agora distingue
  CLI instalada de engine alcançável. O token Chatwoot não está no ambiente;
  canais e atendimento reais continuam sem validação.

### Ativação local em 09/11/2026

O comando `powershell -NoProfile -File scripts/start_operational_services.ps1`
agora inicia os serviços preparados e persiste suas chaves cifradas pelo Windows.
Veja [inicialização e estado](operational-services.md).

- FreeLLMAPI iniciado em `http://127.0.0.1:3001`: painel 200, modelos sem chave 401.
  Ainda exige cadastro dos provedores e chave unificada para inferência na Kiara.
- Chatwoot: integração pronta, serviço bloqueado pela ausência de Docker.
- Maps: corrigidos os caminhos do driver e navegadores Playwright para a instalação
  local dentro de `data/tools`. Dependências baixadas; pesquisa sintética pública
  `dentistas em Curitiba` falhou com `unexpected page type` e CSV vazio.
  Não houve importação nem validação de captação real.
- Roteamento das referências ampliado para pedidos de prospecção em português.
- Verificação das sete suítes de integração: 114 testes passaram.

Os testes acima não comprovam envio WhatsApp/Instagram nem conexão de contas.

O runtime registra `operational_skill` para listar/ler skills e referências Markdown/JSON.
O contexto conversacional seleciona até duas referências relevantes; pedidos em português
como roteiro de reel, legenda e carrossel recebem a skill correspondente.
As referências não executam código nem concedem permissão para publicar ou enviar mensagens.
O planejador usa o registro de ferramentas e os controles de autorização existentes.

O utilitário `instagram_content_check` oferece `hookscore`, `beats`, `caption`,
`humanize`, `detect` e `swipe`. As heurísticas upstream são orientadas ao inglês.
Rascunhos ficam fora dos parâmetros de auditoria da ferramenta. Conteúdo e referências
no contexto de modelos seguem as regras de privacidade descritas no provider selecionado.

Essas skills estão empacotadas para a Kiara em `app/resources`, disponíveis após reiniciar
o runtime. Não foram instaladas globalmente em `.codex/skills` ou `.agents/skills`.

## Preparar outra máquina

```powershell
python -m pip install -e ".[browser]"
powershell -NoProfile -File scripts/install_maps_scraper.ps1
powershell -NoProfile -File scripts/setup_freellmapi.ps1
python scripts/verify_operational_integrations.py
```

O YAML habilita a CLI Maps instalada; sem o executável, o desktop usa o navegador existente.
Os resultados brutos ficam em `data/maps-scraper`, ignorado pelo Git.
O FreeLLMAPI só é selecionado explicitamente, depois de configurar a conta local e as chaves.
Seu launcher exige `ENCRYPTION_KEY` no ambiente e mantém bind em localhost.

## Backend do site

O Hunter pode usar a CLI nativa configurando `KIARA_MAPS_SCRAPER_EXECUTABLE` com
o caminho absoluto do binário apropriado ao sistema do servidor. Sem configuração,
os provedores atuais continuam ativos. O arquivo Windows deste workspace não atende
automaticamente um servidor Linux ou uma função serverless.

A API expõe `GET /v1/instagram/skills`, `GET /v1/instagram/skills/{name}` e
`POST /v1/instagram/content-check`, usando autenticação e membership existentes.
O backend precisa incluir o pacote Python `app` e seus recursos; deployments que copiem
somente `services/api` devem empacotar esses recursos antes de publicar. Sem eles, os
endpoints retornam 503. As análises exigem owner/admin/operator e não publicam conteúdo.

O site não ganhou uma tela nova nesta integração. O provider FreeLLMAPI atende o runtime
Python; a análise de conversas WhatsApp continua no Ollama local.

## Verificação

```powershell
python scripts/verify_operational_integrations.py --smoke-freellmapi
```

O smoke inicia um servidor temporário em loopback com banco isolado, verifica o painel
e a autenticação de `/v1/models`, e encerra o processo. Não cadastra contas, não chama
provedores e não executa scraping. Os artefatos temporários ficam em `.tmp`.

Detalhes: [Maps](maps-scraper.md), [FreeLLMAPI](freellmapi.md),
[Instagram](instagram-agent.md).

Chatwoot: [instalação, credenciais e operação](chatwoot.md).
