---
name: kiara-video-studio
description: Produzir vídeos de apresentação e venda narrados pela própria Kiara (orbe animado com voz), com telas reais do sistema, cards sincronizados com a fala, saudação personalizada com o nome dos clientes e efeitos 3D.
---

# Kiara Video Studio

A Kiara produz vídeos de apresentação em que ela mesma aparece (o orbe com rosto, aura,
barras de áudio e satélites) e narra em português do Brasil. Cada vídeo sai em MP4 1920×1080.

## Como pedir

- **KIARA Chat → modo Vídeo:** descreva para quem é o vídeo, o que mostrar e o tom.
  Ex.: "Vídeo de apresentação da Kiara para Ana e Pedro, mostrando Leads e WhatsApp, tom animado."
  A Kiara escreve o roteiro, grava a fala, renderiza e mostra o player com o botão Baixar.
- **Ferramenta `create_presentation_video`** (agente): `brief`, `audience` (até 3 nomes), `quality`.
  Acompanhe com `presentation_video_status` e o `job_id` devolvido.
- **Linha de comando** (projeto pronto): `python -m app.video_studio make <pasta> [--quality 720p]`.

A produção leva alguns minutos: a fala é rápida; a renderização desenha cada quadro e roda em
paralelo (`KIARA_VIDEO_WORKERS` define quantos processos; padrão = núcleos ÷ 3).

## Estrutura do projeto

```
<pasta>/script.json     roteiro (cenas, falas, cards)
<pasta>/shots/*.png     telas 1920×1080 usadas nas cenas "shot"
<pasta>/build/          áudio, narration.wav, timeline.js, composition.html (gerados)
<pasta>/out/video.mp4   vídeo final
```

## Roteiro (`script.json`)

```json
{
  "voice": "pt-BR-FranciscaNeural",
  "rate": "+2%",
  "meta": {"audience": ["Ana", "Pedro"], "cta": "Conheça a Kiara · kiaralead.vercel.app",
           "pronunciation": {"Termo": "como se fala"}},
  "scenes": [
    {"id": "ola", "layout": "hello", "text": "Olá, Ana e Pedro! ...",
     "words": [{"text": "Ana", "cue": "Ana"}, {"text": "Pedro", "cue": "Pedro"}]},
    {"id": "leads", "layout": "shot", "kicker": "KIARA Leads", "accent": "#38bdf8",
     "shots": [{"shot": "hunter"}, {"shot": "contacts", "cue": "CRM"}],
     "text": "...", "cards": [{"text": "Busca em linguagem natural", "cue": "descreve"}]},
    {"id": "final", "layout": "outro", "title": "Vocês aprovam. A Kiara executa.", "text": "..."}
  ]
}
```

Layouts:

| layout  | o que aparece |
|---------|---------------|
| hello   | "Olá," e os nomes do público entrando em 3D (words = nomes) |
| orb     | Kiara no centro com até 3 frases girando ao redor (words) |
| shot    | tela real numa janela 3D, câmera aproximando de `focus` [x, y, zoom], até 4 cards; `cardsSide: "left"` |
| custom  | módulos girando (`tiles`) e um bloco "+ Novo módulo" (`new_tile`) surgindo; até 3 cards |
| control | anéis de proteção e até 3 frases (cards) |
| outro   | título em duas frases e botão `meta.cta` |

Telas da biblioteca (`app/resources/video_studio/shots`): landing-hero, landing-modules, hunter,
contacts, queue, whatsapp-inbox, whatsapp-automation, chat, voice, automation-run, automation-ads.

## Regras que deixam o vídeo bom

- 6 a 11 cenas, 1 a 2 frases curtas por cena; vídeo de 1 a 2 minutos.
- Cada card/word tem `cue`: uma palavra dita na cena. O card surge exatamente nesse momento.
- Cards com até 30 caracteres. Fale com o público pelo nome na abertura e no encerramento.
- Não invente números, preços ou clientes. Não mencione IA local.

## Voz e pronúncia

- Use **pt-BR-FranciscaNeural** (nativa). A voz "ThalitaMultilingual" mistura idiomas e soa
  espanhola em nomes e saudações ("Olá" vira "Hola").
- `text` é a legenda; `speech` (opcional) é o que a voz fala. Siglas e termos em inglês são
  convertidos automaticamente (CRM → "cê érre ême", Automation → "Automêichon");
  acrescente outros em `meta.pronunciation`.
- `python -m app.video_studio narrate <pasta> --check` transcreve a fala com Whisper e aponta
  palavras ouvidas diferentes do roteiro.

## Requisitos no computador

edge-tts (voz, precisa de internet), Playwright com Chromium, ffmpeg (`winget install Gyan.FFmpeg`).
O texto do roteiro é enviado ao serviço de voz da Microsoft; nada mais sai do computador.
