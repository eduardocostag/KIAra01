# Kiara no servidor Debian (24 horas, grátis)

Este pacote deixa a Kiara rodando sem parar numa máquina Debian em casa:

- **Kiara Chat**: conversa, voz da Kiara, transcrição de áudio e vídeos de apresentação, na porta 3008.
- **OmniRoute**: o roteador dos modelos de IA, na porta 20128.
- **Endereço público com HTTPS** pelo Tailscale Funnel. Não precisa de domínio, de IP fixo nem de abrir portas no roteador.

Os serviços iniciam com a máquina e reiniciam sozinhos se travarem.

## Do que você precisa
- Um PC ou notebook com Debian 12 ou 13, ligado na tomada e de preferência no cabo de rede. Recomendo pelo menos 8 GB de RAM.
- Acesso ao terminal dele, direto ou por SSH, com um usuário que possa usar `sudo`.
- Uma conta gratuita no Tailscale (tailscale.com). Dá para entrar com Google, Microsoft ou GitHub.

## Passo a passo

### 1. Baixar o código no Debian
```bash
sudo apt-get install -y git
sudo mkdir -p /opt/kiara
sudo git clone https://github.com/eduardocostag/KIAra01.git /opt/kiara/KIAra01
cd /opt/kiara/KIAra01
```
Como o repositório é privado, o git vai pedir seu usuário do GitHub e um **token de acesso** no lugar da senha. Para criar o token: GitHub → Settings → Developer settings → Personal access tokens.

### 2. Levar a configuração do seu computador (Windows)
O arquivo `.env.local` guarda as chaves da Kiara. Copie-o direto, sem mandar por WhatsApp nem por e-mail. No **PowerShell do Windows**, troque `usuario` e `IP-DO-DEBIAN`:
```powershell
cd $HOME\Desktop\KIAra01
scp .env.local usuario@IP-DO-DEBIAN:/tmp/kiara.env
```
Depois, no Debian:
```bash
sudo mv /tmp/kiara.env /opt/kiara/KIAra01/.env.local
```

### 3. Instalar
```bash
cd /opt/kiara/KIAra01
sudo bash deploy/debian/install.sh
```
Leva uns 10 a 20 minutos. Perto do fim, o script mostra um **link do Tailscale**. Abra esse link no navegador, entre na sua conta e, se ele pedir, **ative o Funnel**. No final aparece o endereço da Kiara, algo como `https://kiara-debian.tail1234.ts.net`.

### 4. Levar as contas de IA do OmniRoute
Assim você não precisa configurar tudo de novo. A pasta `.omniroute` tem as chaves dos provedores, então copie do mesmo jeito do passo 2. Primeiro, **feche o OmniRoute no Windows**. Depois, no PowerShell:
```powershell
tar -czf $env:TEMP\omniroute.tgz -C $HOME --exclude=.omniroute/logs --exclude=.omniroute/call_logs .omniroute
scp $env:TEMP\omniroute.tgz usuario@IP-DO-DEBIAN:/tmp/
Remove-Item $env:TEMP\omniroute.tgz
```
No Debian:
```bash
sudo tar -xzf /tmp/omniroute.tgz -C /var/lib/kiara && sudo rm /tmp/omniroute.tgz
sudo chown -R kiara:kiara /var/lib/kiara/.omniroute
sudo systemctl restart kiara-omniroute kiara-chat
```
Deixe o OmniRoute ligado só no Debian. Dois OmniRoutes usando as mesmas contas podem derrubar o login um do outro.

### 5. Apontar o site para o servidor
Na Vercel, abra o projeto do site, vá em **Settings → Environment Variables** e adicione:

| Nome | Valor |
|---|---|
| `NEXT_PUBLIC_KIARA_CHAT_URL` | o endereço do passo 3, por exemplo `https://kiara-debian.tail1234.ts.net` |

Depois faça um novo deploy. Pronto: o Chat, a voz e os vídeos passam a funcionar de qualquer lugar, sem o seu PC ligado.

### 6. Ligar as automações (a cada minuto)
O servidor chama a API da Kiara a cada minuto. Nessa chamada a API dispara os agendamentos, confere se entraram leads novos e executa os fluxos que estão na fila. Use o mesmo `KIARA_WORKER_TOKEN` que está nas variáveis da API na Vercel. Se ele ainda não existir, crie um valor longo e aleatório e cadastre na Vercel também.
```bash
sudo install -d -m 0750 /etc/kiara
sudo nano /etc/kiara/automation.env
```
Escreva duas linhas, com os seus valores:
```
KIARA_API_URL=https://kiara-api-rouge.vercel.app
KIARA_WORKER_TOKEN=cole-o-token-aqui
```
Depois rode `sudo bash deploy/debian/install.sh` de novo. Para conferir, use `systemctl list-timers kiara-automation.timer` e `journalctl -u kiara-automation -n 5`. O esperado é ver `tick HTTP 200`.

Sem o Debian ligado, qualquer serviço gratuito de cron (por exemplo, cron-job.org) pode fazer a mesma chamada a cada minuto: `POST https://SUA-API/v1/automation/internal/tick` com o cabeçalho `Authorization: Bearer SEU_TOKEN`.

## No dia a dia
| Para… | Comando no Debian |
|---|---|
| Ver se está tudo rodando | `systemctl status kiara-chat kiara-omniroute` |
| Ver o que a Kiara está fazendo | `journalctl -u kiara-chat -f` |
| Reiniciar | `sudo systemctl restart kiara-chat kiara-omniroute` |
| Atualizar após um push | `cd /opt/kiara/KIAra01 && sudo -u kiara git pull && sudo bash deploy/debian/install.sh` |
| Ver o endereço público | `tailscale funnel status` |

- **Painel do OmniRoute:** instale o Tailscale também no Windows, entre na mesma conta e acesse `http://NOME-DO-DEBIAN:20128`. Esse painel fica fora da internet pública; só aparece para os aparelhos da sua conta Tailscale.
- **Volta sozinho depois de queda de energia:** na BIOS do PC, ative a opção *Restore on AC power loss* (ou *After power loss: Power On*). Um nobreak ajuda a segurar quedas curtas.

## Segurança
- A Kiara só atende pedidos que vêm do site da Kiara e de pessoas logadas como dono ou admin da organização. O endereço público, sozinho, não dá acesso a nada.
- As chaves ficam somente em `.env.local` e `/var/lib/kiara/.omniroute`, e só o usuário `kiara` consegue lê-las.
- Nenhuma porta é aberta no roteador. O Tailscale cuida do HTTPS e do certificado.

## Ainda não incluído
O OpenWA, a conexão oficial do WhatsApp, entra num próximo passo. O launcher atual dele é específico do Windows.

## Servidor atual (Docker em /opt/kiara) e gateway da Kiara

O Debian em produção (192.168.1.12, `ssh kiara-debian`) roda OmniRoute, OpenWA, Ollama e Redis em Docker,
todos presos a 127.0.0.1. A única porta para fora é o gateway (`gateway/`, Caddy em 127.0.0.1:8088),
publicado por `tailscale funnel --bg 8088` (HTTPS com certificado do Tailscale).

- Todas as rotas, exceto `/healthz`, exigem `Authorization: Bearer $KIARA_GATEWAY_TOKEN`.
- `/ai/v1/*` → OmniRoute (`/v1`), `/wa/api/*` → OpenWA (`/api`). Painéis, Ollama e Redis não passam.
- As chaves reais do OmniRoute e do OpenWA ficam só em `/opt/kiara/gateway/.env` (root, 0600).
- Na Vercel (projeto kiara-api): `KIARA_SERVER_GATEWAY_URL` (https://kiara-debian.<tailnet>.ts.net),
  `KIARA_SERVER_GATEWAY_TOKEN` e `KIARA_CHAT_MODEL` (modelo/combo do OmniRoute).
  `GET /v1/server/status` (administrador) mostra o estado do gateway, da IA e das sessões do WhatsApp.

Instalar/atualizar o gateway:

```bash
scp deploy/debian/gateway/{Caddyfile,docker-compose.yml} kiara-debian:/tmp/
ssh kiara-debian 'sudo install -m 644 /tmp/Caddyfile /opt/kiara/gateway/ && sudo install -m 600 /tmp/docker-compose.yml /opt/kiara/gateway/ && sudo sh -c "cd /opt/kiara/gateway && docker compose up -d --force-recreate"'
```

Trocar o token: gere outro em `.env` (`openssl rand -hex 32`), recrie o contêiner e atualize a Vercel.
