# Integração do Landing Page System

O snapshot inclui documentos, 33 templates com sua mídia embutida, conteúdo compartilhado, design system, configurações, scripts e fontes do Space leve. Não inclui `.hf-home`, `.tools`, caches, ambientes virtuais, builds anteriores, versões históricas ou credenciais.

## Operação local

Na Kiara, use `landing_page_templates` para prévias isoladas. A cópia de trabalho usa um diretório novo em `generated-sites`; não executa o `fs.rmSync` do builder upstream e não altera o snapshot ou a pasta original.

O projeto upstream oferece os scripts `build-template.mjs`, `create-psychology-templates.mjs`, `create-nutrition-law-templates.mjs`, `apply-premium-system.mjs`, `materialize-premium-content.mjs`, `rollback-premium-system.mjs`, `optimize-template-images.py`, `generate-cinematic-scene.ps1`, `request-cinematic-clip.py`, `build-cinematic-assets.ps1`, `ffmpeg-tools.ps1`, `create-demo-source.ps1`, `template-quality.mjs` e `verify-templates.ps1`. Consulte suas fontes no snapshot antes de executar.

Comandos upstream, executados na cópia de trabalho apropriada:

```text
node scripts/build-template.mjs --mode preview --config config/site.example.json
node scripts/template-quality.mjs --mode preview --json
node scripts/template-quality.mjs --mode production --config config/cliente.json
```

Não passe um slug arbitrário ao builder upstream: ele remove `dist/<template>` recursivamente. Use um ID do catálogo e uma cópia isolada. O build não substitui automaticamente todos os textos de demonstração por informações do cliente. Para produção, personalize corpo, CTA, contato, imagens e dados profissionais, e inspecione o output completo.

Verificação real da prévia `dentista-template-1`: mobile, tablet e desktop sem overflow, sem erros de execução JavaScript ou problemas nos checks básicos de acessibilidade; o gate completo não aprovou porque a fonte solicita a imagem ausente `assets/services-fitness-v1.webp`. Isso é uma pendência do acervo original, preservada para não substituir imagens de segmentos distintos silenciosamente. Corrija ou substitua por mídia apropriada antes de publicar; não considere os 33 templates homologados apenas por terem sido importados.

## Dependências e hospedagem

Implementação existente: HTML/CSS/JavaScript estáticos, Node.js, PowerShell e Python. Next.js, TypeScript, Tailwind, Framer Motion, GSAP e Lenis são opções do playbook, não dependências já instaladas no acervo. Google Fonts precisam de fallback e consideração do orçamento de rede.

Vercel e Cloudflare R2 são destinos documentados; não há conta, bucket, DNS ou publicação ativados por esta skill. Consulte `config/vercel-headers.json`, `PUBLISHING.md` e `CINEMATIC-PIPELINE.md` antes de configurar um destino solicitado.

Os assets locais são usados pelo executor da Kiara. A existência de referências num deploy da API não garante que HTML, mídia ou ferramentas locais tenham sido empacotados naquele ambiente. Verifique o manifest de release e as capacidades reais antes de prometer geração ou hospedagem remota.
