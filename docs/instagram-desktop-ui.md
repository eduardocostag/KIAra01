# Painel desktop do piloto Instagram B2C

## Escopo entregue

`app/ui/instagram_inbox.py` fornece uma caixa de entrada PySide6 para o piloto
assistido. Ela lista ações recentes do ledger de governança, mostra somente o
sufixo do hash do contato, o estado do rascunho, tentativas, qualificação
injetável e a base de consentimento do inbound DM.

O resumo de configuração aceita apenas indicadores booleanos de webhook,
credenciais e conta. Tokens, app secret, recipient ID e demais segredos nunca
são renderizados.

## Fronteira de segurança

- **Aprovar rascunho** chama somente `InstagramDMGovernance.approve`. Não chama
  `InstagramPilotService.approve_and_send` nem qualquer cliente HTTP.
- **Bloquear** muda ações elegíveis para `blocked_by_operator` e registra ator
  humano no audit log. Kiara não pode ser usada como ator.
- O kill switch global desabilita Aprovar e Bloquear e é apresentado em texto.
- O estado de entrega do Instagram também é exibido. Desabilitado é o padrão
  seguro, mas aprovação humana e autorização de entrega continuam sendo gates
  diferentes.
- A decisão de envio continua no serviço governado, que precisa revalidar
  aprovação, opt-out, TTL, retry e habilitação imediatamente antes do I/O.

## Composição

O widget recebe `InstagramDMGovernance`, `KillSwitch` e `actor_provider` por
injeção. `configuration` e `qualification_provider` são opcionais, facilitando
composição pelo runtime e teste sem Meta. A integração no shell principal deve
ocorrer quando o bootstrap possuir uma instância única e durável desses
serviços; criar uma segunda governança apenas para a tela produziria estado
divergente e não é seguro para o lançamento.

## Evidência

`tests/test_instagram_inbox.py` comprova aprovação sem envio/tentativa, ocultação
do identificador real, reflexo do kill switch e bloqueio humano. Os testes de
governança cobrem consulta, bloqueio terminal e ator obrigatório.
