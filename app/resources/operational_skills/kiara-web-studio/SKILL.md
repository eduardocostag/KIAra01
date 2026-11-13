---
name: kiara-web-studio
description: "Criar sites e landing pages a partir do acervo Landing Page System da Kiara: 33 templates profissionais, brief, design premium, critérios de qualidade, mídia cinematográfica e preparação de preview/publicação."
---

# Geração de sites da Kiara

Use esta skill para gerar ou adaptar sites profissionais, escolher templates e preparar mídia de landing pages. O acervo é uma cópia portátil do projeto local `landing-page-system`; não depende da existência da pasta original. Leia `references/catalog.json` para origens e inventário. O manifesto integral de hashes está em `references/source-manifest.json`; verifique-o com `python scripts/import_landing_page_system.py --verify`, sem carregar seus 96 KB no contexto.

## Recursos que podem ser usados agora

- `landing_page_templates` com `action=list` lista o acervo; `action=preview, template=<id>` cria uma cópia isolada para personalizar. A prévia conserva conteúdo demonstrativo, não é publicação nem prova de qualidade aprovada.
- `generate_business_site` / `generate_business_site_from_screen`: geração por modelo e referência visual; `validate_business_site`: validação de navegador. As permissões dessas ferramentas continuam em vigor.
- `operational_skill` com `action=read, name=kiara-web-studio, resource=<caminho>` lê as referências Markdown/JSON citadas abaixo.

## Antes de gerar

Leia `assets/landing-page-system/README.md`, `assets/landing-page-system/PLAYBOOK.md` e `assets/landing-page-system/prompts/master-prompt.md`. O brief de origem está em `assets/landing-page-system/templates/brief.yaml`; a configuração de exemplo em `assets/landing-page-system/config/site.example.json`.

Defina público, oferta, CTA, conteúdo real e direção visual específica. Escolha uma família do catálogo de templates; não imponha fundo escuro/glow a todo cliente. Conteúdo faltante fica explicitamente demonstrativo. Nunca invente telefone, endereço, registro, depoimento, preço ou resultado.

## Qualidade e publicação

Leia `assets/landing-page-system/QUALITY-GATES.md`, `assets/landing-page-system/PUBLISHING.md` e `references/integration.md` antes de preparar produção.

- Imagens até 750.000 bytes; vídeo até 6.000.000; página até 9.000.000.
- Preview: `noindex, nofollow, noarchive`. Produção: dados reais, canonical HTTPS e registro profissional quando aplicável, conforme `config/publishing-policy.json` e `templates/content/publication-requirements.json` do acervo.
- Confira mobile, teclado, contraste, reduced-motion, links/CTA, console, SEO e conteúdo sem JavaScript. Registre os checks efetivamente executados.
- O build upstream aplica metadados, mas não personaliza sozinho todo o conteúdo visível. O gate upstream não substitui a inspeção do resultado final.
- O HTML avulso do Chat mantém seu isolamento de rede. Sites com vídeos, fontes e vários arquivos usam o projeto completo; não remova o isolamento da prévia para carregar serviços externos.

## Mídia cinematográfica

Leia `references/cinematic.md` e `assets/landing-page-system/CINEMATIC-PIPELINE.md` quando houver vídeo. Engine padrão `real`: Space `Lightricks/ltx-video-distilled`; alternativa explícita `light`: `eduardocostag/landing-cinema-generator`. Fonte/modelo: `Lightricks/LTX-Video`, com referência original ao distilled 13B 0.9.8.

Clipes de 2–5 segundos; pós-processamento padrão 12 FPS/96 frames. Repositórios/modelos e Spaces estão referenciados, sem download automático de pesos, autenticação Hugging Face ou ativação de GPU. Não apresente disponibilidade/configuração como validada sem teste real. FFmpeg e FFprobe são dependências distintas.

## Skills de apoio importadas

Consulte `references/supporting-skills.md` para Sites, Sites Remix, Imagegen e as skills Vercel de deployment, CLI, env vars, domains, verification e React. São cópias de referência; ferramentas de plugins e credenciais não são concedidas pela importação. Escolha apenas a skill necessária ao fluxo atual.
