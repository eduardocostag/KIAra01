# Entrega e validação da preparação modular Kiara

Data: 11/11/2026. Branch de trabalho: `codex/kiara-modular-platform`.
Não publicar, executar migrações, trocar ambiente ou ativar workers nesta fase.
Inventário e fronteiras: [auditoria](kiara-modular-audit.md).

## Contrato de entrega

- A home `/app`, navegação comercial, Hunter, leads/CRM, inbox e estilos existentes
  permanecem. O acesso adicional é pelo rodapé Plataforma e páginas `/app/platform`.
- Autenticação Supabase existente é reutilizada. Backend modular expõe apenas GET
  de contexto, detalhes de módulo, skills e portfólio, com política confiável do
  servidor e verificação de membership somente leitura.
- Papéis globais e grants de portfólio permanecem limitados pela policy do
  servidor. Para esta publicação específica, as novas rotas também exigem a
  identidade verificada `admin@kiara.local`; isso não concede acesso a dados
  comerciais de clientes.
- Leads permanece habilitado por compatibilidade. WhatsApp/Atendimento/TI são preparação,
  sem ativar transporte, automação, Computer Use ou execução de comando.
- O catálogo visual `/app/platform/skills` lista referências autorizadas e seus
  módulos, mantendo os executores inativos. A API empacota apenas metadados
  conferidos contra o catálogo fonte; os corpos das skills não são enviados nem
  executados por esse módulo. Dependências, permissões e ambiente de execução
  ainda não são validados ou exibidos.
- Nesta publicação, as rotas modulares ficam restritas no frontend e no backend
  ao claim de email assinado `admin@kiara.local`; ocultar o menu não é a única
  barreira de acesso.
- Não há schema novo/migração, convite, troca de empresa ativa, cobrança, publicação
  ou alteração dos projetos Vercel. Gates comerciais de workers ficam para fase
  futura com migração aprovada e testes de isolamento.

## Arquitetura antes e depois

| Camada | Antes desta fase | Depois desta fase |
| --- | --- | --- |
| Entrada e shell | Home `/app`, navegação comercial e rodapés KIARA | Mesma home/navegação; apenas os dois rodapés viram links Plataforma |
| Interface modular | Sem portal modular | `/app/platform`, detalhes de WhatsApp, Atendimento e TI, catálogo de skills somente leitura e CSS Module próprio |
| Frontend/API | Pontes e contratos comerciais existentes | Quatro pontes GET novas sob `/api/platform`, parser de respostas e consultas server-only |
| Backend | Routers e identidade comerciais existentes | Pacote `platform` e quatro GET novos sob `/v1/platform`; import/montagem em `main.py` |
| Identidade e dados | Supabase, workspace pessoal legado, organizations/memberships/RLS existentes | Mesmo login; resolução somente leitura de membership, fallback pessoal compatível e policy confiável |
| Autorização modular | Sem catálogo/policy modular | Módulos de preparação filtrados por policy; Leads sempre compatível; grants de portfólio só metadata |
| Atendimento e execução | Adapters/workers locais já existentes e separados | Nenhum novo executor, serviço, conexão ou transporte ativado |
| Persistência e entrega | Bancos e projetos web/API existentes | Sem migração, contratação persistente, troca de empresa ou deploy |

TI apresenta Tickets, Prioridades, SLA, Distribuição, Alertas de infraestrutura e
Relatórios; Tiflux e GLPI aparecem somente como integrações futuras. Atendimento
apresenta Triagem, Atendimento humano, Histórico, Distribuição e Indicadores e
relatórios. São estruturas de consulta, sem alegação de dados ou conexão ativa.

## Arquivos exatos desta etapa

Fontes novas do produto, sem incluir arquivos preexistentes de fases anteriores:

```text
services/api/kiara_api/platform/__init__.py
services/api/kiara_api/platform/access.py
services/api/kiara_api/platform/policy.py
services/api/kiara_api/platform/registry.py
services/api/kiara_api/platform/router.py
services/api/kiara_api/platform/service.py
services/api/kiara_api/platform/skills_catalog.py
apps/web/src/lib/platform/contracts.ts
apps/web/src/lib/platform/server.ts
apps/web/src/components/platform/module-preparation.tsx
apps/web/src/components/platform/platform-nav.tsx
apps/web/src/components/platform/platform-overview.tsx
apps/web/src/components/platform/platform-shell.tsx
apps/web/src/components/platform/platform-skills.tsx
apps/web/src/components/platform/platform-unavailable.tsx
apps/web/src/components/platform/platform.module.css
apps/web/src/app/(app)/app/platform/layout.tsx
apps/web/src/app/(app)/app/platform/page.tsx
apps/web/src/app/(app)/app/platform/[moduleKey]/page.tsx
apps/web/src/app/(app)/app/platform/skills/page.tsx
apps/web/src/app/api/platform/context/route.ts
apps/web/src/app/api/platform/modules/[moduleKey]/route.ts
apps/web/src/app/api/platform/portfolio/route.ts
apps/web/src/app/api/platform/skills/route.ts
```

Exatamente três fontes/contratos preexistentes foram modificados no escopo desta
etapa: `services/api/kiara_api/main.py`,
`apps/web/src/components/app-shell/app-shell.tsx` e
`packages/contracts/openapi.yaml`. Os outros diffs preexistentes no working tree
pertencem ao estado local capturado; não são mudanças desta etapa modular.

Novos arquivos de suporte: `services/api/tests/test_platform_access.py`,
`tests/web_api/test_modular_compatibility.py`,
`apps/web/tests/platform-contracts.test.mjs`,
`scripts/verify_modular_preservation.py` e os dois documentos modulares. Baselines
e resultados estão em `evidence/kiara-modular`; não incluem segredos nem backup
completo do working tree.

## Baseline e revisão dos diffs

O manifesto `evidence/kiara-modular/baseline.json` guarda hashes do estado local
capturado, não só de HEAD. Há 1.470 alterações locais anteriores; rollback não
pode usar limpeza global, hard reset nem restauração indiscriminada de `main`.
Não atualize os baselines para fazer um check passar.

O verificador `scripts/verify_modular_preservation.py` é somente leitura e:

1. Compara os 227 arquivos de origem ao manifesto; falha para desaparecimento ou
   mudança fora das duas exceções de integração autorizadas.
2. Relata `main.py` e `app-shell.tsx` como arquivos que exigem revisão manual se
   mudarem; não considera seus diffs integralmente seguros só por serem exceções.
3. Compara os objetos das operações dos 28 caminhos canônicos anteriores e
   rejeita adições fora de `/v1/platform`.

O teste complementar de rotas completas usa
`evidence/kiara-modular/legacy-api-routes.json` (67 caminhos/80 operações) e
`app.openapi()` com URL de banco sintética e chave gerada efemeramente. Nenhuma
conexão é aberta; o teste falha se a inspeção tentar conectar. Todos os métodos
anteriores devem continuar presentes e só GET de plataforma pode ser novo.

Revisar manualmente: import/montagem do router em `main.py`; substituição apenas
dos dois rodapés no shell; novos schemas sem mudança nos schemas legados; páginas
novas sem CSS global; nenhuma alteração em migrations, credenciais ou workers.

## Matriz de verificação

| Verificação | Evidência esperada | Limite |
| --- | --- | --- |
| Preservação de fontes/contrato | Script retorna `passed=true`, lista exceções e novos paths | Não substitui revisão das exceções/schemas |
| Caracterização do legado | Health, me, inbox/lista/detalhe/ETag, erro auth e isolamento continuam iguais | Fixtures locais, sem banco/conta externa |
| Autorização modular | Sem auth negado; IDs e membership verificados; grants sem acesso implícito; policy inválida falha segura | Não certifica multiempresa comercial futura |
| Contrato e suítes API | Routers reais e contrato canônico alinhados; testes legados passam | Não criar credenciais nem chamar serviços |
| Frontend | Lint, TypeScript e build local passam | Build não comprova sessão de produção |
| UI | Revisão das rotas novas, incluindo catálogo de skills, em desktop/mobile, foco/teclado, estados vazio/negado/erro | Login real depende de sessão autorizada disponível |
| Não ativação | Diffs não alteram workers/configs; nenhum POST de envio ou migração | Não declarar atendimento/canais validados |

Comandos locais seguros, a executar na raiz:

```powershell
.\.venv\Scripts\python.exe scripts/verify_modular_preservation.py
.\.venv\Scripts\python.exe -m pytest tests/web_api/test_modular_compatibility.py -q
.\.venv\Scripts\python.exe -m pytest tests/web_api -q
```

Os testes novos caracterizam respostas reais do app montado com identidade e
repositório em memória; não usam tokens reais.

## Conferência local com autenticação normal

Use somente o ambiente local/de desenvolvimento já configurado do projeto;
não carregue arquivos de ambiente de produção nem direcione testes ao banco de
produção. Os comandos abaixo não criam
credenciais, não exportam policy, não desabilitam autenticação nem carregam dados
de demonstração em produção. Para a API, variáveis existentes de identidade,
banco e integrações devem estar disponíveis no ambiente normal do processo.
A consulta nova de membership da plataforma é somente leitura, mas isso não
autoriza usar dados reais de produção como fixture de desenvolvimento.

Na raiz, em um terminal dedicado:

```powershell
.\.venv\Scripts\python.exe -m uvicorn kiara_api.main:create_app --factory --app-dir services/api --host 127.0.0.1 --port 8000
```

Em outro terminal, dentro de `apps/web`:

```powershell
npm run dev
```

O frontend usa seu `.env.local` existente, inclusive a URL de API apropriada ao
ambiente. Entre pelo login normal Supabase e abra `/app/platform`; confira os
quatro módulos e os detalhes disponíveis para sua participação. `/app` continua
sendo a operação Leads. Iniciar o dev server não ativa os executores externos
pelo portal modular. Falta de configuração deve ser exibida como indisponibilidade,
sem bypass de login nem exposição de secrets.

## Exemplo sintético de policy, sem aplicação

O JSON abaixo ilustra o schema de `KIARA_PLATFORM_POLICY_JSON`. Não foi aplicado
ao ambiente. Os IDs são fictícios; grants não criam organização, membership,
assinatura, contratação persistente ou direito de consultar leads de terceiros.

```json
{
  "organizations": {
    "empresa-exemplo": {
      "disabled_modules": ["ti"],
      "module_roles": {"atendimento": ["owner", "admin"]}
    }
  },
  "platform_admin_user_ids": ["usuario-admin-exemplo"],
  "reseller_assignments": {
    "usuario-revendedor-exemplo": ["empresa-exemplo"]
  }
}
```

A policy deve ser gerida como configuração confiável de servidor em uma etapa
autorizada. Não usa emails para promoção de papel e não aceita desabilitar ou
restringir Leads nesta preparação. Ausência de policy não concede papel global;
JSON inválido falha de forma explícita nas rotas modulares, sem reconfigurar o
legado comercial.

## Estado das evidências desta entrega

- Caracterização/preservação: **7 testes passaram** no arquivo
  `tests/web_api/test_modular_compatibility.py`, incluindo o inventário completo
  dos 67 caminhos/80 operações preexistentes sem conexão de banco.
- Verificador repetido após inclusão do contrato modular: 227 arquivos capturados,
  225 intactos, duas exceções para revisão; 28 caminhos canônicos anteriores
  preservados e quatro novos caminhos: `/v1/platform/context`,
  `/v1/platform/modules/{module_key}`, `/v1/platform/skills`, `/v1/platform/portfolio`.
- API: `services/api/tests` e `tests/web_api` tiveram **440 testes aprovados e
  1 ignorado**, com zero falhas/erros. Registro:
  [`api-tests.xml`](../evidence/kiara-modular/api-tests.xml).
- Após um ajuste somente na ordem de importação de `main.py`, a suíte focal
  posterior teve **44 testes aprovados**. O ajuste não altera o comportamento do
  router; não foi necessário atribuir a esse resultado uma nova execução ampla.
- Após empacotar os metadados do catálogo na API independente, os testes focais
  da plataforma tiveram **32 testes aprovados**; um teste compara cada nome e
  descrição com o catálogo fonte para evitar divergência.
- Frontend: `npm run build` terminou com exit 0; build otimizado Next.js 16.3.4,
  verificação TypeScript e geração de **55 páginas** concluídos.
  O build final também passou após os textos Tiflux/GLPI e Alertas de infraestrutura.
- Node: todos os arquivos `*.test.mjs` do frontend tiveram **52 testes aprovados**.
- ESLint dos arquivos novos e de AppShell terminou com exit 0. Ruff passou no
  pacote/testes novos, `main.py`, script de preservação e compatibilidade.
- A conferência final de status nos arquivos de autenticação/Supabase, proxy,
  configuração/identidade, migrations, requirements, manifests de pacote/lock,
  Next config e Vercel não encontrou mudanças nesses caminhos.
- A publicação autorizada ainda não foi realizada: a sessão local não dispõe
  de autenticação Vercel/CLI disponível para publicar e verificar os projetos.
- Revisão AppSec/CodeReviewer somente leitura do pacote modular não encontrou
  achado bloqueante concreto. Essa revisão não certifica produção nem os
  executores legados; exclusividade de execução por conversa e gates comerciais
  permanecem futuros.

Os resultados gerais acima foram fornecidos pelo coordenador após a execução;
não foram inferidos a partir da presença de código ou de um build anterior.
O resumo consolidado está em
[`verification.json`](../evidence/kiara-modular/verification.json), e o relatório
de preservação em [`preservation.json`](../evidence/kiara-modular/preservation.json).

### Evidência visual e limites

Foram executados **12 cenários** de componentes reais renderizados isoladamente
por SSR com fixtures: overview, WhatsApp, Atendimento, TI, indisponível e acesso
negado, em desktop **1440 × 1000** e mobile **390 × 844**. Os checks registram zero
overflow horizontal, um h1 por cenário, ausência de forms/controles de executor,
links dos quatro módulos e foco visível ao navegar por Tab.

Artefatos: [`visual-checks.json`](../evidence/kiara-modular/visual-checks.json) e
capturas em [`visual/`](../evidence/kiara-modular/visual/). O coordenador inspecionou
três capturas e confirmou a apresentação escura/lilás e legibilidade.
O servidor temporário das fixtures na porta 3188 foi encerrado após os checks.

Isso valida o render isolado dos componentes, **sem hidratação, login Supabase ou
banco real**. Não comprova a experiência autenticada em produção, reconexão de
sessão, comportamento integrado do shell móvel nem conformidade WCAG com leitor
de tela. Nenhuma proteção foi desativada para obter as capturas. Produção
autenticada não foi testada nesta sessão; não usar credenciais de cliente nem
alterar secrets para contornar essa limitação.

## Rollout futuro, após revisão da entrega

Esta fase prepara um diff revisável. Um rollout posterior deve validar os mesmos
checks no commit exato, revisar policy sem expor seu conteúdo, publicar API/web
compatíveis em ambiente de validação autorizado e verificar GET autenticado e
acesso negado. A configuração inicial deve preservar o workspace pessoal legado
e não conceder grants globais por padrão. Publicação não está incluída nesta fase.

Antes de um produto multiempresa/comercial: aprovar separadamente modelo de
empresas/memberships, migração/backfill/rollback, papéis, entitlements, cobrança,
troca de contexto, observabilidade e ownership exclusivo de executores.

## Rollback da fase modular

Como não há migração nem ativação operacional, o rollback é de código/configuração
modular. Preparar um diff inverso somente dos arquivos adicionados e dos dois
pontos de integração, preservando qualquer edição concorrente. Remover o link e
router modular; restaurar somente as operações contratuais acrescentadas por esta
fase. Não apagar diretórios globais, dados, tokens, sessões ou alterações anteriores.

Se política nova tiver sido configurada em rollout autorizado, retirar apenas essa
configuração pelo mesmo mecanismo de gestão, sem tocar a identidade e configurações
legadas. Após rollback, repetir preservação/characterization e confirmar `/app`,
health, identidade, inbox e Hunter no ambiente autorizado. Não desinstalar OpenWA,
Chatwoot ou provedores, nem encerrar sessões como parte do rollback desta estrutura.
