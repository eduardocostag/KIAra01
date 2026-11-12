# Módulo WhatsApp — 12/11/2026

## Estrutura publicada

- `/app/whatsapp`: Central com conexão local, contato autorizado, modelo, análise de conversa e configuração/diagnóstico. A análise é somente leitura e usa OpenWA e Ollama no computador do usuário.
- `/app/whatsapp/automacao`: executor via extensão, contatos do CRM/manuais, consentimento, contexto da empresa, horários, limites, passagem para humano e histórico.
- Sidebar específica no desktop e menu mobile; seleção por página/seção, retorno ao seletor e configuração aberta ao navegar para sua âncora.
- Entrada WhatsApp no seletor de módulos; rotas antigas `/app/followups`, `/app/whatsapp/config`, `/app/whatsapp/status` e `/app/platform/whatsapp` encaminham para a nova Central/seção.
- Página de teste `/ui-verification` disponível somente em desenvolvimento, retornando 404 no build de produção.

## Correção funcional

Salvar a configuração agora reconcilia toda a lista autorizada no banco: contatos removidos não continuam marcados com automação ativa. A atualização é limitada à organização e ao canal WhatsApp. A ponte tem prazo total para autenticação/consulta e valida as respostas de status/análise antes de exibi-las.

## Evidências

- Build Next.js/TypeScript aprovado; ESLint dos componentes alterados aprovado.
- 98 testes Python aprovados, registrados em `evidence/whatsapp-module-2026-11-12/python-tests.xml`.
- 16 testes Node de navegação, contratos da plataforma e sessão aprovados; 12 testes Node de comandos/sessão da extensão aprovados. Os comandos usam DOM simulado, sem envio real.
- Gateway no navegador: desconectado, conectado, análise, resposta inválida, permissão negada, hash da sidebar, menu mobile, configuração e largura mobile; sem erros JavaScript. APIs interceptadas.
- Automação no navegador: cadastro, autorização/contexto obrigatórios, ativação, alteração de contatos, passagem humana, atualização de histórico preservando edição, pausa ignorando alterações não salvas e largura mobile. APIs interceptadas.
- Screenshots e relatórios em `evidence/whatsapp-module-2026-11-12/`.
- Revisão visual independente da Central, sidebar e automação aprovada em desktop/mobile, limitada às imagens examinadas.

## Publicação verificada

- Site: `https://kiaralead.vercel.app/app/whatsapp`; deploy `dpl_4vKyC2ekih9EX6WQAftgoBhngqtt`, estado READY em produção.
- API: `https://kiara-api-rouge.vercel.app`; deploy `dpl_6gc56YZ183NmzLoMSJUzpTxxL54D`, estado READY em produção.
- Site público HTTP 200, API `/health/live` HTTP 200.
- Central e automação redirecionam usuários sem sessão para `/sign-in` (HTTP 307).
- `/ui-verification` retorna HTTP 404 em produção.
- Não foi executado um fluxo com usuário autenticado e conta WhatsApp conectada em produção.

## Repositórios e serviços

OpenWA 0.30.0, commit `44856156e121632cac8fb6f14d14633a6c2e3794`: checkout, servidor, painel e Chrome verificados. HTTP de saúde 200; sessões sem chave retornam 401. Contratos upstream: 549 pares de tipos e 355 rotas SDK conferidos. Repositórios oficiais OpenWA e OpenWA-plugins acessíveis.

Ollama respondeu HTTP 200 com o modelo padrão `kiara-stable:latest` instalado. OmniRoute respondeu 401 sem chave; inferência não foi executada. A Central usa OpenWA/Ollama diretamente e não depende de OmniRoute.

## Pendência operacional

`KIARA_WHATSAPP_ANALYSIS_PHONE` não está definido na configuração local verificada. A ponte exige esse contato autorizado para iniciar. A publicação disponibiliza as páginas e a API; não configura o contato, vincula uma conta WhatsApp ou inicia serviços no computador de quem acessa o site. Chatwoot não foi validado como conectado.

Não foram consultadas conversas reais, vinculadas contas, ativadas automações de clientes ou enviadas mensagens nesta verificação. Testes de interface usam respostas simuladas e não comprovam operação real com uma conta conectada. A revisão visual não constitui certificação WCAG completa.
