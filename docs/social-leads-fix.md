# Facebook e Instagram: descoberta e leitura de perfis

Correção de 13/11/2026 UTC. A busca agora descarta URLs de publicações, login e grupos antes de consumir a cota de candidatos. Quando os índices não encontram perfis, consulta links explícitos nos sites encontrados pelo Exa. Nunca cria nomes de usuário a partir do nome da empresa.

A leitura direta rejeita redirecionamentos para outro perfil, login e descrições genéricas. Se não retornar descrição válida, tenta o Firecrawl já configurado na API de produção, com cache desativado, proxy básico e até oito candidatos por rede. A resposta precisa identificar o mesmo perfil, retornar HTTP 200 e conter descrição pública. Os critérios de nicho, localização e contato continuam obrigatórios; o link no site isoladamente não confirma um lead.

Validação: 167 testes passaram e Ruff passou. A amostra real local descobriu oito candidatos, mas não confirmou leads porque as redes não forneceram descrição verificável. Firecrawl não está configurado no ambiente local dessa amostra; sua chave está cadastrada como Secret em produção. A execução real do fallback com essa chave não foi validada no teste local. Testes isolados cobrem resposta válida nas duas redes, redirecionamento, bloqueio e página de login.

Evidências agregadas sem contatos: `evidence/social-leads-fix/live.json` e `evidence/social-leads-fix/tests.xml`.
