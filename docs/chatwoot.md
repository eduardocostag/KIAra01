# Chatwoot na Kiara

O Chatwoot fornece caixas de entrada e conversas de atendimento. A Kiara usa sua
Application API; a configuração de WhatsApp, Instagram, email e demais canais
continua no próprio Chatwoot. Instalar o serviço não conecta automaticamente esses canais.

## Origem e edição

- Repositório: [chatwoot/chatwoot](https://github.com/chatwoot/chatwoot).
- Release fixada: [v4.19.1](https://github.com/chatwoot/chatwoot/releases/tag/v4.19.1).
- Commit: `caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82`.
- Imagem: `chatwoot/chatwoot:v4.19.1-ce`, fixada pelo digest
  `sha256:04895c7bd0550d9e74b45b7202787b56f7ee4e891ebbde0c429c8c32901b97cf`.

O digest foi consultado no registry oficial em 9 de novembro de 2026. O workflow
[CE upstream](https://github.com/chatwoot/chatwoot/blob/v4.19.1/.github/workflows/publish_foss_docker.yml)
remove `enterprise/` e publica a edição comunitária. O código principal usa MIT Expat;
o diretório `enterprise/` no checkout tem licença própria e não é disponibilizado pela
imagem CE desta integração. Componentes de terceiros mantêm suas licenças.

## Instalar no Windows

Requer Docker Desktop com engine Linux em funcionamento e Docker Compose v2.
O código foi baixado em `services/chatwoot`; esse checkout é local e ignorado pelo Git.
Não é necessário instalar Ruby, Node ou Rails no Windows para usar a imagem pronta.

```powershell
# Baixar/verificar somente o código, sem Docker ou containers:
powershell -NoProfile -File scripts/setup_chatwoot.ps1 -DownloadOnly
powershell -NoProfile -File scripts/setup_chatwoot.ps1 -CheckOnly

# Com Docker disponível, validar Compose e baixar as imagens fixadas:
powershell -NoProfile -File scripts/setup_chatwoot.ps1
```

O setup recusa checkout existente com origem, commit ou arquivos divergentes.
Não sobrescreve personalizações, não cria conta e não inicia o serviço.

Forneça estes segredos pelo ambiente do processo que executará o launcher:

| Variável | Requisito |
| --- | --- |
| `CHATWOOT_SECRET_KEY_BASE` | Pelo menos 64 caracteres alfanuméricos aleatórios |
| `CHATWOOT_POSTGRES_PASSWORD` | Pelo menos 24 caracteres aleatórios, sem quebra de linha |
| `CHATWOOT_REDIS_PASSWORD` | Pelo menos 24 caracteres aleatórios, sem quebra de linha |

Guarde os valores no seu gerenciador de segredos e reutilize-os ao reiniciar.
Trocar a senha no ambiente não altera uma senha PostgreSQL já inicializada em volume.
Os scripts não geram nem gravam `.env`, senhas ou tokens no repositório. O Docker
recebe variáveis de ambiente para os containers; administradores do daemon podem inspecioná-las.

```powershell
powershell -NoProfile -File scripts/run_chatwoot.ps1 -CheckOnly
powershell -NoProfile -File scripts/run_chatwoot.ps1
```

O launcher inicia Postgres e Redis, aguarda seus healthchecks, executa
`rails db:chatwoot_prepare` e inicia Rails e Sidekiq. Cada comando falha antes do próximo
se sua execução retornar erro. As migrações são limitadas ao banco Chatwoot deste Compose;
nenhuma migração do banco Kiara é aplicada pelo launcher.

Abra `http://127.0.0.1:3005` e conclua o onboarding inicial. A porta 3005 evita conflito
com o frontend de desenvolvimento da Kiara na porta 3000. O Compose desativa signup
público e relay de push. O onboarding da primeira instalação permanece disponível.
Somente Rails publica porta no host; Postgres e Redis ficam na rede privada do Compose.
Para acessar o Chatwoot a partir de um backend remoto, configure uma instalação separada
com HTTPS: `127.0.0.1` do seu computador não é acessível pelo servidor da Kiara.

## Persistência e interrupção

```powershell
powershell -NoProfile -File scripts/run_chatwoot.ps1 -Action Status
powershell -NoProfile -File scripts/run_chatwoot.ps1 -Action Stop
```

O projeto Docker `kiara-chatwoot` mantém três volumes: `postgres_data`, `redis_data` e
`storage_data`. Parar containers preserva banco, filas e anexos. Os scripts não removem
volumes. Faça backup consistente do Postgres e dos anexos antes de atualizar a versão.

O Compose desta entrega está preparado para execução local em loopback. Não inclui domínio,
TLS, SMTP, credenciais Meta, armazenamento S3 ou exposição pública de webhooks.

## Conectar a Kiara

Depois de criar a conta no Chatwoot, obtenha o ID da conta e o token de acesso de um
usuário dedicado em suas configurações de perfil. O acesso disponível depende das permissões
desse usuário e das inboxes das quais ele participa. Não coloque o token no chat, no YAML
ou em código versionado. Configure as credenciais na integração da Kiara ou no ambiente
do runtime:

```powershell
$env:CHATWOOT_BASE_URL = 'http://127.0.0.1:3005'
$env:CHATWOOT_ACCOUNT_ID = '1' # Substitua pelo ID real da sua conta.
# CHATWOOT_API_ACCESS_TOKEN deve vir do seu gerenciador de segredos.
python -m app
```

Com o token no ambiente, o bootstrap registra `chatwoot_read` e
`chatwoot_send_message`. Exemplos de comandos:

```text
liste caixas do Chatwoot
liste conversas abertas no Chatwoot
leia mensagens da conversa 42 no Chatwoot
responda no Chatwoot na conversa 42 dizendo Olá
```

O número 42 é um exemplo: selecione uma conversa real da conta configurada.
Sem token nenhuma ferramenta é registrada. Defina `integrations.chatwoot.enabled: false`
para desabilitar o recurso mesmo com token no ambiente. O token também pode ser carregado
da `.env.local` na raiz pelo carregador de segredos existente; URL e conta vêm do
ambiente do processo ou do YAML. As credenciais não são persistidas por estes scripts.

A leitura de conversas e mensagens não envia respostas. O envio deve apontar uma conversa
específica, mostrar uma confirmação ao operador e usar uma mensagem `outgoing`, pública.
Não repita automaticamente um envio cujo resultado ficou incerto após timeout: confirme o
histórico no Chatwoot antes de tentar novamente. A API não garante deduplicação de mensagens
pela simples repetição de uma chave local.

## Backend do site

O backend usa o armazenamento cifrado existente de integrações por organização.
Cadastre o provider `chatwoot` por `PUT /v1/integrations/chatwoot`, autenticado com
perfil que tenha `integrations.manage`, usando o objeto `credentials` com
`endpoint_url`, `api_access_token` e `account_id` (todos valores string).
A URL deve ser uma origem HTTPS pública; endpoints locais e LAN não são aceitos no backend.

Rotas disponíveis quando banco e chave de cifragem estão configurados:

| Método | Rota | Ação |
| --- | --- | --- |
| GET | `/v1/chatwoot/inboxes` | Listar caixas |
| GET | `/v1/chatwoot/conversations` | Listar conversas com status/page/limit |
| GET | `/v1/chatwoot/conversations/{id}/messages` | Ler mensagens com before/limit |
| POST | `/v1/chatwoot/conversations/{id}/messages` | Enviar content com confirmed=true |

O envio exige owner/admin, conforme a permissão existente `outbound.approve`.
O corpo aceita `content` até 4.000 caracteres e `confirmed: true` como booleano.
O desktop aceita até 10.000 caracteres e exige o gate de confirmação local.
Contas, tokens e URLs são selecionados pelas credenciais da organização autenticada;
o request não pode trocar a conta de destino. Respostas têm `Cache-Control: no-store`.
Falhas de envio retornam resultado incerto e não disparam retries automáticos.

A migration `services/api/migrations/0027_chatwoot_integration.sql` atualiza a lista
de providers permitidos no banco Kiara. Ela foi aplicada na
[publicação comercial](commercial-release.md). Em outra instalação, aplique pelo processo
normal de migração antes de cadastrar credenciais no ambiente alvo.
O deployment deve incluir o pacote Python `app` com o cliente compartilhado; publicar
somente `services/api` sem o runtime retorna indisponibilidade. A publicação comercial
inclui esse runtime e a configuração de Chatwoot no frontend. O Chatwoot também mantém
seu próprio painel de atendimento.

As consultas diretas no desktop exibem os dados sem chamada de modelo. Conteúdo lido e
texto de resposta são omitidos do histórico enviado ao modelo e do aprendizado por
feedback nesse caminho; a interface ainda pode exibir e manter seu histórico local.

## Estado verificado

O checkout e os digests das imagens foram verificados. Os scripts PowerShell foram
analisados pelo parser e executados em modo `-CheckOnly`. O YAML foi analisado e suas
ligações de serviços, portas, volumes e referências de ambiente foram conferidas.
Docker não está instalado no ambiente desta entrega; pull de imagens, criação de containers,
migrações Rails e atendimento real ainda não foram executados. Isso não equivale a uma
instalação Chatwoot ativa.
