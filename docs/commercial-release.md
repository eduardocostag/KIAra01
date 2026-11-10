# Operação comercial — publicação de 9 de novembro de 2026

Frontend e API foram publicados e promovidos em produção:

| Serviço | URL | Deployment |
| --- | --- | --- |
| Kiara | https://kiaralead.vercel.app | `dpl_BNPw3bkDceK4R4wsqzZ6XR2H3hbZ` |
| API | https://kiara-api-rouge.vercel.app | `dpl_GS3RLxgeETgFp9TMEsSNCqGK4Rkv` |

Destino: **produção**, ambos **READY**. Frontend Next.js 16.3.4: build remoto de 24 s;
API FastAPI/Python: build remoto de 23 s. Fonte: snapshot local validado sobre
`ec77d56e`, incluindo alterações locais não commitadas. Não foi criado commit nem feito push.

## O que foi conectado

- **Caixa de entrada:** conversas dos canais conectados, leitura, resposta, responsável
  humano/IA, temperatura comercial, score, motivos e próxima ação. O CRM permanece em
  **Pipeline**; a caixa de entrada passa a mostrar mensagens.
- **WhatsApp Web:** extensão 2 bidirecional na sessão Chrome existente, sincronização de
  histórico, fila manual do site, respostas da IA local e acompanhamento opcional.
- **Prospecção inicial:** opção explícita para contatos autorizados cuja conversa esteja
  verificada e completamente sem histórico; abordagem inicial única por telefone.
- **Autonomia:** operação com múltiplos contatos, modo piloto opcional, contexto comercial,
  horários, limite diário, pausa por conversa, opt-out e transferência para humano.
- **CRM:** atualização de contatos existentes e qualificação explicável a partir dos sinais
  recebidos. Etapas ganhas/perdidas não são sobrescritas automaticamente pela classificação.
- **Instagram e Chatwoot:** ingestão de webhooks assinados, deduplicação e resposta pela
  caixa unificada com credenciais próprias da organização. O agente automático desta
  entrega atende WhatsApp; não há bot automático Instagram habilitado.
- **Conteúdo Instagram:** Postiz acessível por workspace para canais, mídia, rascunhos,
  agendamento e publicação. Nenhuma credencial global é usada como fallback de outro cliente.

Fila, envio em andamento, falha e resultado incerto aparecem como estados distintos.
Resultado incerto não provoca reenvio automático. Enviar ou retomar IA exige owner/admin;
perfis de operação podem pausar a automação conforme as permissões existentes.

## Ativar no computador conectado ao WhatsApp

1. No Chrome, abra `chrome://extensions` e recarregue a extensão **Kiara WhatsApp**.
   Os arquivos atualizados estão em `extensions/kiara-whatsapp` neste workspace.
2. Atualize as guias do WhatsApp Web e da Kiara. A sessão continua sendo a mesma.
3. Mantenha o executor local e o Ollama ativos; confirme o modelo em
   `KIARA_WHATSAPP_OLLAMA_MODEL`. Se o executor antigo estiver aberto, encerre-o e
   inicie-o novamente pelo fluxo **WhatsApp** do site para carregar o código atualizado.
4. Em **WhatsApp**, configure contexto da empresa, contatos autorizados, horários e
   limite diário. Escolha piloto ou operação e habilite os comportamentos desejados.
5. Acompanhe a sincronização em **Caixa de entrada** e a qualificação em **Pipeline**.

O deploy na Vercel não liga o Chrome nem o modelo local do computador. A automação começa
somente depois de configurar e habilitar a operação. Guia completo:
[executor WhatsApp](whatsapp-executor.md).

## Conectar os outros canais

- **Chatwoot:** configure URL pública HTTPS, conta, token e `webhook_secret` na integração
  do workspace. Webhook: `/v1/channels/chatwoot/{organization_id}/webhook` na API.
  O segredo deve corresponder ao webhook configurado no Chatwoot.
- **Instagram:** configure as credenciais da conta e o webhook
  `/v1/channels/instagram/{organization_id}/webhook`, com `app_secret` e `verify_token`.
  A conta configurada deve corresponder aos eventos recebidos. O envio direto usa
  `graph.instagram.com`; o backend exige `KIARA_INSTAGRAM_GRAPH_VERSION` com uma versão
  suportada pela conta/aplicativo. Configure as permissões de mensagens no aplicativo Meta.
- **Publicações:** conecte seu Postiz em **Integrações**, autorize o Instagram no provedor
  e use **Conteúdo**. Agendamento e publicação dependem da conta/canal realmente conectado.

Tokens, senhas e segredos devem ser cadastrados nas configurações próprias, nunca em chat
ou arquivos versionados. Esta publicação não criou contas nem conectou canais de terceiros.

## Evidências e limites da verificação

- **385 testes Python passaram**, um teste foi ignorado.
- **29 testes JavaScript passaram:** oito de comportamento da extensão e 21 de contratos,
  estados da inbox, CRM, rotas e transporte Postiz.
- Build local e build remoto do frontend aprovados; API e frontend `READY` na Vercel.
- API pública: `/health/live` e `/health/ready` retornaram 200; inbox sem token retornou 401.
- Site público: entrada carregou em desktop/mobile; inbox exigiu login; envio sem sessão
  retornou 401. Nenhum erro JavaScript não tratado foi observado nesse teste de navegador.
- Migrações 0022–0024 e 0027–0029 aplicadas. Tabelas das migrações 0025/0026 já existiam
  no banco e não foram recriadas. A fila comercial tem RLS habilitada e forçada;
  índices de workers não permitem leitura por `anon`/`authenticated`.
- Verificação transacional no banco confirmou deduplicação e rejeição de referência a
  conversa de outra organização; rollback deixou zero registros sintéticos.
- O teste comportamental com `SET ROLE kiara_app` não pôde ser executado pela conexão
  MCP, que não tem permissão para assumir esse papel. Políticas, grants e constraints
  foram inspecionados; testes locais cobrem as fronteiras de organização e autorização.
- Logs observados após a publicação: nenhum erro da API; no frontend, apenas a rejeição
  esperada da solicitação de teste sem sessão, registrada como `session_missing`.
- O advisory de banco deixou de apontar tabelas públicas sem RLS ou helpers com
  search_path mutável. O registro interno de migrações permanece intencionalmente sem
  políticas públicas. Há um aviso pré-existente de proteção contra senhas vazadas
  desabilitada no Supabase Auth; configuração separada descrita na
  [documentação de senhas](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

Não houve envio a cliente real, teste em uma sessão WhatsApp autenticada, publicação
Instagram real ou verificação visual da inbox autenticada. Os testes de envio da extensão
usaram DOM simulado. A primeira operação real deve confirmar o comportamento dos seletores
na versão atual do WhatsApp Web e as permissões dos canais configurados.

Capturas de entrada desktop/mobile: `evidence/commercial-release/`.
Smoke reproduzível: `python scripts/verify_production_release.py --browser`.

## Reversão

Deployments anteriores registrados antes da promoção:

- API: `dpl_8L9akcHR5AHsL1aqnRt9tBA8Py8R`.
- Frontend: `dpl_B5bHZTGMWSeA5zGYQ9Hnfh5j1MCz`.

As migrações são expansivas; um rollback de aplicação pode manter as novas tabelas/colunas.
Não remova filas ou histórico de clientes como parte de um rollback de código.
Os pacotes limpos de upload foram gerados com `scripts/prepare_api_release.py` e
`scripts/prepare_web_release.py`; eles excluem dados locais, cookies, `.env` e credenciais.
