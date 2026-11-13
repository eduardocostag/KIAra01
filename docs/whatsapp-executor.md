# Conectar e analisar o WhatsApp na Kiara

Atualização de conexão em 12/11/2026: a ponte local usa a porta **3009**.
Inicie com `powershell -NoProfile -File scripts/launch_whatsapp_local_bridge.ps1`.
O launcher preserva outros processos, registra seu PID e mantém logs locais em
`.cache/whatsapp`. Na página WhatsApp, abra **Conexão** para vincular pelo QR.
O contato em `KIARA_WHATSAPP_ANALYSIS_PHONE` é necessário somente para resumir
uma conversa específica; não é obrigatório para conectar a sessão.

A alternativa via WhatsApp Web exige instalar a extensão no Chrome uma vez.
O pacote atualizado está em `/downloads/kiara-whatsapp-extension.zip` no site.
Extraia, abra `chrome://extensions`, ative o modo desenvolvedor e selecione
**Carregar sem compactação**. Recarregue as guias da Kiara e do WhatsApp Web.

A aba **WhatsApp** do site pode resumir, em modo somente leitura, a conversa de
um contato autorizado. O WhatsApp permanece conectado ao OpenWA no computador
local; a análise usa o Ollama local. Nenhuma extensão do Chrome, Chatwoot,
OmniRoute ou chave de API paga é necessária. Essa ponte não envia mensagens,
não faz prospecção e não lista contatos.

## Configuração local

1. Confirme que OpenWA está ativo em `http://127.0.0.1:3006`, a sessão `kiara`
   está conectada e o modelo Ollama `kiara-stable:latest` está instalado.
2. No arquivo ignorado pelo Git `.env.local`, configure o telefone completo do
   único contato autorizado:

   ```dotenv
   KIARA_WHATSAPP_ANALYSIS_PHONE=+5511999999999
   ```

   Use DDI e DDD; mantenha o telefone e `OPENWA_API_KEY` somente no arquivo
   local. O exemplo de configuração está em `.env.example`.
3. Configure `NEXT_PUBLIC_SUPABASE_URL` e
   `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (ou `NEXT_PUBLIC_SUPABASE_ANON_KEY`)
   no `apps/web/.env.local`, como usados pelo site. A ponte consulta o endpoint
   de identidade Supabase para validar cada token temporário do site.
4. Inicie o serviço local:

   ```powershell
   python scripts/run_whatsapp_local_bridge.py
   ```

   Ele escuta somente em `127.0.0.1:3009`. Para conferir a configuração sem
   conectar ao WhatsApp nem chamar o modelo, use `--check-only`.
5. Entre na Kiara com uma conta `owner` ou `admin`, abra **WhatsApp** e clique
   em **Analisar conversa autorizada**. Se o navegador solicitar acesso à rede
   local, permita-o para a Kiara.

## Proteções

- O contato é definido no computador e não pode ser substituído pela página.
- A ponte aceita somente as origens definidas em
  `KIARA_WHATSAPP_ALLOWED_ORIGINS`; por padrão, o site de produção e localhost.
- Cada operação exige uma sessão Supabase válida e usa autorização temporária
  emitida pela rota autenticada da Kiara.
- O resumo é processado pelo Ollama em `127.0.0.1:11434`, não é persistido pelo
  site e não inclui credenciais.
- O servidor oferece apenas status e análise; não existe endpoint de envio.
- OpenWA é uma integração não oficial e pode desconectar ou estar sujeita a
  restrições do WhatsApp.

O executor anterior via extensão Chrome continua separado e não é utilizado
pela aba atual. Respostas automáticas e prospecção permanecem desligadas.
