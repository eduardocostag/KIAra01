# Kiara Chat — auditoria de capacidades

Verificação de código em 12/11/2026. O módulo de chave `atendimento` passa a se chamar **Kiara Chat**; a chave e a rota da plataforma permanecem compatíveis.

## Integrações que antes simulavam sucesso

`services/api/kiara_api/platform/executors/voice_studio.py`, `wan2_1.py`, `money_printer_turbo.py` e `open_jarvis.py` não possuem implementação de transporte ou execução real. Retornavam `success=True` e, nos casos de mídia, caminhos fictícios `/tmp/*.mp3` ou `/tmp/*.mp4` sem criar arquivos.

Agora retornam `success=False`, `output_path=None` e uma mensagem que exige configurar a integração. Não imprimem o prompt privado no console. Metadados enviados pelo cliente não habilitam esses executores. O nome de uma ferramenta no catálogo não comprova sua disponibilidade.

`platform/brain/orchestrator.py` classifica intenções por palavras-chave; esse roteamento não é prova de execução ou inteligência geral.

## Componentes reais reutilizáveis

| Recurso | Implementação existente | Dependências e limite |
| --- | --- | --- |
| Conversa e análise | `app/providers` | Ollama local ou provedor remoto configurado; chave e modelo quando exigidos. |
| Voz e transcrição | `app/voice/adapters.py`, `service.py` | FasterWhisper, SAPI, Edge TTS ou Kokoro no runtime adequado; modelos/dependências reais. Voz do navegador é um recurso diferente de uma voz própria treinada. |
| Criação de sites estáticos | `app/web_studio/generator.py` | Gera HTML/CSS/JavaScript isolados a partir de referência visual com modelo de visão e texto. Não implanta automaticamente backend, domínio ou banco. |
| Navegação e automação da máquina | `app/computer_use`, `app/tools`, `app/core/agent_core.py` | Executor local, configuração explícita, validação de ferramentas, `PermissionGate`, auditoria e kill switch. Hospedar o site na Vercel não fornece acesso à máquina do usuário. |
| Atendimento Chatwoot | `app/integrations/chatwoot.py`, `services/api/kiara_api/chatwoot.py` | Adapter existente; serviço, conta, canal e credenciais ainda precisam estar disponíveis. |
| FreeLLMAPI | `external/freellmapi`, `app/providers/freellmapi.py` | Checkout e adapter existentes; inferência depende de provedores e chave unificada configurados. |

Esta auditoria é estática. Não foram gerados vídeos/imagens, enviados áudios, vinculadas contas ou executadas ações externas por esta correção. Disponibilidade, inferência e resultados de cada integração devem ser verificados separadamente no ambiente em que o módulo executa.
