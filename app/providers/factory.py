from __future__ import annotations

import os
from collections.abc import Mapping

from app.config import Settings
from app.providers.llm import FallbackProvider, LLMProvider, LocalFallbackProvider
from app.providers.remote import (
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    ProviderConfigurationError,
)


def build_llm_provider(
    settings: Settings,
    environ: Mapping[str, str] | None = None,
) -> LLMProvider:
    env = os.environ if environ is None else environ
    provider = env.get("KIARA_LLM_PROVIDER", str(settings.get("llm.provider", "local"))).casefold()
    timeout = float(settings.get("llm.timeout_seconds", 30))
    model = env.get("KIARA_LLM_MODEL", str(settings.get("llm.model") or ""))
    primary = _build_provider(provider, settings, env, timeout, model)
    fallback_name = env.get("KIARA_LLM_FALLBACK_PROVIDER", "").casefold()
    if not fallback_name:
        return primary
    fallback = _build_provider(
        fallback_name,
        settings,
        env,
        timeout,
        env.get("KIARA_LLM_FALLBACK_MODEL", model),
        prefix="KIARA_LLM_FALLBACK_",
    )
    return FallbackProvider([primary, fallback])


def _build_provider(
    provider: str,
    settings: Settings,
    env: Mapping[str, str],
    timeout: float,
    model: str,
    *,
    prefix: str = "KIARA_LLM_",
) -> LLMProvider:
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
    if provider in {"groq", "openrouter", "gemini", "openai-compatible"}:
        defaults = {
            "groq": ("https://api.groq.com/openai/v1", "llama-3.1-8b-instant"),
            "openrouter": ("https://openrouter.ai/api/v1", "openrouter/free"),
            "gemini": (
                "https://generativelanguage.googleapis.com/v1beta/openai",
                "gemini-2.0-flash",
            ),
            "openai-compatible": ("http://127.0.0.1:8000/v1", ""),
        }
        base_url, default_model = defaults[provider]
        selected_model = model or default_model
        if not selected_model:
            raise ProviderConfigurationError("Configure KIARA_LLM_MODEL para o provedor remoto.")
        api_key = env.get(f"{prefix}API_KEY", "")
        if not api_key and provider == "groq":
            api_key = env.get("GROQ_API_KEY", "")
        if not api_key and provider == "openrouter":
            api_key = env.get("OPENROUTER_API_KEY", "")
        if not api_key and provider == "gemini":
            api_key = env.get("GEMINI_API_KEY", "")
        return OpenAICompatibleProvider(
            selected_model,
            api_key,
            env.get(
                f"{prefix}BASE_URL",
                str(settings.get("llm.remote_base_url") or base_url),
            ),
            timeout,
        )
    raise ProviderConfigurationError(f"Provider de IA desconhecido: {provider}")
