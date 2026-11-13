# Estabilidade da Kiara — 13/11/2026

Correções publicadas no site e na API:

- O backend de Chat e WhatsApp exige a identidade administrativa, além das verificações existentes de papel. A ponte local do Chat confere o e-mail verificado do Supabase; a ponte local do WhatsApp também exige essa identidade. Campos editáveis em user_metadata não concedem acesso.
- O acompanhamento de vídeos repete consultas com espera crescente e pausa após quatro falhas, com retomada manual. Cancelamento/troca de vídeo interrompe consultas e ignora respostas atrasadas. Uma retomada não cria outra geração.
- Novos trabalhos de vídeo persistem proprietário e estado atomicamente. Após reiniciar, trabalhos concluídos continuam acessíveis ao proprietário; trabalhos interrompidos são apresentados como falha, sem execução automática. Os vídeos antigos sem manifesto não recebem proprietário por inferência.
- FFmpeg instalado no ambiente virtual pelo pacote imageio-ffmpeg 0.6.0; a dependência está no extra `video` do projeto. Foi gerado um MP4 real de teste de um segundo, com narração de 6,33 segundos preparada e decodificação válida; relatório em `evidence/kiara-stability/media-runtime.json`.

Validação: 128 testes Python e 15 do cliente passaram; 1 teste de symlink real foi ignorado no Windows, com guardas também testadas sem privilégio. Outros 14 testes da ponte local do WhatsApp passaram. Ruff, ESLint e build aprovados. Produção respondeu 200 nos endpoints de saúde e login, e 401 nas rotas protegidas sem sessão.

Implantações: API `dpl_7h7wrA1wTZZCofJeG4Mvo9QhaKpA`; site `dpl_FWaXGaVAeHjGJdY6gCHFUsAvEt8K`, ambas READY. Ponte WhatsApp reiniciada na porta 3009 após validar o processo específico do workspace.

Pendência de configuração: o usuário optou por manter OmniRoute e preencher `OMNIROUTE_API_KEY` e `OMNIROUTE_MODEL` no `.env.local`. Enquanto faltarem, a ponte Chat não inicia; nenhum provedor foi trocado e nenhuma chave foi exposta. Após configurar, executar `powershell -NoProfile -File scripts/launch_kiara_chat_bridge.ps1`, que valida a configuração, inicia em janela oculta e preserva qualquer processo que já ocupe a porta.
