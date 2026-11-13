# Engines e pipeline cinematográfico

Fontes registradas:

- Space leve: https://huggingface.co/spaces/eduardocostag/landing-cinema-generator — endpoint `/generate_cinematic_clip`.
- Space real padrão: https://huggingface.co/spaces/Lightricks/ltx-video-distilled — endpoint `/image_to_video`.
- Código upstream: https://github.com/Lightricks/LTX-Video.
- Modelo upstream: https://huggingface.co/Lightricks/LTX-Video; o inventário original referencia `ltxv-13b-0.9.8-distilled.safetensors`.

Essas referências não significam clone local, licença verificada, endpoint disponível, créditos ou GPU concedidos. Os clientes existentes chamam serviços externos; confirme a configuração e a utilização desejada antes de transmitir imagens ou solicitar processamento.

A cópia local do código do Space real está em `assets/landing-page-system/upstream/ltx-video-distilled/app.py`, importada por whitelist. Pesos do modelo e caches não foram copiados.

```text
powershell -File scripts/generate-cinematic-scene.ps1 -Image <imagem> -SceneId hero-v1 -Engine real -Duration 3 -FrameRate 12 -MaxFrames 96
```

Presets de origem: Entrada premium, Impacto 3D, Respiração cinematográfica. O prompt de exemplo do script descreve um personal trainer; substitua-o pelo briefing real de cada projeto.

Versões declaradas no inventário: Gradio 5.44.1; Gradio Client 1.12.1; WebSockets 15.0.1; ImageIO 2.37.0; imageio-ffmpeg 0.6.0; NumPy 2.2.6; Pillow 11.3.0. Também são necessários `huggingface_hub`, `spaces` e as dependências transitivas dos clientes. Não imponha essas versões ao ambiente principal da Kiara: use um ambiente isolado para o pipeline e confira compatibilidade.

O script PowerShell define `HF_HOME` e `PYTHONPATH` temporariamente, restaurando-os depois. Não importe tokens/cache do projeto original. O instalador upstream usa `--no-deps` para parte do cliente, portanto a simples cópia dos scripts não comprova ambiente funcional.

O pós-processamento exige FFmpeg e FFprobe; o pacote imageio-ffmpeg não garante FFprobe. Gere poster e fallback mobile/reduced-motion; avalie scrubbing por vídeo ou Canvas conforme o custo. Arquivos versionados no R2 usam cache imutável, manifest com cache curto, CORS para o domínio correto e suporte a Range Requests. Não sobrescreva uma cena já publicada.
