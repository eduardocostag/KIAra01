# Checklist de lançamento B2C pelo Instagram

## Estado comprovado no software

- Webhook assinado com `X-Hub-Signature-256` é validado antes do parsing.
- Eventos repetidos são idempotentes e mensagens de eco são ignoradas.
- A DM recebida cria/atualiza uma pessoa B2C, registra consentimento de resposta ao inbound e touchpoint.
- A mensagem recebida é evidência; intenção permanece inferência até ser confirmada.
- Opt-out revoga o canal e impede rascunho/envio.
- A Kiara prepara rascunho; cada envio exige aprovação humana nominal.
- O kill switch nasce desligado e o envio possui claim transacional contra duplicidade.
- Nenhum scraping ou automação do navegador participa deste fluxo.

## Pré-condições externas obrigatórias

1. Usar uma conta profissional do Instagram pertencente ao cliente.
2. Criar/configurar o app na Meta e escolher o fluxo oficial de Instagram Login aplicável.
3. Obter acesso à permissão de mensagens exigida pelo fluxo escolhido e concluir App Review quando aplicável.
4. Configurar webhook HTTPS público, verify token e assinatura com o app secret.
5. Armazenar token e app secret fora do repositório, via ambiente ou cofre do Windows.
6. Ativar o acesso a mensagens/conectores nas configurações da conta profissional.
7. Validar em conta de teste: inbound real, evento duplicado, eco, opt-out, aprovação, envio e erro 429/5xx.
8. Confirmar política de privacidade, exclusão de dados, operador responsável e prazo de retenção.

## Limite comercial do piloto

O fluxo atende pessoas que iniciaram uma DM ou ingressaram por uma entrada oficial autorizada. Não autoriza DMs frias em massa, coleta arbitrária de perfis ou scraping. O identificador do destinatário fica apenas na memória do processo neste piloto; após reinício, entregas pendentes falham fechadas e exigem reconciliação.

## Variáveis esperadas

Copiar `.env.example` para a configuração local e preencher somente fora do Git:

- `KIARA_INSTAGRAM_ACCESS_TOKEN`
- `KIARA_INSTAGRAM_APP_SECRET`
- `KIARA_INSTAGRAM_VERIFY_TOKEN`
- `KIARA_INSTAGRAM_ACCOUNT_ID`
- `KIARA_INSTAGRAM_API_VERSION`

Sem essas credenciais e sem webhook público aprovado, o estado correto é **sandbox/dry-run**, não produção.
