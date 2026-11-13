# Correção de conexão WhatsApp — 12/11/2026

## Causas confirmadas

- O logger HTTP da ponte escrevia diretamente em stdout. Sem console ou com o pipe do launcher fechado, a resposta podia ser interrompida antes dos cabeçalhos. O handler agora não depende de stdout.
- A sessão OpenWA estava presa a um Chrome do perfil exclusivo `data/openwa/sessions/session-34df8d07-fa00-4360-9ba3-d4d61e49d54a`; as novas inicializações falhavam com `browser is already running`. A sessão foi parada pela API; o navegador identificado pelo caminho exato foi encerrado e a sessão reiniciada sem apagar dados. O estado passou a `ready`, com `connected=true`.
- A alternativa por extensão falhava imediatamente ao encontrar a página de login do WhatsApp Web. Agora aguarda até três minutos pela vinculação; a página aguarda a resposta por tempo compatível.
- A extensão Kiara não foi encontrada nas preferências do perfil Chrome verificado. Foi disponibilizado o pacote 2.1.1 para instalação manual pela interface do Chrome.

## Serviço local

A revisão automática rejeitou interromper o Python da porta 3007 porque seu comando não comprovava a identidade da ponte. Esse processo foi preservado. Uma ponte nova e identificável foi iniciada em loopback na porta 3009, com PID/logs próprios e launcher `scripts/launch_whatsapp_local_bridge.ps1`. O frontend agora usa essa porta.

Testes HTTP reais da ponte nova: preflight OPTIONS 204 com CORS da origem de produção; POST sem autenticação 401. Esses testes não usaram token de cliente nem consultaram mensagens.

## Validação e publicação

- 11 testes Python da ponte aprovados, incluindo HTTP com stdout ausente e pipe fechado.
- 14 testes Node da extensão aprovados, incluindo espera pela leitura do QR.
- 4 testes de transferência/autorização da sessão aprovados; ESLint, Ruff e build Next.js/TypeScript aprovados.
- Teste de navegador com APIs interceptadas: QR sintético, polling até conectado, handshake da extensão, download e largura mobile aprovados.
- Deploy `dpl_8i3gTaMk4o298AJorE63kCtyFGbt`, READY em produção, `https://kiaralead.vercel.app`.
- Pacote da extensão respondeu HTTP 200; página WhatsApp sem sessão redireciona para login.

Não foi realizado novo vínculo pelo celular, pois a sessão existente se recuperou como conectada. Nenhuma mensagem foi enviada. A extensão continua exigindo instalação/recarregamento pelo usuário no Chrome. O serviço local precisa permanecer iniciado no computador que acessa a página.
