# Modelos da Kiara via OpenRouter

A Kiara usa uma única credencial, `OPENROUTER_API_KEY`, para acessar os três modelos. A visão
de tela continua local no `qwen2.5vl:3b`; capturas, memória do Obsidian e histórico de ações não
são enviados aos modelos de texto em nuvem.

## Modelos e ordem

- Respostas rápidas: Ling 3.0 Flash → Ox Alpha → Nemotron 3 Ultra → Ollama local.
- Raciocínio complexo: Nemotron 3 Ultra → Ox Alpha → Ling 3.0 Flash → Ollama local.

Identificadores usados:

- `inclusionai/ling-3.0-flash`
- `stealth/ox-alpha`
- `nvidia/nemotron-3-ultra-550b-a55b`

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
