---
name: kiara-freellmapi
description: Configurar e operar o roteador FreeLLMAPI da Kiara, selecionar modelos e diagnosticar falhas de inferencia nesse provider.
---

# FreeLLMAPI da Kiara

O provider `freellmapi` usa o servico instalado em `services/freellmapi`, fixado no
commit `8b4c7a36e3e147bb5add2a5ba4fd95dd6f5120d3`. O servico encaminha chamadas
aos provedores cadastrados; localhost nao significa inferencia local.

- Prepare com `scripts/setup_freellmapi.ps1`; confira sem instalar com `-CheckOnly`.
- Inicie em primeiro plano com `scripts/run_freellmapi.ps1`. Ele exige
  `ENCRYPTION_KEY` no ambiente (64 hex), mantem bind em `127.0.0.1` e dados em
  `data/freellmapi/freeapi.db`. Reutilize a mesma chave ao reiniciar.
- O usuario cadastra provedores e obtem a chave unificada no painel local.
  Use `FREELLMAPI_API_KEY` no ambiente; nao solicite que segredos sejam colados no chat.
- Selecione `KIARA_LLM_PROVIDER=freellmapi`, `KIARA_LLM_MODEL=auto` e opcionalmente
  `FREELLMAPI_BASE_URL=http://127.0.0.1:3001/v1`. `auto:fast` prioriza velocidade.
- Consulte `/v1/models?available=true` com autenticacao para disponibilidade real;
  uma entrada de catalogo nao comprova quota nem credencial valida.
- Preserve `GuardedRemoteProvider`: tela, memoria e documentos estruturados sao
  removidos, visao e bloqueada, uso diario e limitado. Texto livre ainda e enviado.
- Em falhas, verifique servico, chave, modelo e quotas antes de alterar cadeias.
  Configure fallback Ollama com o nome de um modelo realmente instalado.

Procedimentos e limites: `docs/freellmapi.md`. Nenhum modelo, quota gratuita ou
sucesso de inferencia deve ser afirmado somente porque o setup/build passou.
