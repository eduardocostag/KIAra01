# Iniciar os serviços operacionais

O launcher usa os checkouts já preparados; não baixa dependências, cadastra provedores nem conecta canais.

```powershell
# Diagnóstico local sem gravar segredos ou iniciar processos:
powershell -NoProfile -File scripts/start_operational_services.ps1 -CheckOnly

# FreeLLMAPI em segundo plano, seguido do Chatwoot via Docker:
powershell -NoProfile -File scripts/start_operational_services.ps1

# Apenas FreeLLMAPI, em primeiro plano (Ctrl+C encerra):
powershell -NoProfile -File scripts/start_operational_services.ps1 -Service FreeLLMAPI

# Apenas Chatwoot:
powershell -NoProfile -File scripts/start_operational_services.ps1 -Service Chatwoot
```

FreeLLMAPI exige Node e os artefatos de `scripts/setup_freellmapi.ps1`. Chatwoot exige Docker Desktop com engine Linux e Compose v2. Se Docker não estiver disponível, `All` ainda inicia FreeLLMAPI e retorna código 2 indicando ativação parcial. Código 1 indica erro; 0 indica conclusão do comando, sem certificar saúde dos serviços ou canais. `-CheckOnly` sempre relata os pré-requisitos sem mutações.

No primeiro início, o launcher cria chaves aleatórias com RNG criptográfico e as guarda cifradas pelo Windows DPAPI para o usuário atual em `data/operational-services`. O diretório precisa estar ignorado pelo Git; o launcher verifica isso antes de escrever. Chaves nunca aparecem nos argumentos dos processos ou na saída. Variáveis já fornecidas no ambiente são importadas e preservadas; divergência com uma chave salva causa erro. Não remova esses arquivos nem troque de usuário/máquina sem um plano de backup: perder a chave pode impedir a leitura das credenciais dos provedores. Arquivo indecifrável não é substituído.

Se já existir banco FreeLLMAPI ou volumes Chatwoot sem chaves salvas, informe as chaves originais no ambiente. O launcher não gera substitutas nesse cenário. Os volumes Chatwoot pertencem ao projeto Docker `kiara-chatwoot`.

Em `All`, o PowerShell do FreeLLMAPI fica oculto e herda a chave somente pelo ambiente. Os logs são `data/operational-services/freellmapi.stdout.log` e `freellmapi.stderr.log`. O registro de PID inclui horário de criação; antes de reutilizá-lo, o launcher verifica também a linha de comando. Nunca encerra um processo pelo PID salvo. Porta 3001 ocupada impede um novo início. O launcher não configura inicialização automática no Windows.

Depois do início, abra `http://127.0.0.1:3001` para cadastrar os provedores e obter a chave unificada do FreeLLMAPI. Abra `http://127.0.0.1:3005` para concluir o onboarding do Chatwoot e conectar os canais. Esses passos exigem as contas e permissões do usuário; iniciar serviços não os substitui. A integração com a Kiara continua documentada em [FreeLLMAPI](freellmapi.md) e [Chatwoot](chatwoot.md).

Serviços locais não ficam acessíveis automaticamente pela API da Kiara hospedada na Vercel. O FreeLLMAPI pode encaminhar textos a provedores externos conforme as contas cadastradas; usar o launcher não garante gratuidade dessas contas.

Validação em 09/11/2026: parser PowerShell e `-CheckOnly` passaram; o início em contexto Windows com perfil carregado iniciou FreeLLMAPI. O painel respondeu HTTP 200 e `/v1/models` sem chave respondeu 401. Nova execução reconheceu o mesmo processo sem duplicá-lo. Docker estava ausente: Chatwoot permaneceu bloqueado e o launcher retornou código 2. Nenhum provedor foi cadastrado ou chamado. No sandbox, DPAPI e inspeção do processo do Windows falharam por restrições do contexto; execute o launcher em PowerShell normal do mesmo usuário.
