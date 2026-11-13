from __future__ import annotations

import math
import tempfile
from pathlib import Path

import gradio as gr
import imageio.v2 as imageio
import numpy as np
import spaces
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


WIDTH, HEIGHT = 720, 1280
FPS = 24


def cover(image: Image.Image, width: int, height: int) -> Image.Image:
    ratio = max(width / image.width, height / image.height)
    resized = image.resize(
        (math.ceil(image.width * ratio), math.ceil(image.height * ratio)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def ease_out_cubic(value: float) -> float:
    return 1 - (1 - value) ** 3


def render_frame(source: Image.Image, progress: float, preset: str) -> Image.Image:
    entrance = ease_out_cubic(min(progress / 0.28, 1.0))
    breath = math.sin(progress * math.tau * 1.25)
    drift = math.sin(progress * math.pi)

    if preset == "Entrada premium":
        scale = 1.09 - 0.055 * entrance + breath * 0.003
        offset_x = int((1 - entrance) * -150 + drift * 12)
        offset_y = int((1 - entrance) * 24 - drift * 8)
    elif preset == "Impacto 3D":
        scale = 1.13 - 0.07 * entrance + breath * 0.006
        offset_x = int((1 - entrance) * 180 - drift * 18)
        offset_y = int(breath * 7)
    else:
        scale = 1.045 + progress * 0.035 + breath * 0.002
        offset_x = int(drift * 8)
        offset_y = int(-progress * 24)

    work = source.resize(
        (round(WIDTH * scale), round(HEIGHT * scale)), Image.Resampling.LANCZOS
    )
    left = (work.width - WIDTH) // 2 - offset_x
    top = (work.height - HEIGHT) // 2 - offset_y
    frame = work.crop((left, top, left + WIDTH, top + HEIGHT)).convert("RGBA")

    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    sweep_x = int(-240 + progress * (WIDTH + 480))
    for step in range(160, 0, -8):
        alpha = int(24 * (1 - step / 168))
        draw.polygon(
            [(sweep_x - step, 0), (sweep_x + 80 - step, 0),
             (sweep_x + 320 - step, HEIGHT), (sweep_x + 180 - step, HEIGHT)],
            fill=(70, 225, 255, alpha),
        )

    rng = np.random.default_rng(20260831)
    for x, y, radius, phase in rng.uniform(
        [0, 0, 1, 0], [WIDTH, HEIGHT, 4, math.tau], size=(34, 4)
    ):
        particle_y = (y - progress * (90 + radius * 18)) % HEIGHT
        particle_x = x + math.sin(progress * math.tau + phase) * 12
        draw.ellipse(
            (particle_x - radius, particle_y - radius,
             particle_x + radius, particle_y + radius),
            fill=(120, 235, 255, int(35 + radius * 18)),
        )

    overlay = overlay.filter(ImageFilter.GaussianBlur(2.2))
    frame = Image.alpha_composite(frame, overlay).convert("RGB")
    frame = ImageEnhance.Contrast(frame).enhance(1.08)
    frame = ImageEnhance.Color(frame).enhance(1.04)
    return frame


@spaces.GPU(duration=60)
def generate(image: Image.Image, preset: str, duration: float, progress=gr.Progress()):
    if image is None:
        raise gr.Error("Envie uma foto do profissional.")

    source = cover(image.convert("RGB"), WIDTH, HEIGHT)
    frame_count = max(FPS, round(duration * FPS))
    output = Path(tempfile.mkdtemp()) / "landing-cinema.mp4"

    with imageio.get_writer(
        output,
        fps=FPS,
        codec="libx264",
        quality=7,
        pixelformat="yuv420p",
        macro_block_size=None,
    ) as writer:
        for index in progress.tqdm(range(frame_count), desc="Criando movimento"):
            value = index / max(frame_count - 1, 1)
            writer.append_data(np.asarray(render_frame(source, value, preset)))

    return str(output)


with gr.Blocks(theme=gr.themes.Soft(primary_hue="cyan")) as demo:
    gr.Markdown(
        "# Landing Cinema Generator\n"
        "Envie uma foto e gere um clipe vertical cinematográfico, gratuito e pronto para a landing page."
    )
    with gr.Row():
        with gr.Column():
            photo = gr.Image(type="pil", label="Foto do profissional")
            preset = gr.Dropdown(
                ["Entrada premium", "Impacto 3D", "Respiração cinematográfica"],
                value="Entrada premium",
                label="Movimento",
            )
            duration = gr.Slider(2, 5, value=3, step=0.5, label="Duração (segundos)")
            button = gr.Button("Gerar clipe", variant="primary")
        video = gr.Video(label="Resultado", autoplay=True)

    button.click(
        generate,
        inputs=[photo, preset, duration],
        outputs=video,
        api_name="generate_cinematic_clip",
    )


if __name__ == "__main__":
    demo.queue(max_size=20).launch()
