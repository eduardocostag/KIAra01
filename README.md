# Kiara Assistant

MVP local-first de uma assistente pessoal para Windows. A Fase 1 prioriza um fluxo vertical
executável: entrada em linguagem natural, contexto da janela ativa, ferramentas locais com
permissões, PowerShell allowlisted, screenshot sob demanda, auditoria redigida e kill switch.

## Arquitetura

- `AgentCore` interpreta pedidos e roteia ferramentas; um provedor de LLM é substituível.
- `ToolRegistry` valida, autoriza, executa e audita cada capacidade.
- `PermissionGate` mantém ações críticas sob confirmação até no modo autônomo.
- `ScreenPerception` usa APIs do Windows e screenshot apenas sob demanda.
- `EventBus` fornece a base assíncrona para voz, automações e percepção incremental.
- `AgentRouter` seleciona especialistas de software, segurança, produtividade e pesquisa; quando
  mais de um domínio se aplica, compõe as análises em uma resposta única. Solicitações sem domínio
  claro usam o generalista. Especialistas orientam, mas não recebem nem executam ferramentas.

Python 3.12, `asyncio`, pywin32, MSS e YAML formam a base. PySide6, voz, OpenAI e Playwright
são extras isolados para não tornar o núcleo dependente de nuvem ou de uma GUI específica.

## Instalação e execução

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,ui]"
python -m app --diagnostics
python -m app
```

`python -m app` abre a janela compacta e mantém a Kiara disponível na bandeja do Windows.
O menu da bandeja permite reabrir a conversa, interromper ações e encerrar a aplicação. Fechar
a janela apenas a oculta; **Sair** encerra a thread de trabalho e aciona o kill switch. Para usar
somente o terminal, execute `python -m app --console`. Sem PySide6, o console é usado como fallback.

Comandos demonstráveis no console:

- `Kiara, abra o bloco de notas.`
- `Kiara, qual programa estou usando?`
- `Kiara, execute no PowerShell o comando hostname.`
- `Kiara, o que estou vendo?`
- `Kiara, analise esta tela e me ajude a resolver o erro.`
- `Kiara, faça um diagnóstico do computador.`
- `Kiara, faça um diagnóstico dos drivers.`
- `Kiara, verifique se resolveu o driver.`
- `Kiara, planeje e execute a correção deste problema.`

PowerShell pede confirmação e somente aceita comandos em `config/kiara.yaml`. `/parar` encerra
subprocessos registrados; `/sair` fecha a sessão.

### Visão e execução controlada

A janela ativa é acompanhada localmente e, quando seu conteúdo muda, o modelo visual cria um
resumo semântico efêmero. Perguntas relacionadas à tela solicitam uma leitura visual atualizada;
ao trocar de janela, a leitura anterior deixa de ser usada. Pixels, texto acessível e resumos de
tela são removidos antes de qualquer tentativa de chamada a um modelo em nuvem.

O Computer Use utiliza seletores semânticos do Windows UI Automation, nunca coordenadas geradas
pelo modelo. Pedidos explícitos com `planeje e execute` podem criar até cinco passos. Cliques,
digitação, teclas e operações de janela mostram a ação proposta e exigem confirmação humana.
Depois da execução, a Kiara verifica uma pós-condição e, quando disponível, compara o estado
visual efêmero anterior e posterior. O menu **Parar ações** continua sendo o kill switch.

O atendimento de helpdesk também pode criar uma linha de base somente leitura para `overview`,
`drivers`, `network`, `battery` ou `events`. Ao pedir uma verificação, a Kiara repete a mesma
consulta e compara as evidências. Drivers só são marcados como recuperados quando a contagem de
dispositivos com código de erro cai de um valor positivo para zero; rede exige que adaptadores
antes indisponíveis apareçam operacionais. Outros resultados são apresentados como mudanças, não
como prova de resolução, até que exista um teste funcional específico.

## Providers de IA

Para a cadeia gratuita com NVIDIA Nemotron, Ling, Vercel AI Gateway e Ox Alpha, consulte
[`docs/FREE_AI_PROVIDERS.md`](docs/FREE_AI_PROVIDERS.md). Provedores sem chave são ignorados e o
Ollama permanece como fallback local; contexto visual e dados privados locais não são enviados.

Em `config/kiara.yaml`, defina `llm.provider` como `local`, `openai` ou `ollama`, além de
`llm.model`. Também há suporte a endpoints compatíveis com OpenAI usando `groq`, `openrouter`
ou `gemini`. Para esses provedores, defina a chave somente no ambiente:

```powershell
$env:KIARA_LLM_PROVIDER = "groq"
$env:KIARA_LLM_MODEL = "llama-3.1-8b-instant"
$env:GROQ_API_KEY = "..."
```

Para manter a aplicação disponível quando o limite gratuito falhar, configure um fallback:

```powershell
$env:KIARA_LLM_FALLBACK_PROVIDER = "ollama"
$env:KIARA_LLM_FALLBACK_MODEL = "kiara-stable:latest"
```

Para OpenAI, instale o extra `openai` e forneça a credencial somente pelo ambiente:

```powershell
$env:OPENAI_API_KEY = "..."
```

Ollama usa `http://127.0.0.1:11434` por padrão; `OLLAMA_HOST` pode substituir esse endereço.
Visão no Ollama exige um modelo multimodal e `llm.vision_enabled: true`. `KIARA_LLM_PROVIDER`
pode substituir temporariamente o provider. Nenhum segredo deve ser gravado no YAML.

## Base de conhecimento local

`KnowledgeStore` ingere `.txt`, `.md` e `.pdf`, cria chunks com sobreposição e evita ingestões
duplicadas pelo hash SHA-256 do arquivo. O índice fica em `data/knowledge.db` e combina FTS5 com
embeddings quando um `EmbeddingProvider` é fornecido; busca lexical continua disponível sem eles.
PDF requer o extra `knowledge`. Resultados relevantes são incluídos no contexto conversacional
como `relevant_knowledge`, preservando fonte, posição do chunk e metadados.

Um vault local do Obsidian pode ser conectado em modo somente leitura, com sincronização
incremental, exclusão de notas privadas e links de volta à origem. Consulte
[`docs/OBSIDIAN_INTEGRATION.md`](docs/OBSIDIAN_INTEGRATION.md).

## Limites atuais da Fase 1

O núcleo, percepção de janela, screenshot, ferramentas, auditoria e console funcionam localmente.
STT/TTS, overlay e análise multimodal requerem os extras e adapters de runtime ainda não
concluídos. Modelos remotos dependem de rede e credenciais; o fallback local não envia dados.

Riscos principais: conteúdo malicioso na tela, vazamento por screenshot, comandos perigosos,
privilégios excessivos e interrupção incompleta. O MVP reduz esses riscos com captura sob demanda,
allowlist exata, confirmação, processo PowerShell sem perfil, timeout, redação e kill switch.

## Instalador Windows

O projeto inclui um instalador Inno Setup por usuário, com upgrade no mesmo diretório,
desinstalação, atalhos opcionais e autostart opt-in. Consulte
[`docs/WINDOWS_INSTALL.md`](docs/WINDOWS_INSTALL.md) para o build reproduzível e o gate de
assinatura Authenticode.

## Evolucoes locais

- Memoria tipada e separada por perfil pessoal/trabalho, com proveniencia, expiracao,
  revisoes versionadas, consolidacao sem apagar fontes e explicacao da pontuacao recuperada.
- Planejamento persistente em `data/planning.db`, com checkpoints, pausa/retomada apos reinicio,
  estimativas e autorizacao explicita para objetivos de alto risco. O recurso permanece opt-in.
- Automacoes com previa sem execucao, rascunhos ensinados desativados, modelos seguros,
  historico e repeticao manual idempotente de falhas.
- Validacao visual opcional antes/depois de Computer Use. Somente assinaturas perceptuais
  efemeras ficam na memoria; imagens e hashes nao entram no log.
- Painel de auditoria com timeline limitada e exportacao redigida.
- Voz com endpointing adaptativo, wake word apenas no inicio do comando, protecao por wake word
  em cada turno e selecao opcional de uma voz SAPI instalada.

Os recursos invasivos continuam desligados por padrao. Habilite-os individualmente em
`config/kiara.yaml`; toda ferramenta continua sujeita ao mesmo gate de permissao e auditoria.
