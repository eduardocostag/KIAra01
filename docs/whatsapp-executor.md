# Usar o WhatsApp Web já conectado no Chrome

A extensão da Kiara usa a guia atual do WhatsApp Web no Chrome; ela não cria um perfil novo nem pede outro QR code enquanto a sessão existente permanecer conectada. A versão 2 permite ler conversas e executar respostas solicitadas pela caixa de entrada ou pela operação previamente habilitada. Nenhuma automação é ativada apenas por instalar a extensão.

## Configuração inicial

Faça estes passos uma vez no computador que já tem o WhatsApp Web conectado:

1. Prepare o executor local e instale as dependências:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -e .
   ```
2. No Chrome, abra `chrome://extensions`, ative **Modo do desenvolvedor** e escolha **Carregar sem compactação**. Selecione a pasta `extensions\kiara-whatsapp` dentro do repositório Kiara.
3. Volte à guia WhatsApp Web já conectada e atualize-a uma vez para ativar a extensão nessa guia.
4. Confira se `apps/web/.env.local` contém `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Configure também um modelo que já esteja instalado no Ollama:

   ```dotenv
   KIARA_WHATSAPP_OLLAMA_MODEL=nome-do-modelo-instalado
   ```

   Use `ollama list` para conferir os nomes disponíveis. Se o Ollama não estiver em `http://127.0.0.1:11434`, configure também `KIARA_WHATSAPP_OLLAMA_URL` com o endereço local correto. Sem um modelo configurado, o executor pode iniciar, mas a análise não será concluída.
5. Registre o executor local para este usuário do Windows:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\install_whatsapp_executor.ps1
   ```

6. No site da Kiara, abra **WhatsApp** no menu e clique em **Analisar WhatsApp no Chrome**.
7. No primeiro uso, entre na conta Kiara na janela de login. A extensão encontrará a guia WhatsApp Web existente; se não houver nenhuma aberta, abrirá uma guia no mesmo perfil do Chrome. Mantenha o computador e o Ollama local ligados até a análise terminar.

O executor local abre sem uma janela de terminal. A senha e os tokens da sessão Kiara não são gravados; ficam somente na memória do processo. Resultados da leitura passam pela ponte local em `127.0.0.1:17843`, limitada à origem da extensão instalada. Saídas técnicas sanitizadas são gravadas em `data/whatsapp-web/executor.log`.

Cada solicitação de análise lê até 30 conversas visíveis na guia Chrome conectada, usa o modelo Ollama local e importa nome, telefone e etapa provável para o CRM. Conversas sem telefone verificável são ignoradas. Recarregue a extensão em `chrome://extensions` e atualize a guia do WhatsApp para usar a versão 2.

## Atendimento e prospecção autorizados

Configure contatos, contexto comercial, horário e limite diário no site. O modo piloto mantém um contato habilitado; o modo operação permite vários contatos cadastrados. `enabled` habilita a operação, `auto_reply_enabled` controla respostas da IA e `followup_enabled` habilita um acompanhamento após resposta confirmada. As três opções são independentes; o motor observa as conversas cadastradas para sincronizar o histórico mesmo com a IA pausada.

`initial_outreach_enabled` começa desativado. Quando habilitado, `outreach_template` prepara uma única abordagem somente para uma conversa verificada completamente sem histórico de entrada ou saída. Apenas `{name}` é substituído. A abordagem não é repetida depois de reiniciar, alterar o texto ou obter resultado incerto. Conversas que já contêm mensagens não recebem essa abordagem inicial automática.

Ao responder manualmente pela caixa de entrada, o executor lê novamente o chat e envia uma única vez, confirmando uma nova mensagem de saída. A IA desse contato é pausada. Rascunho humano, troca de destinatário, mensagem nova, comando expirado ou falta de autorização interrompem o envio. Se o clique não tiver confirmação, o resultado permanece incerto e não gera repetição automática.

O histórico usa o horário de observação em UTC, com sequência estável para preservar a ordem das mensagens no mesmo lote. Esse horário não representa o horário original de envio ou entrega do WhatsApp. Reprocessar o mesmo ID de mensagem não altera o registro existente.

Para remover o protocolo deste usuário do Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_whatsapp_executor.ps1 -Uninstall
```

Este executor via WhatsApp Web é experimental e não oficial. A sessão pode expirar ou deixar de funcionar; use a integração oficial da Meta para operação de produção.
