# FreeLLMAPI na Kiara

A Kiara oferece o provider opt-in `freellmapi`, usando o contrato OpenAI-compatible
do [repositório upstream](https://github.com/tashfeenahmed/freellmapi).
O cliente Python não exige pacote adicional. O servidor FreeLLMAPI roda como
processo separado, com chaves de provedores cadastradas no painel. As cotas
dependem desses provedores. O checkout local em `services/freellmapi` usa o commit
`8b4c7a36e3e147bb5add2a5ba4fd95dd6f5120d3`; requer Node >=20.18 e <25 e npm >=10.

Prepare o checkout e compile servidor/painel:

```powershell
.\scripts\setup_freellmapi.ps1
.\scripts\setup_freellmapi.ps1 -CheckOnly
```

O setup clona a origem e seleciona o commit fixado apenas quando o diretório
ainda não existe; recusa checkout existente com origem, commit ou arquivos
divergentes. Usa `npm ci` com cache em `.cache/npm-freellmapi` e `npm run build`,
sem sobrescrever configurações. O clone usa OpenSSL do Git para evitar falhas
de Schannel neste ambiente Windows.

Forneça `ENCRYPTION_KEY` no ambiente do processo (64 caracteres hexadecimais,
32 bytes aleatórios), por seu gerenciador de segredos. Guarde a mesma chave
para cada reinício: substituí-la impede a leitura das credenciais já cifradas.
O launcher não gera nem grava esse segredo. Inicie em primeiro plano:

```powershell
.\scripts\run_freellmapi.ps1
# Opcional: .\scripts\run_freellmapi.ps1 -Port 3002
# Somente verificar artefatos: .\scripts\run_freellmapi.ps1 -CheckOnly
```

O processo usa `NODE_ENV=production`, bind `127.0.0.1` e banco
`data/freellmapi/freeapi.db`, fora do checkout. `Ctrl+C` encerra o servidor.
As credenciais dos provedores que você cadastrar são cifradas pelo upstream
nesse banco; não são inseridas pelos scripts. Não use o modo dev upstream para
evitar a geração automática de um arquivo `.encryption-key`.

Abra o painel local `http://127.0.0.1:3001`, conclua o cadastro local, cadastre
as chaves e copie a chave unificada. No PowerShell que iniciará a Kiara:

```powershell
$env:KIARA_LLM_PROVIDER = "freellmapi"
$env:KIARA_LLM_MODEL = "auto"
$env:FREELLMAPI_API_KEY = "sua-chave-unificada"
$env:FREELLMAPI_BASE_URL = "http://127.0.0.1:3001/v1"
$env:KIARA_LLM_FALLBACK_PROVIDER = "ollama"
$env:KIARA_LLM_FALLBACK_MODEL = "nome-exato-do-modelo-local"
python -m app
```

`auto` usa a cadeia ativa; `auto:fast` e `auto:smart` selecionam estratégias do
roteador. Confira modelos disponíveis no painel ou em `/v1/models?available=true`.
A chave pode ser carregada de `.env.local` na raiz, ignorado pelo Git; nunca a
inclua no YAML. A URL é opcional, e serviços externos exigem HTTPS.

O provider também pode ser um candidato explícito de `llm.routing.fast.candidates`
ou `llm.routing.reasoning.candidates` no modo híbrido, com `provider: freellmapi`
e `model: auto`. Não é incluído automaticamente nas cadeias existentes.

Mesmo em localhost, esse roteador pode enviar prompts para provedores externos.
Por isso a Kiara aplica `GuardedRemoteProvider`: remove contexto estruturado de
tela, memória e documentos, bloqueia visão e aplica o orçamento diário e circuit
breaker de `llm.routing`. Texto livre enviado pelo usuário continua no prompt.
O timeout vem de `llm.timeout_seconds` (30 segundos por padrão) e o limite de
resposta de `llm.max_output_tokens`. Logs de uso locais guardam contagem e data.

Testes offline verificam payload, privacidade, orçamento, URL, timeout e fallback.
Eles não comprovam disponibilidade de modelos ou credenciais de um servidor real.

Esta seleção de provider atende o runtime Python `app`. O frontend web e a API
Hunter não possuem uma cadeia LLM equivalente: a inteligência comercial da API
é determinística, e o enriquecimento opcional ScrapeGraph usa sua configuração
própria. O executor de WhatsApp Web continua exigindo Ollama local; selecionar
FreeLLMAPI não encaminha conversas de WhatsApp à nuvem.
