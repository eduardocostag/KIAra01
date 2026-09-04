# Kiara Lead Intelligence — definição do MVP comercial

**Status:** definição de produto; não constitui aprovação de lançamento  
**Responsável:** Product Manager  
**Data:** 2026-09-04  
**Horizonte:** demonstração comercial e piloto assistido no Windows

## Press release do MVP

A Kiara Lead Intelligence ajuda vendedores de serviços e pequenas operações comerciais a transformar sinais permitidos e dados importados em oportunidades priorizadas, explicáveis e prontas para ação. Em vez de entregar uma lista de contatos, a aplicação local organiza um pipeline B2B ou B2C, separa fatos de hipóteses, aponta lacunas, recomenda a próxima ação e prepara materiais para reunião, proposta e contrato, mantendo qualquer contato externo sob aprovação humana. O primeiro lançamento será vendido como copiloto comercial local para operação assistida — não como robô autônomo de prospecção nem como CRM empresarial completo.

## Problema e decisão de escopo

O usuário-alvo perde tempo consolidando fontes, avaliando a qualidade de cada lead e preparando uma abordagem consistente. O custo não está apenas em encontrar contatos, mas em priorizar mal, abordar sem contexto e deixar oportunidades sem próximo passo.

O pedido original descreve simultaneamente produto, CRM, motor de pesquisa, automação multicanal, IA, governança, analytics e distribuição empresarial. Entregar tudo como requisito de uma primeira venda elevaria muito o risco e esconderia a proposta central. A decisão é lançar primeiro um **MVP local, assistido e auditável**, capaz de demonstrar o ciclo entre entrada autorizada e oportunidade preparada.

## Personas prioritárias

### B2B primária — dono-vendedor de serviços

- Autônomo, consultoria, agência ou pequena empresa com venda consultiva e ticket médio relevante.
- Opera o próprio funil ou uma equipe de até cinco pessoas; hoje usa planilha, WhatsApp e anotações dispersas.
- Precisa decidir rapidamente quem abordar, por quê e com qual próximo passo.
- Compra quando enxerga ganho de foco, preparo para reunião e controle sobre os dados.

### B2B secundária — SDR ou gestor de pequena operação

- Recebe/importa listas de empresas e precisa padronizar qualificação e handoff.
- Valoriza explicação do score, histórico, filtros, deduplicação e consistência do pipeline.
- Não deve receber promessa de multiusuário, RBAC, sincronização de CRM ou SLA empresarial no MVP local.

### B2C primária — operador de vendas inbound consentidas

- Pequena empresa que recebe pessoas por formulário, indicação, evento, WhatsApp Business ou conta oficial conectada.
- Precisa distinguir intenção real de sinal social fraco e comprovar consentimento antes do contato.
- Compra quando consegue ordenar demanda, registrar contexto e entregar um briefing seguro ao responsável pela venda.

### Comprador econômico

- Dono ou gestor comercial da pequena empresa.
- Avalia tempo economizado, oportunidades com próximo passo, segurança contra contato indevido e previsibilidade do pipeline.

## Proposta comercial do primeiro lançamento

**Categoria:** copiloto de inteligência comercial local para Windows.  
**Promessa:** “Da fonte autorizada ao próximo passo comercial, com evidência e controle humano.”  
**Modelo de adoção recomendado:** demonstração guiada → piloto assistido de 14–30 dias → licença por instalação/operação.  
**Nível de autonomia:** 3 — prepara ações e pede aprovação. Nenhuma mensagem, publicação, proposta ou contrato é enviado automaticamente.

## MVP obrigatório (Now)

1. Configuração guiada da operação: empresa, oferta, ICP/persona, região, ticket, qualificadores, desqualificadores e limite de contato.
2. Dois domínios explicitamente separados:
   - B2B: empresas e evidências de negócio;
   - B2C: pessoas originadas de fontes autorizadas, com consentimento/base legal e retenção.
3. Entrada de dados por CSV com preview/validação/deduplicação ou por fluxo de demonstração claramente identificado.
4. Qualificação explicável com score, dimensões, fatos, hipóteses, desconhecidos, confiança, desqualificadores e próxima ação.
5. Dossiê/handoff com resumo, evidências, perguntas de descoberta, objeções prováveis e preparação de reunião.
6. Rascunhos de abordagem, proposta e contrato sempre sujeitos a gates explícitos de revisão e envio.
7. Pipeline persistente com mudança de etapa, próxima ação, filtros essenciais e histórico suficiente para auditar o fluxo.
8. Dashboard calculado exclusivamente a partir dos dados persistidos, com estado vazio honesto e sinalização de demonstração.
9. Pesquisa/processamento sem janelas externas visíveis, com progresso real, cancelamento e origem dos resultados quando a fonte estiver disponível.
10. Instalador Windows reproduzível, diagnóstico local, ajuda mínima, backup/restore documentado e rollback de versão.

## Fora do MVP (Next/Later)

- Disparo autônomo ou em massa, scraping clandestino e coleta arbitrária de contatos pessoais.
- Integrações completas simultâneas com todos os CRMs e redes sociais; cada integração oficial exige descoberta, credenciais, termos e testes próprios.
- Multi-tenant, colaboração em tempo real, RBAC empresarial, mobile e cobrança embutida.
- Personalização avançada de etapas do Kanban e automações irrestritas.
- Atribuição de receita sofisticada, previsão de vendas e experimentação causal.
- Promessa de “closer autônomo”: no MVP, a Kiara prepara e recomenda; o humano negocia, aprova e envia.

## Critérios de aceite do produto

### Jornada B2B

- Dado um perfil comercial válido, quando o usuário importa ou pesquisa empresas de um nicho/região, cada registro persistido contém origem/data, empresa, localização, estado de verificação e confiança ou aparece como incompleto.
- O score exibe suas dimensões e razões; campo ausente não é promovido a fato.
- O usuário abre uma oportunidade e encontra fatos com fonte, hipóteses marcadas, lacunas críticas e próxima ação específica.
- A mudança de etapa e próxima ação permanece após fechar e reabrir a aplicação.
- Preparar contato, proposta ou contrato gera rascunho e aprovação pendente; não há envio externo durante demonstração/teste.

### Jornada B2C

- Uma pessoa somente entra pelo pipeline de pessoas a partir de fonte autorizada e payload validado; sinal social público isolado não cria consentimento.
- Sem consentimento válido para canal e finalidade, o status bloqueia contato e recomenda obter consentimento.
- Sinal social fraco isolado não produz SQL; intenção explícita, evidência e confiança mínima são necessárias.
- Revogação/expiração impede nova ação de contato, e retenção/exclusão são rastreáveis.
- O handoff mostra contexto verificado, perguntas pendentes, oferta recomendada e ação do responsável.

### Experiência e dados

- B2B e B2C nunca são misturados silenciosamente em banco, score ou tela.
- CSV inválido produz relatório por linha sem corromper registros válidos; exportação respeita os filtros visíveis e abre no Excel com caracteres pt-BR íntegros.
- Dashboard e funil mudam de forma consistente com período e etapa; não exibem números fixos ou inventados.
- Estados vazio, carregando, cancelado, erro de rede e provedor indisponível são compreensíveis e não simulam progresso.
- A interface principal funciona por teclado, mantém foco visível e não corta conteúdo nas resoluções homologadas.

### Segurança e operação

- Segredos não aparecem no repositório, UI, exportações ou logs; credenciais ficam em ambiente/armazenamento apropriado.
- Toda ação externa apresenta preview, alvo, canal e conteúdo e requer aprovação; cancelar/kill switch interrompe a execução.
- Uma instalação limpa, upgrade, desinstalação e rollback são testados em Windows suportado antes de GA.
- O produto não pode ser anunciado como pronto enquanto testes críticos, segurança, acessibilidade, desempenho, realidade e acabamento visual não tiverem evidência aprovada.

## Métricas de sucesso

Sem telemetria e pilotos reais, os valores atuais são **baseline desconhecido**. Eles devem ser medidos em pilotos consentidos, nunca fabricados a partir dos dados de demonstração.

| Resultado | Métrica | Meta do piloto | Janela |
|---|---|---:|---|
| Ativação | operações que concluem configuração e criam/importam ≥10 leads | ≥70% | primeiro dia |
| Valor inicial | operações que chegam a ≥3 oportunidades com dossiê e próxima ação | ≥60% | 60 minutos |
| Qualidade | oportunidades aceitas pelo operador sem correção material do status | ≥75% | 14 dias |
| Explicabilidade | scores classificados como compreensíveis pelo operador | ≥80% | após 20 revisões |
| Completude | oportunidades ativas com próxima ação e prazo | ≥85% | semanal |
| Eficiência | redução mediana no tempo de preparação de uma reunião | ≥40% | versus baseline do piloto |
| Segurança | contatos externos executados sem aprovação válida | 0 | contínuo |
| Privacidade B2C | contatos tentados sem consentimento válido | 0 | contínuo |
| Confiabilidade | sessões sem erro crítico ou perda de dados | ≥99% | piloto |
| Retenção inicial | operações que retornam e atualizam o pipeline | ≥50% | 7 dias |

**North Star provisória:** número semanal de oportunidades revisadas pelo humano que terminam com evidência suficiente e uma próxima ação aceita.

## Gates para oferta comercial

### Demonstração interna

- Cenários B2B e B2C do Rio Grande do Sul executados com dados claramente marcados como demonstração.
- Jornada principal gravada/capturada sem envio externo.
- Nenhum P0/P1 aberto na persistência, consentimento, aprovação ou integridade de dados.

### Piloto assistido

- Termos/privacidade, política de retenção, backup e procedimento de suporte publicados.
- Instalador testado em máquina limpa; logs e diagnósticos reproduzíveis.
- Limitações comerciais apresentadas por escrito: single-user/local, integrações dependentes de credencial e ausência de disparo autônomo.

### Disponibilidade geral

- Evidência dos gates técnicos e visuais pedidos; métricas de pelo menos três pilotos; suporte e atualização definidos.
- Critérios de rollback: perda/corrupção de dados, ação externa sem aprovação, quebra do gate de consentimento, erro crítico recorrente ou regressão de instalação.

## Evidência encontrada no repositório

- `app/leads/store.py`: pipeline B2B persistente, estágios, próxima ação, dados de qualificação, dossiê e artefatos comerciais.
- `app/leads/intelligence.py`: separação determinística entre fatos, inferências e desconhecidos, com gates para outreach, preço, jurídico e envio.
- `app/consumers/store.py`, `models.py`, `ingestion.py` e `intelligence.py`: domínio B2C separado, consentimento/base legal, retenção e bloqueio conservador de contato.
- `app/ui/commercial_settings.py`: configuração comercial guiada com oferta, ICP, ticket, regras, limites e divulgação progressiva.
- `app/ui/sdr_cockpit.py` e `app/ui/desktop.py`: dashboard, oportunidades, dossiê e Kanban ligados ao armazenamento.
- `app/leads/csv_io.py`: importação/exportação CSV existente.
- `README.md` e `docs/WINDOWS_INSTALL.md`: execução local, limites declarados e fluxo de build/instalação.
- A suíte contém testes específicos de leads, consumidores, score, cockpit, filtros, CSV, segurança e instalador; sua existência não equivale a aprovação — os resultados precisam ser executados e registrados pelos gates responsáveis.

## Riscos e decisões abertas

1. A configuração atual não cobre integralmente tipo de operação, canais autorizados, calendário/responsável e políticas detalhadas de autonomia; isso bloqueia afirmar onboarding empresarial completo.
2. Integrações reais dependem de credenciais, aprovação de plataformas e termos externos; o produto deve vender conectores como opcionais, não como capacidades universais já disponíveis.
3. A aplicação é local-first/single-user; chamar o MVP de “plataforma empresarial” sem autenticação, isolamento de tenant, SLA e operação de suporte seria uma promessa excessiva.
4. O valor do score ainda precisa de calibração com decisões humanas e resultados comerciais reais. Testes de software validam contrato, não eficácia de vendas.
5. Dados existentes em `data/` não podem ser tratados como evidência comercial sem confirmação de origem, consentimento e rotulagem de demonstração.

## Recomendação

Prosseguir para **demonstração comercial controlada**, condicionada aos gates técnicos, com posicionamento explícito de copiloto local assistido. Não aprovar ainda GA nem venda como automação empresarial autônoma. A próxima decisão de produto deve usar evidência de pilotos para escolher entre aprofundar o fluxo B2B (recomendado) ou ampliar integrações B2C; tentar fazer ambos simultaneamente dilui aprendizagem e aumenta risco regulatório.
