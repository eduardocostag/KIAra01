# Instagram Agent na Kiara

Origem: https://github.com/Jakeschincariol/instagram-agent-skill
Commit incorporado: `d03c56bb598be770c60b201f94237e5d1a4268a6`, licença MIT preservada.

As 13 skills e seus recursos estão em `app/resources/instagram_agent/skills`:
ig-reel, ig-viral, ig-caption, ig-carousel, ig-story, ig-profile, ig-plan,
ig-human, ig-comment, ig-reply, ig-dm, ig-repurpose e ig-audit.
São conhecimento de preparação de conteúdo. Não publicam posts nem enviam DMs.

O catálogo operacional da Kiara disponibiliza essas instruções ao agente. Os caminhos
`~/.claude/instagram/` citados no material original correspondem a `data/instagram/`
na Kiara. Copie e preencha `app/resources/instagram_agent/voice-template.md` em
`data/instagram/voice.md` para definir a voz da operação. Nunca invente resultados,
clientes ou métricas para preencher os exemplos.

`instagram_content_check` executa os seis utilitários locais sem rede ou dependências extras:

| operation | Entrada | Resultado |
| --- | --- | --- |
| hookscore | text | Propriedades do gancho e sinais de revisão |
| beats | text, wpm opcional, target_seconds opcional | Tempo estimado e sequência de cenas |
| caption | text, keywords opcional | Prévia de truncamento e revisão de legenda |
| humanize | text | Texto limpo e relatório das alterações |
| detect | text | Heurísticas de estilo |
| swipe | reels | Ranking relativo à mediana da conta, ou seguidores quando ausente |

Exemplo de chamada: `instagram_content_check(operation="caption", text="Seu rascunho")`.
Cada reel de swipe contém account, hook e views; median e followers são opcionais.
Os dados devem ser fornecidos pelo usuário ou por fonte autorizada. A ferramenta não coleta Instagram.

As heurísticas originais são voltadas ao inglês. Pontuação não prevê viralização, não é
detecção confiável de autoria e pode ser pouco representativa para português. Limites de
plataforma citados nas skills precisam de conferência antes de decisões de publicação.
Rascunhos não são persistidos nem incluídos nos parâmetros de auditoria desta ferramenta.
O envio oficial de mensagens já existente na Kiara continua usando suas permissões próprias.

## API web

O backend expõe endpoints autenticados com o mesmo Bearer token e contexto de organização
das demais rotas. Não aceita organização ou membership enviados no corpo:

- `GET /v1/instagram/skills`: catálogo das 13 skills.
- `GET /v1/instagram/skills/ig-reel?resource=hooks.json`: lê referências Markdown/JSON
  contidas na skill. Scripts e caminhos que saem da pasta são recusados.
- `POST /v1/instagram/content-check`: recebe operation, text e opções da tabela acima;
  exige papel owner, admin ou operator. Retorna result, metadata e publishing=false.

Exemplo de corpo: `{"operation":"beats","text":"Seu roteiro","target_seconds":30}`.
As análises executam no backend, sem enviar rascunhos a serviços de IA e sem persistência.
Respostas usam `Cache-Control: no-store`.

O deploy precisa preservar o pacote `app` e seus recursos, além de instalar PyYAML.
Quando executada com apenas `services/api` no PYTHONPATH, a integração encontra o pacote
no diretório raiz fixo do checkout. Imagens que copiem somente a API devem também copiar
o pacote `app` e os recursos. Ausência desses arquivos/dependências retorna 503.
