from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlsplit

from app.config import Settings
from app.providers.guarded import GuardedRemoteProvider
from app.providers.llm import FallbackProvider, LLMProvider, LocalFallbackProvider
from app.providers.remote import (
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    ProviderConfigurationError,
)
from app.providers.router import LocalProfilePolicy, ModelRouter


def build_llm_provider(
    settings: Settings,
    environ: Mapping[str, str] | None = None,
) -> LLMProvider:
    env = os.environ if environ is None else environ
    provider = env.get("KIARA_LLM_PROVIDER", str(settings.get("llm.provider", "local"))).casefold()
    timeout = float(settings.get("llm.timeout_seconds", 30))
    model = env.get("KIARA_LLM_MODEL", str(settings.get("llm.model") or ""))
    primary = _build_provider(provider, settings, env, timeout, model)
    routing_mode = str(settings.get("llm.routing.mode", "local")).casefold()
    if provider == "ollama" and bool(settings.get("llm.routing.enabled", False)):
        fast_model = env.get(
            "KIARA_LLM_FAST_MODEL", str(settings.get("llm.routing.fast_model") or model)
        )
        reasoning_model = env.get(
            "KIARA_LLM_REASONING_MODEL",
            str(settings.get("llm.routing.reasoning_model") or model),
        )
        profiles: dict[str, LLMProvider] = {
            "fast": _build_provider("ollama", settings, env, timeout, fast_model),
            "reasoning": _build_provider("ollama", settings, env, timeout, reasoning_model),
        }
        if bool(settings.get("llm.vision_enabled", False)):
            profiles["vision"] = primary
        primary = ModelRouter(
            profiles,
            policy=LocalProfilePolicy(
                reasoning_chars=int(settings.get("llm.routing.reasoning_chars", 1_200))
            ),
        )
        if routing_mode == "hybrid":
            primary = _build_hybrid_router(settings, env, timeout, primary)
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
        selected_base_url = env.get(
            f"{prefix}BASE_URL",
            str(settings.get("llm.remote_base_url") or base_url),
        )
        if provider in {"groq", "gemini"}:
            expected_host = {
                "groq": "api.groq.com",
                "gemini": "generativelanguage.googleapis.com",
            }[provider]
            parsed = urlsplit(selected_base_url)
            if parsed.scheme != "https" or parsed.hostname != expected_host:
                raise ProviderConfigurationError(
                    f"Endpoint não autorizado para {provider}: use HTTPS no host oficial."
                )
        return OpenAICompatibleProvider(
            selected_model,
            api_key,
            selected_base_url,
            timeout,
            vision_enabled=provider == "gemini",
        )
    raise ProviderConfigurationError(f"Provider de IA desconhecido: {provider}")


def _build_hybrid_router(
    settings: Settings,
    env: Mapping[str, str],
    timeout: float,
    local_router: LLMProvider,
) -> LLMProvider:
    if not isinstance(local_router, ModelRouter):
        return local_router
    ledger = settings.root / str(
        settings.get("llm.routing.usage_ledger", "data/cloud-usage.json")
    )
    daily_limit = int(settings.get("llm.routing.daily_cloud_request_limit", 500))
    failure_threshold = int(settings.get("llm.routing.failure_threshold", 3))
    cooldown = float(settings.get("llm.routing.cooldown_seconds", 60))

    def remote_profile(profile: str, local: LLMProvider) -> LLMProvider:
        provider_name = str(settings.get(f"llm.routing.{profile}.provider", "groq")).casefold()
        model = str(settings.get(f"llm.routing.{profile}.model", "")).strip()
        if provider_name in {"", "local", "ollama"} or not model:
            return local
        try:
            remote = _build_provider(provider_name, settings, env, timeout, model)
        except ProviderConfigurationError:
            return local
        guarded = GuardedRemoteProvider(
            remote,
            name=f"{provider_name}:{model}",
            ledger_path=ledger,
            daily_request_limit=daily_limit,
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown,
        )
        return FallbackProvider([guarded, local])

    profiles = {
        "fast": remote_profile("fast", local_router.profiles["fast"]),
        "reasoning": remote_profile("reasoning", local_router.profiles["reasoning"]),
    }
    if "vision" in local_router.profiles:
        profiles["vision"] = local_router.profiles["vision"]
    return ModelRouter(profiles, policy=local_router.policy, metrics=local_router.metrics)
