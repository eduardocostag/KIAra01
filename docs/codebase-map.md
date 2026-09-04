# Codebase Orientation Map

## Resumo em uma linha

A Kiara é uma aplicação Python 3.12 local-first, com interface desktop PySide6 e console, que persiste operações comerciais B2B e B2C em SQLite/JSON, pesquisa por ferramentas de navegador headless e usa provedores de LLM locais ou remotos roteados por perfil.

## Explicação de cinco minutos

- **Tarefas principais no código:** conversar com o operador; pesquisar negócios locais B2B; registrar, pontuar e preparar leads; detectar sinais públicos B2C sem convertê-los automaticamente em contatos; organizar pessoas, consentimentos e supressões; exibir cockpit, Kanban, gráficos e conversas; executar automações e serviços de fundo.
- **Entradas principais:** texto digitado ou voz na UI/console, CSV de leads, resultados retornados pelas ferramentas de navegador, payloads normalizados pelos adaptadores B2C, configuração YAML e variáveis de ambiente para provedores.
- **Saídas principais:** respostas no chat, registros SQLite em `data/*.db`, conversas em `data/conversations.json`, cartões e métricas na UI, CSV UTF-8 com BOM, chamadas a ferramentas sujeitas ao `PermissionGate` e artefatos Windows em `dist/`.
- **Arquivos-chave:** `app/__main__.py` inicia console ou desktop; `app/bootstrap.py` compõe stores, ferramentas, segurança, provider e `AgentCore`; `app/core/agent_core.py` roteia intenções e contém os fluxos de pesquisa; `app/ui/desktop.py` conecta os stores à interface; `app/leads/store.py` e `app/consumers/store.py` são as persistências comerciais.
- **Caminho principal:** entrada em `app/__main__.py` → composição em `app/bootstrap.py` → UI em `app/ui/desktop.py` ou loop de console → `AgentCore.handle()`/`stream()` em `app/core/agent_core.py` → ferramenta/provider/store → atualização da UI ou texto no console.

## Deep dive

### Tipo, runtimes e entradas

- **Tipo:** aplicação desktop/console empacotável, em um único pacote Python `app`.
- **Runtimes:** Python 3.12; PySide6 no desktop; `asyncio` para o núcleo, providers e automações; thread dedicada para os serviços de fundo; SQLite e JSON no armazenamento local.
- **Entradas:**
  - `app/__main__.py:main`: configura log rotativo, aceita `--diagnostics` e `--console`, e inicia desktop por padrão.
  - `app/bootstrap.py:build_app`: instancia `KillSwitch`, `PermissionGate`, `AuditLog`, ferramentas, stores, provider, contexto e `AgentCore`.
  - `app/bootstrap.py:run_desktop_app`: importa PySide6 sob demanda e chama `app.ui.desktop.run_desktop`.
  - `app/ui/desktop.py:KiaraWindow`: mantém widgets, stores, worker assíncrono e liga sinais da interface aos fluxos comerciais.
  - `app/core/agent_core.py:AgentCore.handle` e `AgentCore.stream`: classificam a intenção e despacham para os handlers registrados em `_handlers`.

## Estrutura superior

| Caminho | Responsabilidade observada |
|---|---|
| `app/core/` | Orquestração de intenções, contexto, streaming e eventos. |
| `app/leads/` | Modelo, SQLite, scoring, inteligência comercial, política, supressão e CSV B2B. |
| `app/consumers/` | Modelo, SQLite, consentimento/supressão, ingestão autorizada, sinais orgânicos e inteligência B2C. |
| `app/ui/` | Janela desktop, cockpit SDR, cockpit B2C, conversas, painéis, tema e overlay. |
| `app/providers/` | Contrato de LLM, adapters remoto/local, fallback, guardas e roteamento por perfil. |
| `app/automation/` e `app/runtime.py` | Agendamentos/eventos e ciclo de vida de serviços de fundo. |
| `app/tools/`, `app/browser/`, `app/integrations/` | Fronteira de efeitos externos e integrações. |
| `config/kiara.yaml` | Configuração entregue para runtime, providers, segurança e recursos. |
| `scripts/`, `kiara.spec`, `installer/` | Teste/lint/build PyInstaller e instalador Inno Setup. |

## Fluxos reais

### 1. B2B: pesquisa local até oportunidade preparada

1. `AgentCore.handle()` identifica `local_lead_research`; se falta localização, `_local_lead_research()` guarda o pedido em `_pending_local_lead_research` e solicita cidade/CEP.
2. `_consume_local_lead_location()` combina a resposta posterior com o pedido. `_research_local_leads()` extrai quantidade/local/nicho e chama a ferramenta `google_maps_business_search` pelo `ToolRegistry`.
3. O resultado é filtrado para negócio com WhatsApp e sem site listado, deduplicado por nome/telefone e pontuado por `LeadScoringPolicy.evaluate()` (`app/leads/scoring.py`).
4. `LeadStore.upsert()` grava o lead; `add_observation()` grava fatos e fonte; `CommercialIntelligenceService.generate()` separa fatos, inferências e desconhecidos e prepara qualificação, briefing, outreach, proposta e minuta contratual.
5. `LeadStore.update_sales_intelligence()` persiste `qualification_data`, `dossier_data` e `sales_artifacts` em `data/leads.db`.
6. `KiaraWindow._refresh_leads()` lê o store, aplica somente período e agrupamento visual de etapa, calcula KPIs/gráficos e entrega cartões ao `SdrCockpit`. `_show_cockpit_lead()` monta o painel de dossiê a partir dos JSONs persistidos.
7. `PipelineOpportunityCard` cria o MIME `application/x-kiara-lead-id`; `PipelineDropColumn.dropEvent()` emite a movimentação; `KiaraWindow._move_pipeline_lead()` mapeia a coluna visual para `LeadStage`, chama `LeadStore.update()` e recarrega a tela. O store também grava o evento de mudança em `lead_events`.

### 2. B2C: pessoa consentida e sinal orgânico

- **Pessoa conhecida:** `ConsumerStore.upsert_person()` deduplica identidades/contatos; `record_consent()`, `has_active_consent()`, `suppress_contact()` e `can_contact()` governam autorização. `KiaraWindow._refresh_consumers()` lê pessoas e chama `ConsumerIntelligenceService.generate()` para construir readiness, claims, consent gate, handoff e próxima ação. `_show_consumer()` exibe o `CustomerDetail`.
- **Sinal público:** `AgentCore._organic_consumer_research()` chama `organic_consumer_search`, passa cada resultado por `OrganicIntentClassifier.classify()` e salva apenas oportunidades em `ConsumerStore.save_organic_opportunity()`. A UI as exibe como “Aguardando opt-in”; `_show_consumer()` não oferece canal privado e recomenda resposta pública.
- **Adaptadores de entrada:** `GenericFormAdapter`, `MetaLeadAdapter`, `TikTokLeadAdapter` e `LinkedInLeadAdapter` em `app/consumers/ingestion.py` validam e normalizam envelopes, datas, plataforma, base legal e menores. No código de aplicação inspecionado não há chamada desses adaptadores nem persistência dos `ConsumerLeadPayload`; seus usos encontrados estão em `tests/test_consumer_ingestion.py` e nas exportações de `app/consumers/__init__.py`.

### 3. Conversas

1. `KiaraWindow` abre `ConversationStore(data/conversations.json)` e seleciona/cria a primeira conversa.
2. `submit_message()` chama `_append_message()`, que grava a mensagem do operador por `ConversationStore.add_message()` e emite `submit_requested` ao worker.
3. `RequestWorker` chama `AgentCore.stream()`; `_on_completed()` persiste a resposta da Kiara e atualiza leads.
4. `ConversationStore` grava JSON por arquivo temporário seguido de `replace`; ao primeiro texto do operador, troca automaticamente “Nova conversa” pelos primeiros 42 caracteres.
5. A UI cria, seleciona e exclui individualmente com confirmação por `_new_conversation()`, `_select_conversation()` e `_delete_selected_conversation()`.

### 4. Jobs e serviços em segundo plano

- `AgentCore.start_background()` delega a `BackgroundServices.start()`.
- `BackgroundServices` cria a thread daemon `kiara-background`, um loop `asyncio` e inicia, conforme configuração: percepção de tela, proatividade, entendimento contínuo, sincronização Obsidian e `AutomationEngine`.
- `AutomationEngine` persiste specs/runs em SQLite, aceita triggers por intervalo, horário e evento, usa `claim()` como chave de execução e executa ações pelo `ToolRegistry`.
- As pesquisas B2B/B2C são corrotinas executadas pelo worker assíncrono da interface; não existe, nos arquivos inspecionados, um modelo persistente de job de pesquisa com checkpoint, progresso por fonte ou cancelamento por pesquisa.

### 5. Providers e fallback

1. `build_llm_provider()` lê `KIARA_LLM_PROVIDER`, modelo e timeout, e cria local, Ollama, OpenAI ou compatível OpenAI (Groq, OpenRouter, Gemini, NVIDIA, Antling, Tokenra e Vercel Gateway).
2. Para endpoints remotos pré-definidos, `_build_provider()` exige HTTPS e hostname oficial; chaves vêm do ambiente.
3. Com Ollama e roteamento habilitado, `ModelRouter` escolhe `fast` ou `reasoning` por `LocalProfilePolicy`; visão é um perfil separado.
4. Em modo híbrido, `_build_hybrid_router()` envolve candidatos remotos em `GuardedRemoteProvider`, que mantém ledger diário, sanitiza o prompt, limita chamadas e abre circuito após falhas; cada perfil cai para o provider local via `FallbackProvider`.
5. `FallbackProvider` tenta providers em ordem em `generate`, `stream` e visão. O fallback configurado por `KIARA_LLM_FALLBACK_PROVIDER` envolve ainda o provider primário completo.

### 6. Build e instalação

- `scripts/build-windows.ps1` roda toda a suíte `pytest`, `ruff check` e PyInstaller com `kiara.spec`; depois exige assinatura Authenticode válida, salvo `KIARA_ALLOW_UNSIGNED_DEV_BUILD=1` para build local não distribuível.
- `kiara.spec` empacota `app/__main__.py`, `config/` e assets, gera `dist/Kiara.exe`, sem console e sem elevação administrativa.
- `scripts/build-installer.ps1` valida versão, executável, Inno Setup e assinatura; gera `dist/installer/Kiara-Setup-<versão>.exe`, assina se houver thumbprint e imprime SHA-256.
- `installer/kiara.iss` instala por usuário em `%LOCALAPPDATA%`, cria atalhos opcionais e autostart opt-in, e preserva um `AppId` estável para upgrade in-place.

## Limites e implementações incompletas constatadas

Esta lista descreve diferenças concretas entre os fluxos presentes e o escopo solicitado; não é uma avaliação de qualidade.

- `ConversationStore` implementa apenas listar, obter, criar, adicionar mensagem e excluir. Não há campos/métodos para favorito ou tipo (pesquisa/campanha/conversa), nem renomear manualmente, pesquisar, selecionar/excluir várias, desfazer ou limpar histórico.
- `LeadCsvService.import_file()` importa diretamente após o diálogo de arquivo. Não existe API ou UI de preview, mapeamento interativo de colunas, relatório exportável, transação de lote/rollback ou backup/restauração. A deduplicação depende do índice `(company, whatsapp, location)` e do `upsert` do store.
- O Kanban persiste a etapa e registra evento, mas `_move_pipeline_lead()` não mantém estado de desfazer nem responsável. As seis colunas são fixas em `SdrCockpit`; não há configuração de etapas.
- Os filtros do cockpit ligados a `_refresh_leads()` são apenas período e grupo visual de etapa. Não foram encontrados filtros de B2B/B2C, origem, score, região, responsável, status textual, pesquisa, ordenação ou multiseleção.
- Métricas e gráficos do cockpit são calculados dos leads visíveis, mas `Lead`/`LeadStore` não possuem campo de receita potencial nem responsável; esses dois recortes não podem ser produzidos pelos modelos inspecionados.
- Os adaptadores B2C oficiais normalizam payloads, mas não estão conectados a endpoint, fila, ferramenta ou UI de ingestão. O fluxo orgânico grava um sinal público separado e não o converte em pessoa.
- A UI B2C lista pessoas e sinais e abre detalhes; não foram encontrados controles nela para criar/importar pessoa, registrar/revogar consentimento, alterar etapa, aplicar retenção ou atender exportação/exclusão do titular.
- Pesquisa roda fora da thread principal da UI, mas não há entidade durável de job de pesquisa, progresso real por lote/fonte, botão de cancelamento dedicado, checkpoint ou retomada.
- `CommercialIntelligenceService` prepara rascunhos e `ApprovalGate`, mas a ação “Preparar abordagem” da UI formula um prompt no chat. Não foi encontrado, nesse caminho, envio do artefato preparado nem workflow de aprovação/execução externo.
- `build_llm_provider()` roteia por perfis e fallback e `GuardedRemoteProvider` aplica orçamento/circuit breaker/redação básica. Não foram encontrados schema estruturado obrigatório para toda saída, retries HTTP controlados no factory, custo/latência na decisão de roteamento ou tela central de saúde/teste/reconexão de providers.
- O build automatiza teste/lint/empacotamento e bloqueia distribuição sem assinatura, mas os scripts inspecionados não executam instalação limpa, smoke test do executável instalado, rollback de versão ou atualização automática.

## Fronteiras e mapeamento

- **Apresentação:** `app/ui/desktop.py`, `app/ui/sdr_cockpit.py`, `app/ui/consumer_cockpit.py`, `app/ui/conversations.py`.
- **Aplicação/domínio:** `app/core/agent_core.py`, `app/leads/scoring.py`, `app/leads/intelligence.py`, `app/consumers/intelligence.py`, `app/consumers/ingestion.py`, `app/automation/engine.py`.
- **Persistência/I/O:** `app/leads/store.py`, `app/consumers/store.py`, `app/ui/conversations.py`, `app/browser/session.py`, `app/providers/remote.py`, `app/integrations/`.
- **Transversais:** composição em `app/bootstrap.py`; configuração em `app/config.py`; permissões/auditoria/kill switch em `app/security/`; métricas de providers em `app/observability/metrics.py`; ciclo de vida em `app/runtime.py`.

## Arquivos inspecionados

`pyproject.toml`, `README.md`, `config/kiara.yaml`, `app/__main__.py`, `app/bootstrap.py`, `app/runtime.py`, `app/core/agent_core.py`, `app/leads/store.py`, `app/leads/scoring.py`, `app/leads/intelligence.py`, `app/leads/csv_io.py`, `app/consumers/store.py`, `app/consumers/ingestion.py`, `app/consumers/intelligence.py`, `app/consumers/organic.py`, `app/providers/factory.py`, `app/providers/router.py`, `app/providers/guarded.py`, `app/providers/llm.py`, `app/automation/engine.py`, `app/ui/desktop.py`, `app/ui/sdr_cockpit.py`, `app/ui/consumer_cockpit.py`, `app/ui/conversations.py`, `scripts/build-windows.ps1`, `scripts/build-installer.ps1`, `kiara.spec` e `installer/kiara.iss`. O restante do repositório foi inventariado por nomes, mas não foi integralmente lido para este mapa.
