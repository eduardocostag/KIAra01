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
- Limites persistem em `instagram-safety.json` no diretório de dados do browser worker, inclusive após reinício.

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

A implementação ainda acessa endpoints internos do Instagram, que não possuem estabilidade nem autorização equivalentes às APIs públicas da Meta. As proteções reduzem rajadas e repetição, mas não eliminam risco contratual ou de restrição. Para produção de longo prazo, mantenha a aba sob feature flag até existir uma fonte oficial ou autorizada que cubra o caso de uso.
