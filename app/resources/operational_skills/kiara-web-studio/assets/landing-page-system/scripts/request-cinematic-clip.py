from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from gradio_client import Client, handle_file
from huggingface_hub import get_token


LIGHT_ENGINE_SPACE = "eduardocostag/landing-cinema-generator"
REAL_ENGINE_SPACE = "Lightricks/ltx-video-distilled"


def find_output_path(value: object) -> Path | None:
    if isinstance(value, (str, Path)):
        candidate = Path(value).resolve()
        return candidate if candidate.is_file() else None
    if isinstance(value, dict):
        for key in ("path", "video", "name"):
            if key in value:
                candidate = find_output_path(value[key])
                if candidate:
                    return candidate
        for nested in value.values():
            candidate = find_output_path(nested)
            if candidate:
                return candidate
    if isinstance(value, (list, tuple)):
        for nested in value:
            candidate = find_output_path(nested)
            if candidate:
                return candidate
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Solicita um clipe ao Landing Cinema Generator."
    )
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--preset",
        default="Entrada premium",
        choices=["Entrada premium", "Impacto 3D", "Respiração cinematográfica"],
    )
    parser.add_argument("--duration", default=3.0, type=float)
    parser.add_argument("--engine", choices=["real", "light"], default="real")
    parser.add_argument(
        "--prompt",
        default=(
            "A fit male personal trainer in a black shirt comes alive naturally. "
            "He shifts his torso, looks confidently toward the camera, then extends "
            "his right arm forward and slightly to the right as if reaching for and "
            "grabbing a glowing interface button. Realistic body motion, fixed camera, "
            "cinematic gym lighting, preserve his identity, face and clothing."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.image.expanduser().resolve()
    destination = args.output.expanduser().resolve()

    if not source.is_file():
        raise SystemExit(f"Imagem não encontrada: {source}")
    if not 2 <= args.duration <= 5:
        raise SystemExit("A duração deve ficar entre 2 e 5 segundos.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if args.engine == "real":
        client = Client(REAL_ENGINE_SPACE, token=get_token(), verbose=False)
        result = client.predict(
            prompt=args.prompt,
            negative_prompt=(
                "worst quality, inconsistent motion, blurry, jittery, distorted face, "
                "deformed hands, extra fingers, extra arms, identity change, camera movement"
            ),
            input_image_filepath=handle_file(str(source)),
            input_video_filepath=None,
            height_ui=704,
            width_ui=512,
            mode="image-to-video",
            duration_ui=args.duration,
            ui_frames_to_use=9,
            seed_ui=20260831,
            randomize_seed=False,
            ui_guidance_scale=3.0,
            improve_texture_flag=False,
            api_name="/image_to_video",
        )
    else:
        client = Client(LIGHT_ENGINE_SPACE, token=get_token(), verbose=False)
        result = client.predict(
            image=handle_file(str(source)),
            preset=args.preset,
            duration=args.duration,
            api_name="/generate_cinematic_clip",
        )

    remote_file = find_output_path(result)
    if remote_file is None:
        raise RuntimeError(f"O Space não retornou um vídeo válido: {result!r}")

    shutil.copy2(remote_file, destination)
    print(destination)


if __name__ == "__main__":
    main()
