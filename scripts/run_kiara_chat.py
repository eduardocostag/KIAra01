"""Run the authenticated Kiara Chat loopback bridge. No account or model download on startup."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.chat.auth import SupabaseAuthorizationVerifier
from app.chat.automation import ControlledAutomation
from app.chat.bridge import ChatBridge, serve, validate_origins
from app.chat.service import LocalChatService, freellmapi_health, router_health
from app.providers.freellmapi import FreeLLMAPIProvider
from app.providers.omniroute import OmniRouteProvider
from app.providers.remote import ProviderConfigurationError
from app.video_studio.jobs import VideoJobs


def read_env(path: Path) -> dict[str, str]:
    result = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() and not key.lstrip().startswith("#"):
                result[key.strip()] = value.strip().strip("\"'")
    return result


def create_bridge() -> ChatBridge:
    values = {**read_env(ROOT / ".env.local"), **read_env(ROOT / "apps/web/.env.local"), **os.environ}
    origins = validate_origins(values.get("KIARA_CHAT_ALLOWED_ORIGINS", "https://kiaralead.vercel.app,http://localhost:3000,http://localhost:3100,http://127.0.0.1:3000,http://127.0.0.1:3100"))
    verifier = SupabaseAuthorizationVerifier(
        values.get("NEXT_PUBLIC_SUPABASE_URL", ""),
        values.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY") or values.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""),
        values.get("KIARA_CHAT_AUTH_API_URL", "https://kiara-api-rouge.vercel.app"),
    )
    voice = values.get("KIARA_CHAT_VOICE", "pt-BR-FranciscaNeural")
    whisper_model = values.get("KIARA_CHAT_WHISPER_MODEL", "base")
    selected = values.get("KIARA_CHAT_PROVIDER", "ollama").strip().lower()
    if selected == "omniroute":
        # OmniRoute requires an explicit model or combo, chosen in its dashboard.
        base_url = values.get("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1")
        api_key = values.get("OMNIROUTE_API_KEY", "")
        model = values.get("OMNIROUTE_MODEL", "")
        provider = OmniRouteProvider(api_key=api_key, model=model, base_url=base_url,
                                     timeout_seconds=110, max_output_tokens=4096)
        service = LocalChatService(model=model, provider=provider, provider_name="omniroute",
                                   health=router_health(base_url, api_key, model=model),
                                   voice=voice, whisper_model=whisper_model)
    elif selected == "freellmapi":
        # Router may forward messages to external providers; selected explicitly only.
        base_url = values.get("FREELLMAPI_BASE_URL", "http://127.0.0.1:3001/v1")
        api_key = values.get("FREELLMAPI_API_KEY", "")
        model = values.get("KIARA_CHAT_MODEL", "auto")
        provider = FreeLLMAPIProvider(api_key=api_key, model=model, base_url=base_url,
                                      timeout_seconds=110, max_output_tokens=4096)
        service = LocalChatService(model=model, provider=provider, provider_name="freellmapi",
                                   health=freellmapi_health(base_url, api_key),
                                   voice=voice, whisper_model=whisper_model)
    else:
        service = LocalChatService(model=values.get("KIARA_CHAT_MODEL", "kiara-stable:latest"),
                                   ollama_url=values.get("KIARA_CHAT_OLLAMA_URL", "http://127.0.0.1:11434"),
                                   voice=voice, whisper_model=whisper_model)
    automation = ControlledAutomation(ROOT / "data/kiara-chat-audit.jsonl")
    # Presentation videos: the chat model writes the script; voice, frames and encoding run here.
    videos = VideoJobs(ROOT / "data/videos", service._generate, workers=int(values.get("KIARA_VIDEO_WORKERS", "0") or 0))
    return ChatBridge(service, verifier, origins, automation, videos)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3008)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("Use somente 127.0.0.1 ou localhost.")
    try:
        bridge = create_bridge()
    except ProviderConfigurationError as error:
        parser.error(f"{error} Nenhum segredo foi exibido.")
    except ValueError:
        parser.error("Configure a URL/chave pública Supabase usada pelo site e as origens permitidas. Nenhum segredo foi exibido.")
    if args.check_only:
        print(json.dumps({"configuration_valid": True, "bridge": "127.0.0.1:3008", "checks": "configuration_only_no_session_model_or_media_call"}))
        return
    server = serve(bridge, args.host, args.port)
    print(f"Kiara Chat local em http://{args.host}:{args.port}; sessão Kiara owner/admin obrigatória.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
