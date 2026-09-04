# Hub MCP da Kiara

O Hub MCP conecta ferramentas externas padronizadas ao mesmo controle de permissões, kill
switch e auditoria da Kiara. Nesta fase, somente servidores locais `stdio` são aceitos.
HTTP, SSE, OAuth e descoberta automática pela internet permanecem desativados.

## Configuração

Adicione cada servidor em `config/kiara.yaml`:

```yaml
mcp:
  enabled: true
  max_output_chars: 20000
  servers:
    - name: arquivos
      transport: stdio
      command: python
      args: [scripts/meu_servidor_mcp.py]
      env_vars: [MINHA_API_KEY]
      allowed_tools: [buscar_arquivo]
      timeout_seconds: 20
```

`env_vars` contém apenas nomes. O valor deve existir no ambiente ou `.env.local`; nunca coloque
o segredo no YAML. O processo recebe somente essas variáveis explicitamente nomeadas, além do
ambiente mínimo aplicado pelo SDK oficial.

Uma ferramenta só pode ser executada quando também aparece em `allowed_tools`. Toda chamada
MCP é classificada como crítica e exige confirmação. Argumentos são entregues ao servidor, mas
seus valores não aparecem na confirmação nem na auditoria: ficam registrados apenas nomes e
tipos dos campos. Erros externos são reduzidos a uma descrição sanitizada.

## Comandos

```text
liste os servidores MCP
liste as ferramentas MCP do servidor arquivos
execute a ferramenta MCP buscar_arquivo do servidor arquivos com argumentos {"nome":"manual.pdf"}
```

A execução genérica `call_mcp_tool` não é disponibilizada ao planejador autônomo. Assim, um
modelo não pode escolher arbitrariamente uma ferramenta externa; é necessário um comando
explícito e a confirmação do usuário.

## Diagnóstico local

O projeto inclui um servidor MCP sem rede para testar negociação, descoberta e execução:

```powershell
.\.venv\Scripts\python.exe scripts\verify_mcp_runtime.py
```

O resultado esperado é `MCP_RUNTIME_OK=True`.
