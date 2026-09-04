# Modelos de nuvem da Kiara

## NVIDIA NIM direto

A Kiara aceita `NVIDIA_API_KEY` e usa o endpoint OpenAI-compatible oficial
`https://integrate.api.nvidia.com/v1`. A mesma chave acessa os modelos NVIDIA configurados.
O Nemotron Ultra é tentado primeiro em todas as tarefas; se a chamada falhar, atingir o limite
local ou a cota do endpoint, a Kiara segue automaticamente para Super, Gemini, OpenRouter
gratuito e, por fim, Ollama local.

Configure a chave sem colocá-la no YAML:

```powershell
.\scripts\configure_cloud_ai.ps1 -Provider Nvidia
```

Ou adicione somente ao `.env.local`:

```dotenv
NVIDIA_API_KEY=
```

O host é validado pela aplicação; um endereço alternativo é recusado para evitar o envio da
chave a endpoints não autorizados.

## OpenRouter

A Kiara usa uma única credencial, `OPENROUTER_API_KEY`, para acessar os três modelos. A visão
de tela continua local no `qwen2.5vl:3b`; capturas, memória do Obsidian e histórico de ações não
são enviados aos modelos de texto em nuvem.

## Modelos e ordem

- Todas as respostas: Nemotron 3 Ultra → Nemotron 3 Super → Gemini 3.1 Flash-Lite
  → OpenRouter gratuito → Ollama local.

Cada modelo remoto possui circuit breaker e contador local independentes. Uma falha ou cota
esgotada em um candidato não interrompe a resposta: o próximo é usado. A chave OpenAI não
participa automaticamente desta cadeia, evitando cobrança acidental.

Identificadores usados:

- `inclusionai/ling-3.0-flash`
- `stealth/ox-alpha`
- `nvidia/nemotron-3-ultra-550b-a55b`
- `nvidia/nemotron-3-super-120b-a12b`

Se um modelo falhar ou estiver indisponível, a Kiara tenta o próximo. O circuit breaker, o limite
diário local e o Ollama como último fallback evitam repetição sem controle e mantêm o assistente
operante quando a nuvem falhar.

## Configurar a chave

Cole a chave no arquivo `.env.local`:

```dotenv
OPENROUTER_API_KEY=
```

Ou use entrada protegida no PowerShell:

```powershell
.\scripts\configure_cloud_ai.ps1 -Provider OpenRouter
```

Reinicie a Kiara depois de configurar. Nunca envie a chave em conversa, screenshot, commit ou
nota do Obsidian.

## Custos e privacidade

OpenRouter pode alterar disponibilidade e preços. Consulte a página de cada modelo antes de usar.
Ox Alpha é um modelo stealth operado por terceiros; não use os endpoints em nuvem para dados
confidenciais. A Kiara remove contexto sensível antes das requisições remotas.
