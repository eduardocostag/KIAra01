# Vídeo de demonstração da Kiara (Dani e Bruno)

Vídeo de cerca de 2 minutos para enviar a clientes: saudação com o nome deles, telas reais do
sistema, cards em 3D sincronizados com a fala e o orbe da Kiara narrando em português do Brasil.

É um projeto do **Kiara Video Studio** (`app/video_studio`), o mesmo motor que a Kiara usa no
KIARA Chat (modo Vídeo). Guia completo: `app/resources/operational_skills/kiara-video-studio/SKILL.md`.

## Como regerar

Pré-requisitos: o ambiente Python do projeto (`.venv`, com Playwright e edge-tts) e ffmpeg
(`winget install Gyan.FFmpeg`; o motor encontra a instalação do winget sozinho).

```powershell
# 1. Telas reais, com o site em modo de desenvolvimento rodando (apps/web: npx next dev -p 3100)
.venv\Scripts\python.exe marketing\demo-video\capture.py
# 2. Fala + vídeo (renderização em paralelo)
.venv\Scripts\python.exe -m app.video_studio make marketing\demo-video --output marketing\demo-video\out\kiara-demo.mp4
```

- **Mudar a fala ou os cards:** edite `script.json`. Só as cenas alteradas são regravadas.
- **Conferir a pronúncia:** `python -m app.video_studio narrate marketing\demo-video --check`.
- **Conferir quadros sem renderizar tudo:** `python -m app.video_studio preview marketing\demo-video 5 40 90`
  (as imagens ficam em `build/preview`).
- **Voz:** `pt-BR-FranciscaNeural`, nativa do português do Brasil. A ThalitaMultilingual soava espanhola
  em nomes e na saudação.

A narração usa o serviço de voz do Microsoft Edge (o texto do roteiro é enviado a ele).
Os dados exibidos nas telas (clínicas, telefones, mensagens) são fictícios.
