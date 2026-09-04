# Kiara SDR

Workspace local-first de uma especialista SDR para Windows. A Kiara pesquisa empresas,
valida sinais comerciais, qualifica oportunidades e mantém um pipeline local com próxima ação.
Ferramentas de sistema, pesquisa e produtividade são capacidades auxiliares da operação comercial.

O produto inicial é desenhado para autônomos, vendedores de serviços e pequenas empresas. Na
primeira abertura, configure em **Configurar minha operação** o serviço vendido, nichos, regiões,
cliente ideal, proposta de valor, ticket e limite diário. Esses dados orientam a pesquisa e tornam
o score explicável para a realidade de cada vendedor.

## Fluxo comercial

1. Configure oferta e ICP.
2. Peça leads por nicho e região.
3. A Kiara verifica contato e sinais comerciais e grava os resultados no pipeline.
4. Revise o dossiê e os motivos do score antes da abordagem.
5. Registre o resultado do contato; a etapa do funil e as métricas são atualizadas.
6. Defina sempre uma próxima ação para evitar oportunidades esquecidas.

O score é uma priorização baseada em sinais observáveis, não uma garantia de venda. O primeiro
contato permanece sob controle do usuário e os limites diários ajudam a evitar prospecção abusiva.

## Arquitetura

- `AgentCore` interpreta pedidos comerciais, executa pesquisas e alimenta o pipeline.
- `LeadStore` persiste leads, qualificação, etapa, score e próxima ação em SQLite.
- `ToolRegistry` valida, autoriza, executa e audita cada capacidade.
- `PermissionGate` mantém ações críticas sob confirmação até no modo autônomo.
- `ScreenPerception` usa APIs do Windows e screenshot apenas sob demanda.
- `EventBus` fornece a base assíncrona para voz, automações e percepção incremental.
- `AgentRouter` mantém a identidade SDR e usa pesquisa e produtividade como apoio especializado.

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

## Navegador e mensagens sociais

A Kiara usa um perfil Chrome persistente e local em `data/browser-profile`, ignorado pelo Git.
No primeiro uso, diga `abra o Instagram da Kiara`, `abra o WhatsApp da Kiara` ou
`abra o Telegram da Kiara` e faca login manualmente. Depois, comandos como estes ficam
disponiveis:

```text
pesquise no Google como diagnosticar tela azul no Windows 11
mande uma mensagem no WhatsApp para +5511999999999 dizendo chego as 18h
abra o direct de @usuario no Instagram e escreva ola e envie
```

O envio de mensagens e uma acao critica: a Kiara apresenta uma confirmacao antes de enviar.
O conteudo da mensagem e redigido na confirmacao e nos registros. Instagram e Telegram usam
o nome de usuario; WhatsApp aceita o numero completo ou um contato existente. Mudancas nas
interfaces desses servicos podem exigir atualizacao dos seletores.

A navegação geral também aceita domínios, nomes de sites e ações acessíveis da página:

```text
abra example.com
abra o site da prefeitura de Curitiba
pesquise por como configurar uma impressora Wi-Fi
digite no campo Pesquisa com impressora laser
leia esta página
clique no botão Buscar
```

Abrir, pesquisar, ler e preencher sem enviar são ações automáticas. Cliques genéricos pedem
confirmação, pois o mesmo clique pode publicar, comprar, excluir ou enviar dados. Senhas nunca
são extraídas da tela nem gravadas no log. Para aplicativos, a Kiara reconhece os programas
nativos configurados e também procura uma correspondência exata nos atalhos do Menu Iniciar;
atalhos de desinstalação são bloqueados.

## Web Studio para estabelecimentos

Descreva somente dados confirmados do estabelecimento; não é necessário preparar uma imagem:

```text
crie um site completo para Café Aurora, cafeteria artesanal aberta das 8h às 18h
```

A Kiara perguntará se pode capturar a janela atual. Responda `use a tela`, `tire um print` ou
`sim` para usar uma captura efêmera. Se preferir uma foto, coloque um PNG, JPEG ou WebP em
`data/site-references` e responda `use a foto cafe.png`. Responda `não` para cancelar sem captura.

A geração pede confirmação porque a imagem é processada pelo modelo visual configurado. Antes
do envio, a Kiara valida e reprocessa a imagem, removendo metadados. Cada resultado é criado em
uma nova pasta dentro de `generated-sites`, contendo `index.html`, `styles.css` e `script.js`.
Projetos existentes não são sobrescritos e nenhum site é publicado automaticamente. Recursos
remotos, rastreadores, iframes, handlers inline, chamadas de rede e JavaScript dinâmico são
rejeitados.

Antes de declarar sucesso, o Web Studio inicia um servidor efêmero somente em `127.0.0.1` e
abre o projeto em um navegador Playwright isolado. O gate verifica mobile (390x844), tablet
(768x1024) e desktop (1440x900), overflow horizontal, erros de console/JavaScript, título,
`main`, `h1`, textos alternativos e rótulos acessíveis. Requisições externas são abortadas e
as screenshots de verificação não são persistidas. Se o gate falhar, o projeto permanece como
rascunho local e a Kiara não o apresenta como concluído.

## Hub MCP

Servidores MCP locais podem fornecer novas ferramentas à Kiara por `stdio`, com allowlist,
timeout, confirmação crítica e auditoria sem valores dos argumentos. Consulte
[`docs/MCP_HUB.md`](docs/MCP_HUB.md) para configurar e testar. Transporte HTTP/OAuth permanece
desabilitado nesta fase.

## Centro Pessoal

Tarefas e compromissos ficam persistidos localmente em `data/personal.db`. A busca pessoal
consulta somente nomes de arquivos, nunca o conteúdo, e fica limitada às pastas declaradas em
`personal.file_roots` no `config/kiara.yaml`. Exemplos:

```text
adicione uma tarefa comprar leite
liste minhas tarefas
conclua tarefa 12ab34cd
agende consulta para amanhã às 14:30
liste meus compromissos
encontre o arquivo contrato
crie um rascunho de email para pessoa@example.com assunto Olá mensagem Tudo bem?
```

E-mails são apenas salvos como rascunho nesse fluxo; criar um rascunho nunca o envia. A
sincronização real com Google Calendar, Gmail ou Microsoft 365 requer OAuth separado e permanece
desativada enquanto a conta não for conectada explicitamente.
