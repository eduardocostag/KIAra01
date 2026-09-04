# Revisão de mudança mínima

Data da revisão: 2026-09-04.

## Escopo examinado

Revisão somente leitura do diff rastreado em `app/`, `tests/` e `data/`. Nenhum arquivo de aplicação, teste ou dado foi alterado por esta revisão.

## Conclusão

**NEEDS SPLIT antes de integrar.** As alterações de código observadas são coerentes com suas finalidades, mas o diff atual não é uma unidade mínima: agrega otimização SQLite, atomicidade de memória, dashboard/filtros, importação/exportação CSV e dados gerados em execução.

## Achados

### 1. Estado operacional no diff — alto risco

`data/conversations.json` ganhou 136 linhas de conversas de teste e sete bancos em `data/` foram modificados. Esses artefatos não são necessários para entregar as correções de código e podem sobrescrever dados locais ou tornar o patch não reproduzível.

Correção mínima recomendada no momento de preparar a integração: excluir do patch somente as mutações de runtime em `data/`, depois de confirmar com o proprietário que elas não são dados intencionais. Esta revisão não as restaurou, pois pertencem ao worktree compartilhado.

### 2. Artefatos temporários rastreados como removidos — alto risco

O status inclui grande quantidade de exclusões sob `.tmp-test/` e `.test-artifacts/`, inclusive binários empacotados e bancos de testes. Elas dominam o status, geram erros de permissão durante inspeção e não justificam nenhuma das funcionalidades revisadas.

Correção mínima recomendada: não incluir essas exclusões na mesma integração. Qualquer limpeza ou mudança de ignore deve ser tratada separadamente e com confirmação, porque os caminhos já estão rastreados.

### 3. Quatro mudanças independentes no mesmo diff — risco de revisão

As unidades separáveis são:

1. índices e pragmas SQLite (`app/consumers/store.py`, `app/knowledge/store.py`, `app/leads/store.py`);
2. transação atômica de memória e seu teste (`app/memory/engine.py`, `tests/test_memory.py`);
3. dados reais, filtros e gráficos do cockpit (`app/ui/dashboard_widgets.py`, parte de `app/ui/desktop.py`, parte de `app/ui/sdr_cockpit.py`, `tests/test_sdr_cockpit.py`);
4. importação/exportação CSV na UI (`app/leads/__init__.py`, parte de `app/ui/desktop.py`, parte de `app/ui/sdr_cockpit.py`).

Recomendação: integrar e validar essas unidades separadamente. Não é necessário refatorar `desktop.py` para isso; basta separar os hunks na preparação dos commits.

### 4. Atomicidade da memória — mudança justificada

O parâmetro interno `_commit=False`, o `commit` final e o `rollback` em falha são todos necessários para impedir uma nova versão órfã quando o supersede falha. O teste com trigger cobre diretamente a regressão. Não foi identificada redução segura adicional nesse hunk.

### 5. Dashboard e CSV — nenhum reparo adicional comprovado

O diff substitui dados fictícios por estado derivado, conecta filtros e expõe importação/exportação. A inspeção não encontrou uma correção pontual obrigatória além das já presentes. Expandir tratamento de erros, abstrair helpers ou redesenhar a UI seria escopo adicional sem caso falho demonstrado.

## Evidência

- `git diff --numstat -- app data tests docs`: 526 adições e 83 remoções nos 17 arquivos resumidos pelo diff, além das exclusões temporárias exibidas no status.
- `git diff --` nos dez arquivos Python/testes modificados: revisão hunk a hunk concluída.
- Nenhum teste foi executado por esta revisão somente leitura; resultados de outros agentes não foram reapresentados como evidência própria.

## Follow-ups notados, mas não executados

- Confirmar quais mudanças em `data/` pertencem ao usuário antes de removê-las de qualquer patch.
- Preparar commits independentes para banco, memória, dashboard e CSV.
- Tratar a política de artefatos temporários em tarefa separada.

