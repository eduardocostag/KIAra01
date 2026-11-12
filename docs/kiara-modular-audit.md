# Auditoria da base Kiara para a plataforma modular

Data: 11/11/2026. Escopo: estrutura adicional no branch
`codex/kiara-modular-platform`, sem publicação, migração ou ativação de executores.
Este documento diferencia código existente, preparação modular e trabalho futuro.

## Estado de partida e preservação

O ponto de partida foi capturado em `evidence/kiara-modular/baseline.json`:
commit `b025f1dd1acfc1eed2a32b65d2f284435ce04ffa`, branch original `main`, 1.470
alterações locais preexistentes (1.439 exclusões e 31 modificações). Esses arquivos
não devem ser restaurados, limpos ou incorporados a um rollback da fase modular.
O manifesto contém 227 hashes de arquivos frontend/API preexistentes. Não é
um backup do conteúdo nem prova de que todas as alterações locais foram revisadas.

As únicas exceções de edição nessa superfície são:

- `apps/web/src/components/app-shell/app-shell.tsx`: transformar os dois rodapés
  KIARA em links para a plataforma; revisar o diff para preservar navegação e home.
- `services/api/kiara_api/main.py`: registrar o novo router; revisar o diff para
  preservar middleware, handlers, autenticação, payloads e routers anteriores.

`evidence/kiara-modular/api-contract-baseline.json` captura as operações dos 28
caminhos canônicos anteriores. Os objetos dessas operações devem permanecer
iguais; somente caminhos novos sob `/v1/platform` podem ser adicionados. Essa
comparação não substitui a revisão dos schemas referenciados pelo contrato.

O inventário adicional `evidence/kiara-modular/legacy-api-routes.json` registra
**67 caminhos e 80 operações** da aplicação montada com os routers condicionais
de banco e integrações. Os 28 caminhos canônicos anteriores cobriam a montagem
sem banco, não toda a API. O teste modular também monta a configuração completa
com URL sintética e chave efêmera, inspeciona `app.openapi()` e compara as 80
operações, proibindo conexão de banco; somente GET de plataforma pode ser novo.

## Interface e rotas existentes

O frontend usa Next.js 16.3.4, React 19.2.8 e Tailwind 4
(`apps/web/package.json`). `apps/web/src/proxy.ts`, `lib/auth.ts` e
`app/(app)/app/layout.tsx` são as fronteiras atuais de acesso. A fase modular
reutiliza essa autenticação; não cria um segundo login nem substitui o provedor.

| Área existente | Rotas e componentes de referência | Preservação |
| --- | --- | --- |
| Entrada e conta | `/`, `/onboarding`, `/forgot-password`, `/reset-password` | Sem substituição |
| Home comercial | `/app`, `app/(app)/app/page.tsx` | Continua sendo a home |
| Prospecção | `/app/hunter`, `hunter-client.tsx`, `hunter-results.tsx` | Fluxo e identidade visual preservados |
| Atendimento | `/app/inbox`, `/app/inbox/[conversationId]`, `/app/followups` | Sem executor novo |
| Leads e CRM | `/app/pipeline`, `/app/leads/[leadId]` | Legado permanece disponível |
| Concorrência e conteúdo | `/app/concorrencia`, `/app/conteudo` | Sem troca dos fluxos |
| Configuração | `/app/settings`, `/app/settings/integrations`, `/app/integrations`, `/app/admin` | Sem nova autoridade sobre o legado |
| Shell | `components/app-shell/app-shell.tsx` | Apenas links adicionais no rodapé |

Estilos e componentes compartilhados existentes incluem `app/globals.css`,
`orbit-dashboard.css`, `reference-surfaces.css`, CSS Modules do Hunter e
Concorrência, `components/ui`, `components/brand` e componentes de operação de
leads. Novas páginas `/app/platform` devem usar componentes e estilos próprios
ou reutilizar esses elementos sem alterar os arquivos anteriores.

As rotas Next em `src/app/api` já encaminham operações Hunter, pipeline,
integrações, conteúdo, concorrência e atendimento. São separadas da API Python.

## API, dados, identidade e implantação

A API usa FastAPI, psycopg e contratos em `packages/contracts/openapi.yaml`.
`main.py` monta saúde, identidade, inbox e routers condicionais existentes.
`/v1/me`, `/v1/inbox/threads` e os detalhes de conversa têm contratos e fixtures
de teste que devem continuar equivalentes.

O cliente web atual deriva `workspaceId` do `sub` Supabase em `lib/auth.ts`.
A compatibilidade pessoal do backend deriva o workspace do usuário e mantém
o comportamento owner do legado. Isso não equivale a uma plataforma completa de
empresas, convites, revenda ou entitlements. Há estruturas `organizations`,
`users`, `memberships` e RLS no banco, com acesso do backend encapsulado por
`PostgresRepository._transaction`; não é necessário duplicá-las nesta entrega.

A verificação modular de membership deve ser somente leitura. A política
`KIARA_PLATFORM_POLICY_JSON` é configuração confiável do servidor. Papéis globais
são associados a IDs explícitos de usuário, sem promover usuários por email.
A regra de email administrativo preexistente no frontend permanece legado; não
deve ser adotada como autorização da nova plataforma.

Web e API são projetos Vercel distintos. `services/api/vercel.json` reescreve
requisições para `/api/index` e configura duração de 300 segundos. Serviços locais
OpenWA, Chatwoot, Ollama e FreeLLMAPI não ficam acessíveis ao servidor hospedado
automaticamente. Não houve mudança de domínio, secrets, deployment ou recursos.

## Inventário de capacidades reaproveitáveis

| Camada | Fato observado no código | Referências |
| --- | --- | --- |
| Skills do produto | 16 referências empacotadas: 13 Instagram + Maps, FreeLLMAPI e Chatwoot; até duas selecionadas; conteúdo `untrusted_reference`, sem execução implícita | `app/integrations/operational_skills.py`, `app/resources` |
| Tools | 36 classes em `app/tools`, incluindo implementações alternativas Maps com mesmo nome; ativação depende do bootstrap | `app/tools`, `app/bootstrap.py` |
| Agentes | Oito especialistas nativos e generalista; até três consultas; catálogo local opcional importa só nome/descrição | `app/agents/router.py`, `specialists.py`, `catalog.py` |
| Segurança de tools | Registro rejeita duplicatas, valida schema, aplica PermissionGate, auditoria e kill switch; ações sensíveis/críticas exigem confirmação | `app/tools/registry.py`, `app/security/permissions.py` |
| TI | Snapshots Windows de overview/drivers/rede/bateria/eventos, comparação antes/depois; PowerShell por allowlist; Computer Use UIA com pós-condição | `app/helpdesk/diagnostics.py`, `app/tools/powershell.py`, `app/computer_use/agent.py` |
| Memória e integrações | MCP, Obsidian, email, tarefas/calendário, browser e providers LLM têm adapters existentes | `app/tools`, `app/integrations`, `app/providers` |

Essas contagens não representam 36 ferramentas sempre habilitadas ou agentes com
execução autônoma. Skills de desenvolvimento Clerk em `skills-lock.json` e skills
Google do ambiente não são automaticamente módulos executáveis do produto.

## Atendimento e ownership de execução

| Componente | Responsabilidade | Dependências e controle |
| --- | --- | --- |
| OpenWA | Gateway local da sessão WhatsApp, porta 3006 | Node/Chrome, vínculo QR, API key; `infra/openwa/UPSTREAM.json` fixa v0.30.0 MIT |
| Ponte atual porta 3007 | Análise somente leitura de um contato autorizado | OpenWA + Ollama + identidade Supabase + origens permitidas; não envia nem lista contatos |
| Executor Web/extensão | `Engine` com WhatsApp Web ou Chrome; pode consumir configuração e outbox do site | `scripts/run_whatsapp_web.py`, diretório padrão `data/whatsapp-web` |
| Executor OpenWA | Mesmo Engine com REST e responder OmniRoute | `scripts/run_whatsapp_gateway.py`, `data/openwa/kiara`; guard Chatwoot antes de enviar |
| Store/Engine | Baseline, dedupe, janela, limites, opt-out, outbox e pausa por resposta humana | `app/whatsapp/store.py`, `engine.py`; configuração padrão desabilitada |
| Caixa unificada | Threads, handoff, consentimento, idempotência e claims de outbox PostgreSQL | `services/api/kiara_api/unified_inbox.py` |
| Chatwoot | Atendimento humano via Application API | Desktop envio crítico com confirmação; API owner/admin com `confirmed=true`; sem retry automático |

Risco confirmado: `InstanceLock` é por diretório de dados e os dois runners usam
diretórios diferentes. Podem coexistir no mesmo número. O lock OpenWA é por
instância; `ChatwootHandoffGuard` consulta antes do envio, sem compare-and-send
distribuído. Não existe exclusão global comprovada entre executores.

Por isso esta fase não ativa nenhum deles. Fase futura deve definir um único
proprietário de envio por organização/canal/conta/conversa, lease com fencing,
transição humano/automação e tratamento de resultado incerto. Modelos e
especialistas devem preparar rascunhos, sem disputar o transporte de envio.

## Repositórios OSS e proveniência

- Maps: `gosom/google-maps-scraper`, skill MIT e CLI separada, commits/hash em
  `app/resources/operational_skills/google-maps-scraper/UPSTREAM.json`.
- OpenWA: `rmyndharis/OpenWA`, versão/commit/licença em `infra/openwa/UPSTREAM.json`;
  instalar gateway não configura plugin Chatwoot, inbox, webhook ou IA.
- Chatwoot: CE v4.19.1 e adapter próprio Kiara; checkout enterprise não é parte da
  imagem CE. Requer Docker Linux/PostgreSQL/Redis e conta/token/canais.
- FreeLLMAPI: serviço Node local independente em `services/freellmapi`; a presença
  do painel não comprova inferência ou credenciais de provedores.
- Scrapling, ScrapeGraphAI, Firecrawl e Obscura: adapters Hunter HTTP/parser,
  semântica não verificada, Search/Scrape e CDP; não executores de atendimento.
- `google/skills`: instruções Ads/Analytics/Data Manager, dependentes de contas e
  OAuth; não equivalem a scraping. `Tanishq200307/postz-app`: nenhuma chamada
  integrada identificada. Ver `docs/repository-integration-audit.md`.

## Limite da fase modular

O catálogo reúne quatro módulos: Leads existente e três módulos em preparação
(WhatsApp, Atendimento e TI), com contexto, detalhes, skills e portfólio
consultáveis. Leads continua compatível e habilitado.
Desabilitar Leads, impor gates comerciais aos workers e trocar empresa ativa
exigem desenho e migração de dados autorizados em fase futura. Revendedor é
metadata com grants explícitos; não concede leitura de leads/conversas.

A API nova expõe somente GET sob `/v1/platform`. Não cria empresa, convite,
assinatura, revenda operacional, cobrança ou executor. A política não substitui
RLS, não torna os endpoints antigos dependentes de novos entitlements e não deve
ser anunciada como isolamento multiempresa completo.
