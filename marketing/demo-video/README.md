# Vídeo de demonstração da Kiara

Vídeo de cerca de 2min30 para enviar a clientes: telas reais do sistema, cartões em 3D,
o orbe da Kiara apresentando e narração em português (voz neural pt-BR).

## Como regerar

Pré-requisitos: ffmpeg no PATH e o ambiente Python do projeto (`.venv`, com Playwright e edge-tts).

```powershell
cd marketing/demo-video
# 1. Narração e linha do tempo (texto em script.json)
..\..\.venv\Scripts\python.exe narrate.py
# 2. Telas reais, com o site em modo de desenvolvimento rodando (apps/web: npx next dev -p 3100)
..\..\.venv\Scripts\python.exe capture.py
# 3. Vídeo final (cerca de 10 minutos de renderização)
..\..\.venv\Scripts\python.exe render.py
```

Resultado: `out/kiara-demo.mp4` (1920×1080, H.264 + AAC).

- **Mudar a fala:** edite `script.json` e apague `assets/audio/<cena>.mp3` das cenas alteradas antes do passo 1.
- **Mudar uma tela:** ajuste `capture.py` (as APIs são simuladas com dados de demonstração; nada real é lido ou enviado).
- **Mudar o visual:** `composition.html` desenha tudo em função do tempo; abra no navegador e chame `renderAt(segundos)` no console para conferir um quadro.

A narração usa o serviço de voz do Microsoft Edge (o texto do roteiro é enviado a ele).
Os dados exibidos (clínicas, telefones, mensagens) são fictícios.
