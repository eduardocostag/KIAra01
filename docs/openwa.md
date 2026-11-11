# OpenWA local na Kiara

O OpenWA mantém a sessão WhatsApp como serviço HTTP local. Ele não exige uma
extensão do Chrome nem a API paga da Meta. A conexão inicial ainda exige que o
responsável vincule o aparelho pelo QR/código exibido no gateway. Sessões já
vinculadas são persistidas e retomadas no reinício.

Origem: [rmyndharis/OpenWA](https://github.com/rmyndharis/OpenWA), versão 0.30.0,
commit `44856156e121632cac8fb6f14d14633a6c2e3794`, licença MIT. O checkout fica em
`services/openwa`, ignorado pelo Git. A licença e a referência ficam em `infra/openwa`.

## Preparar e iniciar

Esta integração Windows usa Node >=22.19 e <25 e o Google Chrome já instalado.
Não precisa de Docker para o OpenWA. O Chatwoot é outro serviço e continua com
seus próprios requisitos (Rails, Postgres e Redis, via Docker nesta instalação).

```powershell
# Apenas baixar e verificar a origem/revisão:
powershell -NoProfile -File scripts/setup_openwa.ps1 -DownloadOnly
# Dependências fixadas e compilação do servidor e painel:
powershell -NoProfile -File scripts/setup_openwa.ps1
# Verificações sem iniciar serviço ou acessar segredos:
powershell -NoProfile -File scripts/setup_openwa.ps1 -CheckOnly
powershell -NoProfile -File scripts/run_openwa.ps1 -CheckOnly
# Iniciar em segundo plano:
powershell -NoProfile -File scripts/run_openwa.ps1 -Background
# Consultar/parar somente o processo registrado por esse launcher:
powershell -NoProfile -File scripts/run_openwa.ps1 -Action Status
powershell -NoProfile -File scripts/run_openwa.ps1 -Action Stop
```

Sem `-Background`, o serviço roda no terminal. O painel é servido em
`http://127.0.0.1:3006/`. O endpoint público de saúde é `/api/health`; a leitura
de sessões exige autenticação. Os dados ficam em `data/openwa`, não no checkout:
bancos SQLite separados para autenticação e mensagens, sessões, mídias e plugins.
Parar o processo preserva esses arquivos.

O setup usa os arquivos do lockfile com `npm ci --ignore-scripts`, verifica o
binding SQLite pré-compilado e executa explicitamente o `scripts/postinstall.js`
do upstream (dashboard e patches de dependências), antes de compilar. Isso evita
o `node-gyp rebuild` indevido que npm 11 pode inferir pelo marcador
`hasInstallScript` do lockfile para better-sqlite3 13, apesar de seu
`gypfile:false` e seus binários já incluídos. Não altera o lockfile nem faz
downgrade da dependência. O Chrome existente evita downloads globais do Puppeteer.

## Rede e chaves

O upstream inicia Node sem especificar host. O preload
`infra/openwa/loopback.cjs` restringe os listeners a loopback sem editar a origem.
Não existe porta pública, túnel nem exposição automática para a Vercel.

Na primeira execução, o launcher gera API master key e pepper com RNG
criptográfico e os persiste cifrados com DPAPI CurrentUser em `data/openwa`.
Não imprime chaves, não usa argumentos para transportá-las e não troca um arquivo
indecifrável. É necessário usar a mesma conta Windows com perfil carregado para
reiniciar. Se já houver banco sem chaves salvas, informe os valores originais por
`OPENWA_API_MASTER_KEY` e `OPENWA_API_KEY_PEPPER`; não há geração substituta.
O arquivo de conveniência plaintext `data/.api-key` do upstream é redirecionado
para o dispositivo Windows `NUL`; o segredo original permanece no arquivo DPAPI.

Antes de gravar chaves, o launcher verifica que `data/openwa/` está ignorado pelo
Git. Os logs locais são `stdout.log` e `stderr.log` nessa pasta. Configurações
que o operador salvar posteriormente no painel seguem o armazenamento do OpenWA;
não compartilhe nem versione sua pasta de dados.

O launcher fixa SQLite, armazenamento local, fila/Redis desligados, uma sessão,
pacing de 20 envios/dia e até cinco abordagens novas/dia, além dos controles da
Kiara. Esses limites não autorizam destinatários nem garantem entrega ou ausência
de restrições na conta. OpenWA é um cliente não oficial; não existe garantia de
que toda versão do WhatsApp continuará compatível.

## Chatwoot e IA

O upstream oferece o plugin Chatwoot em
[OpenWA-plugins](https://github.com/rmyndharis/OpenWA-plugins). A instalação do
gateway não configura automaticamente uma conta, inbox, token ou webhook do
Chatwoot e não ativa respostas de IA. A ponte da Kiara deve usar uma chave de
operador restrita à sessão e aos chats autorizados, em vez da master key de
bootstrap.

O OmniRoute é um serviço separado. Este launcher não chama modelos, não cadastra
provedores e não envia mensagens. As cotas e custos dos modelos dependem dos
provedores configurados no roteador; executar os gateways localmente não torna
qualquer modelo externo gratuito.

## Verificação

`node --test infra/openwa/loopback.test.cjs` verifica o bind local e a recusa de
interfaces públicas. Os parsers PowerShell e `-CheckOnly` são verificações sem
conexão WhatsApp. Vincular um número, receber eventos, refletir conversas no
Chatwoot e enviar uma resposta confirmada exigem validação autenticada separada.
