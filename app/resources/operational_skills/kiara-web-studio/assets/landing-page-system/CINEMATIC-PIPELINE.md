# Pipeline cinematográfico

Este documento descreve como o `motion-engine.js` do exemplo evolui de camadas 2.5D para vídeo e sequências geradas por IA.

## Arquitetura escolhida

- Site, previews e domínio: Vercel.
- Mídia pesada: Cloudflare R2 com domínio próprio.
- Protótipo de geração: [Landing Cinema Generator](https://huggingface.co/spaces/eduardocostag/landing-cinema-generator) no Hugging Face ZeroGPU.
- Orquestração e pós-processamento: aplicativo local + FFmpeg.
- Desenvolvimento: arquivos locais servidos por HTTP.

O frontend nunca deve conhecer o provedor de geração. Ele recebe apenas um manifesto de mídia versionado.

## Contrato de uma cena

```js
{
  id: 'hero-v1',
  root: '#inicio',
  media: {
    full: {
      type: 'sequence',
      target: '#hero-sequence',
      template: 'https://media.exemplo.com/hero-v1/frame-{frame}.webp',
      frames: 96,
      pad: 3,
      poster: 'https://media.exemplo.com/hero-v1/poster.avif'
    },
    mobile: {
      type: 'video',
      target: '#hero-video',
      src: 'https://media.exemplo.com/hero-v1/mobile.mp4'
    },
    lite: { type: 'layers' },
    static: { type: 'layers' }
  },
  tracks: []
}
```

O motor já inclui renderizadores para:

- Variáveis CSS e camadas.
- Scrub de vídeo por `currentTime`.
- Sequência de imagens em Canvas.

## Estrutura de mídia no R2

```text
landing-media/
└── cliente/projeto/hero-v1/
    ├── manifest.json
    ├── poster.avif
    ├── desktop.webm
    ├── mobile.mp4
    └── frames/
        ├── frame-001.webp
        ├── frame-002.webp
        └── ...
```

Configuração necessária:

- CORS permitindo o domínio da landing page.
- `Cache-Control: public, max-age=31536000, immutable` para ativos versionados.
- Cache curto para `manifest.json`.
- Suporte a `Range Requests` nos vídeos.
- Nome de versão novo a cada alteração; nunca sobrescrever uma cena publicada.

## Pipeline de geração

```text
foto + briefing + preset de movimento
  -> validação
  -> recorte e reconstrução do fundo
  -> prompt e pose
  -> fila ZeroGPU
  -> vídeo fonte
  -> FFmpeg
  -> poster + MP4 + WebM + frames
  -> verificação de peso/duração
  -> upload no R2
  -> atualização do manifesto
  -> deploy na Vercel
```

## Regras de fallback

| Condição | Entrega |
|---|---|
| Desktop capaz | Sequência completa |
| Mobile | Vídeo curto ou sequência reduzida |
| `saveData` ou rede lenta | Poster + camadas leves |
| Pouca memória | Poster + camadas leves |
| `prefers-reduced-motion` | Composição estática |
| Falha de mídia | Poster local e CTA funcional |

## Próximas entregas

1. Produzir uma sequência real de 3–4 segundos para o hero.
2. Adicionar poster e elemento Canvas ao exemplo.
3. ✅ Criar o Space ZeroGPU com uma API Gradio (`generate_cinematic_clip`).
4. Criar o comando local `landing-factory generate`.
5. Configurar bucket R2 e upload versionado.
6. Conectar o repositório à Vercel para previews automáticos.
