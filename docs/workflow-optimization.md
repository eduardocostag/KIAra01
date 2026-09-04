# Otimização do fluxo comercial — Kiara Lead Intelligence

**Data:** 2026-09-04  
**Responsável:** `workflow-optimizer`  
**Escopo:** onboarding → captação → qualificação → aprovação → pipeline  
**Status:** desenho operacional; metas precisam de baseline de piloto antes de serem tratadas como resultado

## Resultado recomendado

Adotar um fluxo único de cinco macrofases, com B2B e B2C separados por política de dados, mas usando a mesma linguagem operacional:

`Configurar uma vez → Captar com proveniência → Qualificar em um snapshot → Aprovar somente ação externa → Avançar pelo resultado`

A simplificação reduz handoffs lógicos, evita que o operador repita decisões já registradas e mantém julgamento humano nos pontos irreversíveis. Não se recomenda automatizar envio, consentimento, exceções de identidade, fechamento ou descarte de alto impacto.

## Linha de base observável

Esta auditoria encontrou estrutura e contratos, não telemetria de uso. Portanto, não há evidência atual de tempo de ciclo, taxa de abandono, retrabalho, conversão ou satisfação. A primeira melhoria obrigatória é medir o estado atual sem usar os dados existentes em `data/` como amostra comercial presumidamente válida.

| Dimensão | Estado atual documentado | Efeito operacional |
|---|---|---|
| Onboarding | UI atual organiza configuração em três abas; contrato de UX propõe sete etapas e reconhece lacunas de operação, canais, calendário/responsável e autonomia | risco de configuração incompleta e de expansão excessiva antes do primeiro valor |
| Captação B2B | pesquisa e CSV persistem leads; pesquisa não possui job durável e CSV não possui preview/lote/undo completo | espera opaca, correção manual e risco de mutação prematura |
| Captação B2C | descoberta pública e ingestão consentida são fluxos distintos | separação é necessária; reuni-los criaria risco de contato sem consentimento |
| Qualificação | regras explicáveis existem; geração e persistência B2B são separadas e B2C não tem snapshot versionado | artefatos podem divergir e o operador revisa informação repetida |
| Aprovação | gates existem nos artefatos, mas não há ledger ponta a ponta de preview, aprovação e tentativa | revisão pode ser repetida sem formar autorização segura para execução |
| Pipeline | B2B persiste etapa/evento e B2C persiste etapa; faltam undo/conflito e histórico B2C | movimentação manual pode divergir do resultado comercial |

## Fluxo futuro simplificado

### 1. Configurar uma vez

Substituir a percepção de “preencher tudo antes de começar” por dois checkpoints:

1. **Essencial para criar valor:** tipo de operação, empresa, oferta, ICP/persona e região.
2. **Obrigatório antes de contato:** canais autorizados, limites, desqualificadores, responsável/calendário, autonomia e política de dados.

Preço, diferenciais, casos, termos de proposta, modelo contratual e integrações ficam em **Aprimorar operação** e são solicitados no contexto da primeira ação que realmente dependa deles. O perfil é salvo como rascunho e reaproveitado; nenhum dado já confirmado deve ser pedido novamente.

**Automação segura:** validação em linha, preenchimento derivado sem sobrescrever entrada humana, checklist de lacunas e retomada no último checkpoint.  
**Intervenção humana:** aceitar política, autorizar canal, escolher autonomia e confirmar dados legais/comerciais.

### 2. Captar com proveniência

Oferecer três entradas explícitas: **Pesquisar empresas**, **Importar CSV** e **Receber opt-in B2C**. Cada entrada produz uma prévia com origem, validade, duplicatas, incompletos e efeitos; a confirmação cria um lote/job rastreável.

Sinais públicos B2C permanecem em uma caixa de oportunidades públicas e nunca viram pessoa contatável automaticamente. Deduplicação determinística acontece antes da gravação; conflito de identidade vai para revisão, não para merge automático.

**Automação segura:** normalização, deduplicação exata, validação, checkpoint, retry limitado e relatório por item.  
**Intervenção humana:** confirmar lote, resolver conflito e decidir se um sinal público merece CTA público autorizado.

### 3. Qualificar em um snapshot

Transformar `qualificação + dossiê + próxima ação + artefatos` em uma única unidade versionada e persistida atomicamente. Uma tela de revisão apresenta somente:

- decisão sugerida e confiança;
- razões determinantes, fatos e fontes;
- lacunas que mudariam a decisão;
- desqualificador, se houver;
- próxima ação recomendada.

Detalhes de reunião, proposta e contrato são expansões do mesmo snapshot, não novas etapas do funil. O operador escolhe **Aceitar**, **Corrigir** ou **Pedir evidência**. Correção alimenta a avaliação do modelo; não exige refazer todo o dossiê.

**Automação segura:** scoring explicável, detecção de lacunas, geração de briefing e priorização.  
**Intervenção humana:** aceitar SQL/desqualificação, corrigir fatos e decidir exceções.

### 4. Aprovar somente ação externa

Não criar uma etapa genérica “Aprovação” para todo lead. A aprovação é um gate ligado a uma ação irreversível: contato, proposta, desconto, termo jurídico ou publicação. O fluxo mínimo é:

`Preparar → Prévia imutável → Aprovar conteúdo+destinatário+canal → Revalidar política → Executar uma vez → Registrar resultado`

Uma aprovação válida deve referenciar hash, destinatário, canal e expiração. Editar qualquer elemento invalida a aprovação. Timeout vira `unknown` para reconciliação, nunca retry cego. Durante demonstração, a execução externa permanece desabilitada.

**Automação segura:** checagem de consentimento/supressão, limites, hash, validade e idempotência.  
**Intervenção humana:** aprovação final e resolução de resultado desconhecido.

### 5. Avançar pelo resultado

O pipeline é uma visão do estado comercial, não uma segunda fonte de verdade. Resultado registrado sugere a transição e a próxima ação; o operador confirma somente transições de alto impacto ou exceções. Exemplos:

| Evento confirmado | Transição sugerida | Ação humana |
|---|---|---|
| qualificação aceita | Novo/Pesquisa → Qualificado | confirmação simples ou regra previamente autorizada |
| resposta recebida | Contatado → Respondeu | registrar intenção e próxima ação |
| reunião agendada | Respondeu → Reunião | validar data/responsável |
| proposta aprovada/enviada | Discovery → Proposta | confirmar execução e prazo |
| assinatura confirmada | Contrato → Convertido | confirmação explícita |
| opt-out/desqualificador | qualquer ativo → Perdido/Bloqueado | motivo obrigatório; supressão preservada |

Toda transição grava evento, ator, motivo/origem e versão. Undo é compensatório e condicionado à ausência de evento posterior. Drag-and-drop permanece atalho visual, nunca bypass dos contratos.

## Etapas removidas ou consolidadas

| Antes | Decisão | Depois |
|---|---|---|
| configuração completa antes do valor | adiar campos não bloqueantes | essencial agora; políticas antes do contato; enriquecimento contextual |
| gerar qualificação e depois salvar dossiê/artefatos | consolidar | um snapshot atômico e versionado |
| revisar score, dossiê e próxima ação em pontos distintos | consolidar | uma decisão com explicação e lacunas |
| aprovação como estágio do lead | remover | gate por ação externa, com validade própria |
| mover Kanban e registrar interação separadamente | consolidar | resultado gera sugestão/transição e evento único |
| etapas detalhadas e seis macrocolunas sem regra canônica | padronizar | macrofase para gestão; subestado/evento para operação |
| nova revisão após falha transitória sem mudança de conteúdo | eliminar | reaproveitar aprovação válida; nunca reaproveitar após edição/expiração |

## KPIs operacionais e instrumentação

Medir por `operation_id`, `job_id/import_batch_id`, `entity_id`, `qualification_version`, `approval_id/action_id` e `event_id`, usando timestamps UTC e sem PII desnecessária nos eventos.

| KPI | Fórmula | Meta inicial de piloto | Cadência/guardrail |
|---|---|---:|---|
| conclusão do essencial | operações que concluem checkpoint 1 / operações que iniciam | ≥ 80% | semanal; segmentar por B2B/B2C |
| tempo até primeira captação | mediana de início do onboarding até primeiro lote confirmado | ≤ 15 min | semanal; P75 também obrigatório |
| ativação | operações com configuração essencial e ≥10 leads válidos / iniciadas | ≥ 70% no D1 | coorte semanal |
| rendimento da captação | itens válidos e não duplicados / itens processados | baseline nas 2 primeiras semanas; +20% relativo após correções | por fonte/lote |
| conflito/retrabalho de dados | itens enviados à revisão manual / itens processados | ≤ 10% após calibração | não automatizar merges para atingir meta |
| tempo de qualificação | mediana de lead captado a snapshot revisável | ≤ 5 min automatizado; medir espera externa separada | P50/P95 diário |
| aceitação sem correção material | snapshots aceitos / snapshots revisados | ≥ 75% em 14 dias | por versão/modelo |
| explicabilidade compreendida | revisões avaliadas como compreensíveis / avaliações | ≥ 80% após 20 revisões | pesquisa de 1 item |
| completude operacional | oportunidades ativas com próxima ação, prazo e responsável / ativas | ≥ 85% | semanal |
| first-pass approval yield | ações aprovadas sem edição / prévias revisadas | baseline; alvo ≥ 70% depois de 30 prévias | por tipo de ação |
| tempo de aprovação | mediana de prévia pronta a decisão humana | baseline; reduzir 30% sem reduzir revisão | P50/P90 semanal |
| envio indevido ou duplicado | ações externas sem aprovação válida ou duplicadas | **0** | alerta imediato/kill switch |
| aging por macrofase | mediana e P90 do tempo em cada macrofase | baseline por 2 semanas; reduzir P90 em 25% | semanal |
| conversão por transição | entidades que chegam à fase seguinte / elegíveis na fase anterior | baseline por coorte | não usar como prova causal do score |
| correção de etapa | eventos compensatórios / transições | ≤ 2% após implantação de undo | semanal |
| satisfação do operador | CSAT curto após 5 ciclos completos | ≥ 8/10 e ≥80% de resposta útil | quinzenal |

Metas sem baseline estão explicitamente classificadas como hipóteses operacionais. Comparar antes/depois por coortes equivalentes, reportar mediana, P75/P90 e volume amostral; não declarar ganho percentual com menos de 30 ciclos completos por fluxo.

## Implantação e gestão da mudança

### Fase 0 — Instrumentar (1–2 semanas)

- definir taxonomia única de eventos e início/fim de cada macrofase;
- capturar baseline de tempo, abandono, correção, aprovação e aging;
- entrevistar ao menos três operadores após cinco ciclos cada;
- publicar dashboard operacional sem dados fixos ou inferidos.

### Fase 1 — Quick wins (até 4 semanas)

- separar campos essenciais dos avançados no onboarding;
- apresentar lacunas e próxima ação em uma única revisão;
- remover “Aprovação” como estágio genérico da jornada;
- padronizar motivo de perda, bloqueio e correção;
- treinar operadores com um SOP de cinco macrofases e cenário dry-run.

### Fase 2 — Consolidação (até 12 semanas)

- implementar snapshot único de qualificação/dossiê/artefatos;
- adicionar jobs/lotes com preview, cancelamento, checkpoint e relatório;
- fazer eventos de resultado sugerirem transições e próxima ação;
- executar piloto A/B ou rollout por coorte, comparando tempo e retrabalho.

### Fase 3 — Automação protegida (até 26 semanas)

- ledger de aprovação/tentativa e reconciliação de `unknown`;
- transições automáticas somente para regras previamente autorizadas e reversíveis;
- alertas de aging, SLA e queda de rendimento por fonte;
- revisão mensal de métricas, feedback e regras; rollback se segurança, qualidade ou satisfação piorarem.

## RACI resumido

| Decisão | Responsável | Aprovador | Consultados |
|---|---|---|---|
| perfil/ICP e regras | operador comercial | dono/gestor | produto |
| política de dados/canais | produto/operação | DPO/negócio | segurança/jurídico |
| qualificação sugerida | sistema | operador | gestor/model QA |
| contato/proposta/contrato | operador | aprovador definido na política | jurídico quando aplicável |
| regra de transição automática | produto/operação | governança | segurança/QA |
| metas e decisão de rollout | analytics/produto | patrocinador | operadores/engenharia |

## Dependências e critérios de sucesso

A otimização depende dos contratos de `docs/workflow-contracts.md`: job/lote persistente, snapshot versionado, histórico/undo e ledger de aprovação. Antes disso, o fluxo futuro é especificação, não capacidade entregue.

O piloto pode avançar quando houver baseline instrumentado, SOP compreendido pelos operadores, zero ação externa indevida, ≥85% das oportunidades ativas completas e evidência de redução de pelo menos 30% no tempo mediano entre captação e próxima ação revisada. GA continua condicionada aos demais gates técnicos, legais, visuais e operacionais.

## Fontes examinadas

- `docs/workflow-contracts.md`
- `docs/product-commercial-readiness.md`
- `docs/ux-architecture.md`
- `docs/ux-research-audit.md`
- `docs/codebase-map.md`
- `app/ui/commercial_settings.py`
- `app/leads/intelligence.py`
- `app/leads/store.py`

Análise documental e inspeção de leitura; nenhum teste foi executado e nenhum código foi alterado.
