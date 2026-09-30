# Segurança operacional — Concorrência no Instagram

A aba Concorrência usa uma sessão autenticada do Instagram. Não existe forma de garantir que uma conta nunca será limitada; o Instagram controla os limites e pode alterar seus critérios. A opção de menor risco é substituir a coleta autenticada por APIs oficiais e dados autorizados sempre que o produto permitir.

## Proteções aplicadas

- Máximo de **25 perfis por análise**.
- Máximo de **5 páginas de comentários**, com intervalo de 3 segundos entre páginas.
- Intervalo mínimo padrão de **5 minutos** entre análises por workspace.
- Máximo padrão de **4 análises por hora** e **12 por dia** por workspace.
- Pausa automática de **1 hora** após resposta de rate limit.
- Pausa automática de **24 horas** após challenge/checkpoint.
- Identidade de cliente estável durante a sessão; não há rotação de user agent.
- Perfil e fingerprint separados por workspace por HMAC, sem expor o identificador do tenant no filesystem.
- O browser worker usa `invisible-playwright` com Firefox modificado e seed estável por workspace; Chromium permanece como fallback operacional temporário.
- Limites persistem em `instagram-safety.json` no diretório de dados do browser worker, inclusive após reinício.

## Motor do navegador e rollout

O motor padrão é selecionado por `KIARA_BROWSER_ENGINE=invisible`. O perfil Firefox fica em uma árvore diferente do perfil Chromium para impedir corrupção ou migração implícita de cookies incompatíveis. `KIARA_BROWSER_ENGINE_FALLBACK=true` permite voltar ao Chromium apenas quando o Firefox não consegue iniciar; a rota `/health/ready` informa o motor configurado, se o fallback está habilitado e os motores das sessões ativas.

Para rollback operacional, configure `KIARA_BROWSER_ENGINE=chromium` e reconstrua o worker. O login do Firefox não é copiado para o Chromium nem vice-versa, portanto uma troca pode exigir nova autenticação do usuário.

O motor modificado reduz diferenças observáveis de um navegador automatizado, mas **não** resolve reputação do IP, CAPTCHA, frequência excessiva, limites por conta ou regras contratuais da plataforma. Ele não deve ser usado para contornar bloqueios; challenge e rate limit continuam acionando pausa obrigatória.

Os limites podem ser reduzidos, mas não elevados além das faixas seguras embutidas, pelas variáveis:

- `KIARA_INSTAGRAM_ANALYSIS_COOLDOWN_SECONDS` (60–3600)
- `KIARA_INSTAGRAM_ANALYSIS_HOURLY_LIMIT` (1–12)
- `KIARA_INSTAGRAM_ANALYSIS_DAILY_LIMIT` (1–50)

## Regras operacionais

1. Use uma conta comercial dedicada, com 2FA e e-mail/telefone de recuperação atualizados.
2. Não execute análises simultâneas nem repita imediatamente uma consulta que falhou.
3. Ao receber challenge, checkpoint, “tente novamente mais tarde” ou logout inesperado, interrompa as consultas e confirme a conta diretamente no aplicativo oficial.
4. Não use proxy rotativo, troca de dispositivo, rotação de user agent ou qualquer mecanismo para contornar limites.
5. Não use a sessão para coletar conteúdo privado. A funcionalidade deve operar somente sobre perfis e publicações públicos.
6. Não automatize mensagens ou ações (seguir, curtir, comentar) a partir dos perfis coletados.
7. Monitore respostas 429 e eventos de verificação; aumente os intervalos ou desative a funcionalidade quando recorrentes.

## Limitação conhecida

A implementação ainda acessa endpoints internos do Instagram, que não possuem estabilidade nem autorização equivalentes às APIs públicas da Meta. Parte da coleta reproduz cookies em requisições HTTP fora do Firefox; portanto, a melhoria do motor não cria uma identidade única e coerente para todo o pipeline. As proteções reduzem rajadas e repetição, mas não eliminam risco contratual ou de restrição. Para produção de longo prazo, mantenha a aba sob feature flag até existir uma fonte oficial ou autorizada que cubra o caso de uso.

O código atual do `invisible-playwright` é usado sob licença MIT. Snapshots do projeto distribuídos antes de 2 de setembro de 2026 permanecem sob AGPL-3.0 e não devem ser incorporados à Kiara.
