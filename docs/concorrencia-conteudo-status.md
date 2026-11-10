# Concorrência e Conteúdo — implementação e ativação

## Entregue nesta alteração

Concorrência: pausa após rate limit/challenge sem fallback adicional; código e prazo de espera preservados até a interface; desconexão 204 corrigida; contatos públicos presentes no payload ou email literal na bio preservados com evidência; busca, filtro por contato e CSV do subconjunto exibido. Exportação neutraliza fórmulas de planilha.

Jobs de concorrência: cada solicitação da Kiara é registrada antes da coleta em `competition_analysis_jobs`, com isolamento RLS por organização, chave idempotente e fingerprint do pedido. `competition_analysis_work_queue` guarda apenas IDs e lease, para permitir reivindicação global com `SKIP LOCKED` sem expor payload de clientes. O endpoint responde rapidamente com HTTP 202; um worker persistente executa a coleta fora da requisição web. Jobs têm estados `queued`, `running`, `paused`, `completed` e `failed`, contador de tentativas, checkpoints por fase e lease de três minutos para recuperação após queda do worker. Um fencing token (`lease_owner`) impede workers antigos de persistirem checkpoints, resultados do arquivo ou conclusão depois que outro worker tomou o lease. Erros temporários têm até cinco tentativas com backoff; rate limit respeita cooldown; challenge de verificação não é repetido automaticamente. Uma repetição com a mesma chave e pedido não inicia coleta concorrente; chave reutilizada para outro pedido responde conflito. Resultados concluídos são reproduzidos do arquivo persistido sem consultar novamente o Instagram. A interface mantém a chave em `sessionStorage` e consulta o status do job.

Conteúdo local: retomar, editar, remover mídia, salvar, agendar lembrete e preparar o mesmo rascunho. PUT exige If-Match, bloqueia a linha e valida organização/estado antes de substituir os targets. Publicações entregues não são editáveis; canceladas não reaparecem na lista.

Conteúdo Postiz: nova aba independente de publicação automática, canais conectados, mídia, criação de rascunhos, agendamento, publicação imediata, calendário mensal, exclusão de grupo e métricas de canal. API key permanece no servidor; endpoints exigem o administrador do sistema. O canal e o provedor são conferidos na conta Postiz antes de enviar conteúdo. TikTok usa DIRECT_POST com opções explícitas de privacidade, marca e IA; YouTube tem título, visibilidade e público infantil.

## Configuração para uso real

1. Manter API Kiara e PostgreSQL disponíveis e aplicar migrations até 0024, incluindo `0022_competition_durable_jobs.sql`, `0023_competition_work_queue.sql` e `0024_competition_worker_fencing.sql`.
2. Concorrência usa KIARA_COMPETITION_API_URL no frontend; API e worker compartilham `POSTGRES_URL` (ou `DATABASE_URL`) e `KIARA_BROWSER_WORKER_URL`/`KIARA_BROWSER_WORKER_TOKEN`. O worker precisa rodar como processo persistente supervisionado, por exemplo a partir de `services/api`: `python -m kiara_api.competition_worker`. Configure restart automático e monitore os logs `competition.worker_*`; em ambiente serverless, não execute esse processo dentro da função HTTP. O Browser Worker precisa de volume persistente para sessão e pausa de segurança. Conectar Instagram pela tela da Kiara.
3. Em Administração → APIs e conexões, configurar Postiz com chave da organização e URL base. Cloud: https://api.postiz.com. Self-host: URL base incluindo /api quando o proxy da instância expõe /api/public/v1. Não incluir /public/v1 na base. A alternativa de configuração por ambiente é POSTIZ_API_URL e POSTIZ_API_KEY; manter restrita ao uso administrativo atual.
4. Conectar as contas sociais no painel Postiz. Cadastrar um canal assistido na Kiara não conecta OAuth e não habilita publicação automática.
5. Validar uma publicação de teste aprovada pelo proprietário, verificar o ID/URL retornado e confirmar a presença na rede. Esta execução não publicou conteúdo real.

Upload na aba Postiz limitado a 4 MB para caber no limite de payload das funções Vercel. Para vídeos maiores, usar o painel Postiz por enquanto; upload direto ao storage ainda precisa ser integrado. Documentação: https://vercel.com/docs/functions/limitations#request-body-size.

## Limites reais e próximos incrementos

Não há paridade completa com Mailerfind ou Postiz. A coleta segue limitada a 25 resultados por análise. Depois que o Browser Worker responde, o job persiste o resultado coletado no checkpoint privado antes de gravar o arquivo; se o processo cair nessa etapa, a retomada persiste o checkpoint sem consultar o Instagram novamente. Uma falha durante a própria chamada externa ainda pode exigir nova consulta: a API atual não retoma de um cursor interno do Instagram, e o cooldown preventivo conta por análise. Ainda faltam cursores/paginação durável do coletor, painel/alertas operacionais da fila e limites de throughput configuráveis por conta. Contatos dependem dos campos efetivamente retornados pelo Instagram; não há enriquecimento remoto, email inventado ou garantia de contato para todo perfil.

O calendário Postiz mostra a agenda em lista mensal. Rascunhos Postiz ainda devem ser editados no painel Postiz; a edição dentro da Kiara vale para rascunhos locais. Seleção de vários canais, configuração de todos os providers, aprovações e calendário visual por dia não estão completos. As rotas de métricas por post existem, mas a UI exibe apenas métricas de canal.

Tokens são uma etapa posterior: antes de cobrar, definir se uma unidade representa perfil novo, contato público entregue ou análise. Implementar ledger por organização com reserva, consumo, liberação e idempotência ligado ao job persistido. Uso próprio não deve descontar créditos fictícios. Não há carteira, pagamento ou cobrança ativada nesta alteração.

## Evidências de validação

Validação executada: 51 testes Python e 12 testes Node passaram na entrega anterior; build de produção e lint passaram. Nesta alteração, testes focados cobrem o schema/RLS, enfileiramento idempotente, conflito de chave, leases expirados, fencing contra worker obsoleto, backoff, pausa de segurança e persistência pelo worker. Dois harnesses de navegador passaram com APIs simuladas na entrega anterior.

Testes Python: social API, worker client, competition/archive/provider e suite browser-worker. Testes Node: server-client, exportação CSV e rotas Postiz com upstream mockado. Browser harnesses exercitam os componentes reais contra respostas interceptadas: agendamento, TikTok, métricas, edição PUT/If-Match, filtros, download CSV e largura mobile. Capturas em apps/web/tests/content-postiz-*.png e competition-mobile.png. Isso não substitui validação com PostgreSQL, Instagram e Postiz reais.

Comandos a partir da raiz:

```powershell
$env:PYTHONPATH='services/api'
.\.venv\Scripts\python.exe -m pytest services/api/tests/test_social_api.py services/api/tests/test_browser_worker_client.py services/api/tests/test_competition.py services/api/tests/test_competition_archive.py services/api/tests/test_competition_jobs.py services/api/tests/test_competition_worker.py services/api/tests/test_competition_job_routes.py services/api/tests/test_kiara_competition_provider.py services/browser-worker/app -q -p no:cacheprovider
node --test apps/web/tests/server-client.test.mjs apps/web/tests/competition-export.test.mjs apps/web/tests/postiz-routes.test.mjs
```

Os harnesses content-browser-check.py e competition-browser-check.py requerem rota temporária /ui-verification, fora do layout autenticado, renderizando ContentWorkspace ou CompetitionConsole conforme query view=competition. Não manter essa rota no produto; a rota usada para validação foi removida.

Referências funcionais: https://docs.postiz.com/public-api/introduction e https://help.mailerfind.com/en/category/how-to-use-mailerfind-auz9v/.
