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
            vision_options={
                "num_gpu": int(settings.get("llm.vision_num_gpu", 0)),
                "num_ctx": int(settings.get("llm.vision_context_window", 2048)),
            },
            generation_options={
                "temperature": float(settings.get("llm.temperature", 0.25)),
                "num_ctx": int(settings.get("llm.context_window", 8192)),
                "repeat_penalty": float(settings.get("llm.repeat_penalty", 1.08)),
            },
            keep_alive=str(settings.get("llm.keep_alive", "10m")),
        )
    if provider in {
        "groq",
        "openrouter",
        "gemini",
        "nvidia",
        "antling",
        "tokenra",
        "vercel-gateway",
        "openai-compatible",
    }:
        defaults = {
            "groq": ("https://api.groq.com/openai/v1", "llama-3.1-8b-instant"),
            "openrouter": ("https://openrouter.ai/api/v1", "openrouter/free"),
            "gemini": (
                "https://generativelanguage.googleapis.com/v1beta/openai",
                "gemini-2.0-flash",
            ),
            "nvidia": (
                "https://integrate.api.nvidia.com/v1",
                "nvidia/nemotron-3-ultra-550b-a55b",
            ),
            "antling": ("https://api.ant-ling.com/v1", "Ling-3.0-flash"),
            "tokenra": ("https://tokenra.io/v1", "stealth/ox-alpha"),
            "vercel-gateway": (
                "https://ai-gateway.vercel.sh/v1",
                "inclusionai/ling-3.0-flash",
            ),
            "openai-compatible": ("http://127.0.0.1:8000/v1", ""),
        }
        base_url, default_model = defaults[provider]
        selected_model = model or default_model
        if not selected_model:
            raise ProviderConfigurationError("Configure KIARA_LLM_MODEL para o provedor remoto.")
        api_key = env.get(f"{prefix}API_KEY", "")
        key_names = {
            "groq": ("GROQ_API_KEY",),
            "openrouter": ("OPENROUTER_API_KEY",),
            "gemini": ("GEMINI_API_KEY",),
            "nvidia": ("NEMOTRON_3_ULTRA_550B_API_KEY", "NVIDIA_API_KEY"),
            "antling": ("LING_3_0_FLASH_API_KEY", "ANT_LING_API_KEY"),
            "tokenra": ("OX_ALPHA_API_KEY", "TOKENRA_API_KEY"),
            "vercel-gateway": (
                "LING_3_0_FLASH_VERCEL_API_KEY",
                "AI_GATEWAY_API_KEY",
            ),
        }
        if not api_key and provider in key_names:
            api_key = next(
                (env.get(name, "") for name in key_names[provider] if env.get(name)),
                "",
            )
        if not api_key and provider == "vercel-gateway":
            api_key = env.get("VERCEL_OIDC_TOKEN", "")
        selected_base_url = env.get(
            f"{prefix}BASE_URL",
            str(settings.get("llm.remote_base_url") or base_url),
        )
        if provider != "openai-compatible":
            expected_host = {
                "groq": "api.groq.com",
                "openrouter": "openrouter.ai",
                "gemini": "generativelanguage.googleapis.com",
                "nvidia": "integrate.api.nvidia.com",
                "antling": "api.ant-ling.com",
                "tokenra": "tokenra.io",
                "vercel-gateway": "ai-gateway.vercel.sh",
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
            max_output_tokens=int(settings.get("llm.max_output_tokens", 4096)),
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
        configured = settings.get(f"llm.routing.{profile}.candidates", [])
        candidates = list(configured) if isinstance(configured, list) else []
        if not candidates:
            candidates = [
                {
                    "provider": settings.get(f"llm.routing.{profile}.provider", "groq"),
                    "model": settings.get(f"llm.routing.{profile}.model", ""),
                }
            ]
        providers: list[LLMProvider] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            provider_name = str(candidate.get("provider", "")).casefold()
            model = str(candidate.get("model", "")).strip()
            if provider_name in {"", "local", "ollama"} or not model:
                continue
            try:
                remote = _build_provider(provider_name, settings, env, timeout, model)
            except ProviderConfigurationError:
                continue
            providers.append(
                GuardedRemoteProvider(
                    remote,
                    name=f"{provider_name}:{model}",
                    ledger_path=ledger,
                    daily_request_limit=int(candidate.get("daily_request_limit", daily_limit)),
                    failure_threshold=failure_threshold,
                    cooldown_seconds=cooldown,
                )
            )
        return FallbackProvider([*providers, local]) if providers else local

    profiles = {
        "fast": remote_profile("fast", local_router.profiles["fast"]),
        "reasoning": remote_profile("reasoning", local_router.profiles["reasoning"]),
    }
    if "vision" in local_router.profiles:
        profiles["vision"] = local_router.profiles["vision"]
    return ModelRouter(profiles, policy=local_router.policy, metrics=local_router.metrics)
