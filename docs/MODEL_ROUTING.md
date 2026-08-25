# Roteamento local de modelos

`ModelRouter` é um provider composto e opt-in. A factory existente continua escolhendo um
único provider; portanto, instalar ou importar o roteador não ativa rede, baixa modelos nem lê
credenciais.

O chamador fornece providers já construídos para os perfis `fast` e `reasoning`. O perfil
`vision` é opcional e só anuncia a capacidade visual se o provider correspondente a oferecer.
`LocalProfilePolicy` escolhe `reasoning` para entradas longas, código e marcadores explícitos de
análise; os demais turnos usam `fast`. Prompts JSON de especialistas são avaliados pelo campo
`user_message`, evitando que instruções internas aumentem artificialmente a complexidade.

Métricas locais:

- `model_router.route.<perfil>`: quantidade de decisões;
- `model_router.latency.<perfil>`: count, média, máximo, p50 e p95;
- `model_router.error.<perfil>`: falhas propagadas ao chamador.

O roteador não faz fallback silencioso: trocar um perfil após falha pode alterar qualidade e
privacidade e deve ser configurado explicitamente com os providers/fallbacks já existentes.
