# Premium design system

Este pacote separa direção de arte de conteúdo e implementação. Cada template recebe uma família narrativa e um tom próprio por `premium-design.js`.

## Famílias

- `clinical-trust`: precisão serena, evidência e espaço em branco.
- `editorial-luxury`: tipografia expressiva, assimetria e luxo contido.
- `local-service`: presença local, alto contraste e conversão direta.
- `performance-system`: métricas, grid técnico e movimento controlado.
- `portfolio-first`: galeria cinematográfica e protagonismo visual.
- `family-care`: formas acolhedoras, hierarquia amigável e baixa ansiedade.

## Integração

Copie a pasta `system` para a raiz pública comum ou preserve sua posição em `templates/system`. Em cada template, carregue antes de `</body>`:

```html
<script src="../system/premium-design.js"></script>
```

O carregador identifica o slug no caminho e inclui `premium-core.css` e `premium-families.css`. Em deploys isolados, copie os três arquivos para `system/` no projeto publicado e use `./system/premium-design.js`.

O HTML novo pode usar `data-premium-shell`, `data-premium-section`, `data-premium-grid`, `data-premium-card` e `data-kicker`. Os seletores também aprimoram as classes legadas `.shell`, `.section`, `.cards`, `.card`, `.photo` e `.portrait`.

## Regras editoriais

1. Uma família define a narrativa da página inteira, não apenas cores do hero.
2. Fotos devem ter enquadramentos diferentes por template; não reutilizar o mesmo tríptico como três imagens.
3. Movimento precisa explicar o serviço ou orientar a leitura. Efeitos decorativos devem ser discretos.
4. Use no máximo uma fonte display e uma fonte de texto por página.
5. Preserve contraste AA e o comportamento de `prefers-reduced-motion`.
6. Conteúdo e contatos de demonstração não podem ser publicados como dados reais.

## Dependência de fontes

O CSS usa Google Fonts com fallbacks locais. Para desempenho e privacidade em produção, o build deve baixar/subsetar WOFF2 e substituir o `@import` por `@font-face` local.
