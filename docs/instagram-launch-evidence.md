# Evidências de lançamento — Instagram B2C

Data da coleta: 2026-09-04  
Veredito: **NEEDS WORK para produção Meta; PASS para demonstração/piloto local assistido**.

## Escopo comprovado localmente

A especificação operacional é: `DM Instagram → persistência → qualificação conservadora → rascunho → aprovação humana → envio`. O gate executado usa os componentes reais de webhook, armazenamento SQLite, fluxo B2C, governança e cliente de mensageria. A única fronteira substituída é HTTP/Meta, por `ClosedMetaTransport`, que mantém chamadas em memória e não abre rede.

Comando executado:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_instagram_e2e.py tests/test_instagram_b2c_flow.py tests/test_instagram_pilot.py tests/test_instagram_integration.py tests/test_instagram_governance.py
```

Resultado observado: **32 passed in 1.15s**. O E2E foi executado mais dez vezes: **70/70 casos passaram**, zero falhas observadas, entre 0,40 s e 0,65 s por execução. O log textual está em `evidence/instagram/test-run-2026-09-04.txt`.

A fixture sanitizada `evidence/instagram/signed-dm.fixture.json` permite conferir o envelope e o resultado local esperado. Ela é sintética e não contém credencial nem dado pessoal real.

## Cenários comprovados

- assinatura HMAC válida aceita; assinatura forjada não persiste nem chega ao transporte;
- pessoa, touchpoint, qualificação e rascunho são persistidos no caminho válido;
- nenhuma chamada HTTP simulada ocorre antes de aprovação humana nominal;
- kill switch desligado bloqueia a entrega mesmo após tentativa de aprovação;
- opt-out posterior ao rascunho cancela a ação e mantém zero chamadas de transporte;
- 429/500/503 entram em espera persistida com retry limitado;
- reinício sem mapeamento seguro do destinatário falha fechado e não envia.

## Evidência visual

Não há, nesta coleta, painel dedicado que exponha o ciclo completo de inbox Instagram, consentimento, rascunho, aprovação e resultado. Portanto, **nenhum screenshot foi produzido ou reaproveitado como prova desse fluxo**. As imagens genéricas existentes do desktop/cockpit não demonstram integração Instagram e não sustentariam essa alegação.

## O que não foi comprovado

- app Meta configurado e aprovado, permissões ativas e conta profissional do cliente vinculada;
- challenge de webhook e entrega de evento originado pela infraestrutura da Meta;
- janela/política de mensageria válida para o caso real;
- envio para destinatário de teste autorizado e reconciliação de `message_id` real;
- rate limits, erros e latência observados contra a API oficial;
- experiência visual do operador para revisar/aprovar cada DM;
- operação contínua, monitoramento e recuperação numa máquina do cliente.

## Gate obrigatório antes do cliente

Usar conta/app de teste da Meta e destinatários explicitamente autorizados. Registrar, sem tokens ou conteúdo pessoal: horário, conta de teste, event ID mascarado, estado interno antes/depois, resposta/status da API e screenshot da inbox do destinatário. Executar pelo menos caminho feliz, assinatura inválida, duplicidade, opt-out concorrente e falha 429. Até isso ocorrer, a formulação comercial correta é **“piloto local assistido preparado para validação Meta”**, nunca “integração Instagram pronta para produção”.
