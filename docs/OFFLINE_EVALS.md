# Evals offline da Kiara

`app.evals.OfflineEvaluator` oferece uma base determinística, sem rede ou modelo, para dois
gates iniciais:

- roteamento: acurácia exata, macro-F1 e latências p50/p95;
- contrato de resposta: presença de termos obrigatórios e ausência de alegações proibidas.

Os casos devem ter identificadores estáveis e representar linguagem real em pt-BR. Contratos
não medem se uma resposta é intelectualmente correta; eles protegem invariantes verificáveis,
como declarar incerteza, pedir confirmação em operações sensíveis e não alegar execução.

Execute com `pytest tests/test_offline_evals.py tests/test_metrics.py`. Para um gate de release,
grave um `EvalReport` em JSON e compare as métricas com limites versionados. Nenhum texto de
tela, memória pessoal ou resposta real deve ser incluído no corpus sem anonimização e consentimento.
