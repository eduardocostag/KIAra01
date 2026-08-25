# Integração com Obsidian

A Kiara indexa um vault local em modo somente leitura. Nenhum plugin comunitário é
necessário e a integração não altera as notas.

## Ativação

Defina um caminho absoluto em `config/kiara.yaml`:

```yaml
integrations:
  obsidian:
    enabled: true
    vault_path: C:\Users\SeuUsuario\Documents\Meu Vault
    state: data/obsidian-index.json
    max_file_bytes: 2000000
    sync_interval_seconds: 10
    write_enabled: true
    feedback_learning_enabled: true
    feedback_prompt: Te auxiliei?
```

Na inicialização, arquivos Markdown novos ou modificados são indexados na base de
conhecimento. Notas removidas deixam o índice. `.obsidian` e `.trash` são ignorados.

## Notas privadas

Use uma propriedade no frontmatter para excluir uma nota:

```yaml
---
kiara_index: false
---
```

Também são aceitos `kiara: private`, `private: true` e `kiara_private: true`.
Todo o diretório `90 - Privado` é excluído mesmo sem frontmatter.

## Comandos

- `Sincronize o Obsidian.`
- `Pesquise no Obsidian por configuração de rede.`
- `Abra a nota Início no Obsidian.`
- `Salve no Obsidian: conteúdo da nova nota.`

A sincronização também ocorre automaticamente no intervalo configurado. Salvar uma nota
é uma ação sensível e sempre passa pelo gate de confirmação da Kiara. Novas notas são
criadas em `00 - Caixa de entrada` por meio de escrita atômica.

## Aprendizado por feedback

Quando `feedback_learning_enabled` está ativo, toda resposta normal termina com
`Te auxiliei?`. A resposta `sim` aprova apenas a última troca e cria uma nota em
`30 - Conhecimento/Aprendizados Kiara`. A resposta `não` descarta a troca. Se o usuário fizer
uma nova pergunta sem responder, a aprovação anterior também é descartada.

As notas aprovadas contêm a solicitação e a resposta/processo validado. Padrões conhecidos
de senhas, tokens e chaves de API são redigidos antes da escrita.

## Privacidade

- O indexador é somente leitura; a ferramenta separada de escrita exige confirmação.
- O estado incremental contém somente caminho relativo, hash e ID interno.
- O texto indexado permanece na base local de conhecimento.
- Se um provider remoto estiver ativo, trechos recuperados podem entrar no prompt remoto.
- Desative a integração ou marque notas privadas antes de usar um provider em nuvem.

Os resultados incluem URI oficial `obsidian://open` para retornar à nota original.
