from __future__ import annotations

import os
from collections.abc import Mapping

from app.config import Settings
from app.providers.llm import LLMProvider, LocalFallbackProvider
from app.providers.remote import OllamaProvider, OpenAIProvider, ProviderConfigurationError


def build_llm_provider(
    settings: Settings,
    environ: Mapping[str, str] | None = None,
) -> LLMProvider:
    env = os.environ if environ is None else environ
    provider = env.get("KIARA_LLM_PROVIDER", str(settings.get("llm.provider", "local"))).casefold()
    timeout = float(settings.get("llm.timeout_seconds", 30))
    model = str(settings.get("llm.model") or "")
    if provider == "local":
        return LocalFallbackProvider()
    if provider == "openai":
        if not model:
            raise ProviderConfigurationError("Configure llm.model para usar OpenAI.")
        return OpenAIProvider(model, env.get("OPENAI_API_KEY", ""), timeout)
    if provider == "ollama":
        if not model:
            raise ProviderConfigurationError("Configure llm.model para usar Ollama.")
        return OllamaProvider(
            model=model,
            base_url=env.get(
                "OLLAMA_HOST", str(settings.get("llm.ollama_base_url", "http://127.0.0.1:11434"))
            ),
            timeout_seconds=timeout,
            vision_enabled=bool(settings.get("llm.vision_enabled", False)),
            vision_model=settings.get("llm.vision_model"),
            vision_options={"num_gpu": int(settings.get("llm.vision_num_gpu", 0))},
            generation_options={
                "temperature": float(settings.get("llm.temperature", 0.25)),
                "num_ctx": int(settings.get("llm.context_window", 8192)),
                "repeat_penalty": float(settings.get("llm.repeat_penalty", 1.08)),
            },
            keep_alive=str(settings.get("llm.keep_alive", "10m")),
        )
    raise ProviderConfigurationError(f"Provider de IA desconhecido: {provider}")
