# Kiara Hunter — contrato técnico de privacidade

## Decisão de lançamento

A Hunter pode pesquisar sinais comerciais públicos de forma proporcional, mas **não pode transformar perfis pessoais públicos em uma base arbitrária nem enviar DM fria automaticamente**. Informação pública continua sendo dado pessoal quando identifica uma pessoa; visibilidade não equivale a consentimento.

O controle executável está em `app/privacy/hunter_policy.py`. Ele não raspa nem envia: atua como gate fail-closed antes dessas fronteiras.

## Regras aplicadas

| Situação | Pesquisa/retenção | Contato Instagram |
|---|---|---|
| Empresa/perfil Business, fonte pública HTTPS, sinal real com até 90 dias, campos mínimos | Permitida por 30 dias, condicionada a teste documentado de legítimo interesse | Somente fila assistida; nunca DM automática |
| Consumidor que iniciou uma conversa | Contexto mínimo por até 180 dias para atender ao pedido | Responder dentro da finalidade; consentimento de canal continua sendo gate comercial |
| Consumidor apenas observado em perfil/post público | Bloqueada como prospecção B2C fria | Bloqueado |
| Dado sensível ou inferência sensível | Bloqueado | Bloqueado |
| Opt-out | Interrompe pesquisa ativa e sequência | Bloqueio imediato e persistente |

Campos aceitos são somente nome/handle/categoria/cidade/site da empresa, URL, sinal comercial público e data. Telefone/e-mail pessoal, cargo presumido, capacidade financeira, saúde, religião e outros enriquecimentos arbitrários não passam. Score deve explicar fatos comerciais e nunca inferir vulnerabilidade ou atributo sensível.

## Base legal, transparência e perfilamento

- `legitimate_interest_assessment_required` é condição técnica, não conclusão jurídica. Antes da campanha B2B, o controlador registra finalidade, necessidade, balanceamento, expectativa razoável, fonte e oposição.
- Consentimento é específico por finalidade e canal. Instagram não autoriza WhatsApp, e-mail, analytics ou treinamento.
- Pontuação serve à priorização interna, sem decisão de efeito jurídico/relevante; requer revisão humana, evidência rastreável e contestação/correção.
- Termos e APIs oficiais da Meta permanecem gates independentes.

## Mapa de dados e retenção

| Dado | Local | Finalidade | Prazo | Exclusão |
|---|---|---|---:|---|
| Sinal público empresarial mínimo | `consumer_organic_opportunities` | triagem comercial | 30 dias | purge por expiração/source URL |
| Identidade/contato declarados | `consumer_people`, `consumer_contacts`, `consumer_social_identities` | atender inbound consentido | até 180 dias | cascade por pessoa |
| Consentimento/opt-out | `consumer_consents`, `consumer_suppressions` | provar preferência/bloquear contato | finalidade; hash mínimo enquanto necessário | apagar conteúdo; preservar só hash de bloqueio |
| Mensagens | `consumer_touchpoints` | contexto operacional | até 180 dias | cascade por pessoa |
| Aprovação/envio | ledger Instagram | governança | prazo contratual documentado | exclusão/tombstone coordenado |

Os prazos são limites máximos. O runtime ainda precisa agendar `purge_expired` e aplicar retenção ao ledger, logs e backups. Sem job e evidência, retenção automática é gap de produção.

## DSAR e exclusão

`HunterPrivacyPolicy.rights_plan()` cobre pessoas, contatos, identidades, consentimentos, touchpoints, oportunidades, ledger, logs, backups e Meta. Um orquestrador deve resolver identidade, exportar formato legível, apagar idempotentemente, obter ACK de terceiros, verificar e emitir recibo sem conteúdo removido. Backups exigem tombstone/delete-on-restore. O hash de supressão pode permanecer separado e minimizado para honrar opt-out.

## Aceite antes de produção

1. Gate invocado antes de todo persist/contact da Hunter.
2. Crawler limitado à allowlist e prompt incapaz de ampliar finalidade.
3. Retenção, DSAR e deleção distribuída testados, incluindo logs/backup/Meta.
4. Aviso de privacidade no primeiro contato e oposição simples.
5. LIA/DPIA e decisão jurídica registradas; subprocessadores inventariados.

Evidência focal em 2026-09-04: testes cobrem pesquisa mínima, dados arbitrários/sensíveis, B2C público, inbound/consentimento, DM automática, opt-out e plano DSAR.
