from __future__ import annotations

from app.agents.catalog import load_local_specialists
from app.agents.router import AgentRouter
from app.browser import BrowserSession
from app.computer_use import (
    EphemeralVisualStateVerifier,
    ProviderVisionFallback,
    register_computer_use_tools,
)
from app.config import Settings
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.core.event_bus import EventBus
from app.integrations.communications import MicrosoftGraphCommunications
from app.integrations.credentials import (
    ChainedCredentials,
    EnvironmentCredentials,
    WindowsCredentialManager,
)
from app.integrations.email import (
    CredentialGraphEmailProvider,
    DraftStore,
    EmailService,
    GmailEmailProvider,
)
from app.knowledge import KnowledgeStore
from app.memory import MemoryEngine
from app.memory.embeddings import LocalHashEmbeddingProvider
from app.models import AutonomyMode
from app.perception import PerceptionOptions, ScreenPerception
from app.perception.windows import get_active_window
from app.planning import PlanStore, TaskPlanner
from app.providers.factory import build_llm_provider
from app.runtime import BackgroundServices
from app.security.audit import AuditLog
from app.security.hotkey import EmergencyHotkey
from app.security.kill_switch import KillSwitch
from app.security.permissions import PermissionGate
from app.tools.browser import BrowserFillTool, BrowserNavigateTool
from app.tools.communications import (
    CreateCalendarEventTool,
    PreviewCalendarEventTool,
    PreviewMessageTool,
    ReadCalendarTool,
    ReadMessagesTool,
    SendMessageTool,
)
from app.tools.email import DraftEmailTool, ReadEmailTool, SendEmailTool
from app.tools.powershell import PowerShellTool
from app.tools.registry import ToolRegistry
from app.tools.windows import OpenApplicationTool, OpenUrlTool, ScreenshotTool
from app.voice.adapters import FasterWhisperRecognizer, SapiSynthesizer, SoundDeviceMicrophone
from app.voice.service import VoiceService


def build_voice_service(settings: Settings) -> VoiceService | None:
    """Build voice adapters only when explicitly enabled; imports remain dependency-safe."""
    if not settings.get("voice.enabled", False):
        return None
    return VoiceService(
        SoundDeviceMicrophone(int(settings.get("voice.sample_rate", 16_000))),
        FasterWhisperRecognizer(
            str(settings.get("voice.stt_model", "base")),
            settings.get("voice.stt_language", "pt"),
        ),
        SapiSynthesizer(
            int(settings.get("voice.tts_rate", -1)),
            int(settings.get("voice.tts_volume", 92)),
            settings.get("voice.tts_voice_name"),
            language=str(settings.get("voice.tts_language", "pt-BR")),
            max_chunk_chars=int(settings.get("voice.tts_max_chunk_chars", 280)),
        ),
        wake_word=str(settings.get("voice.wake_word", "Kiara")),
        require_wake_word=bool(settings.get("voice.require_wake_word", True)),
        vad_enabled=bool(settings.get("voice.vad_enabled", True)),
        continuous_conversation=bool(settings.get("voice.continuous_conversation", False)),
        always_listen_for_wake_word=bool(
            settings.get("voice.always_listen_for_wake_word", True)
        ),
        conversation_requires_wake_word=bool(
            settings.get("voice.conversation_requires_wake_word", True)
        ),
    )


def build_app(settings: Settings, confirm=None) -> tuple[AgentCore, KillSwitch]:
    kill_switch = KillSwitch()
    hotkey = EmergencyHotkey(kill_switch.trigger)
    hotkey.start()
    kill_switch.hotkey = hotkey
    mode = AutonomyMode(settings.get("autonomy.mode", "execute_with_confirmation"))
    gate = PermissionGate(mode, confirm=confirm)
    audit = AuditLog(settings.root / settings.get("security.audit_log", "data/audit.jsonl"))
    registry = ToolRegistry(gate, audit, kill_switch)
    registry.register(OpenApplicationTool())
    registry.register(OpenUrlTool())
    browser = BrowserSession(
        headless=bool(settings.get("browser.headless", False)),
        timeout_ms=int(settings.get("browser.timeout_ms", 15_000)),
        allow_private_hosts=bool(settings.get("browser.allow_private_hosts", False)),
    )
    registry.register(BrowserNavigateTool(browser))
    registry.register(BrowserFillTool(browser))
    credentials = ChainedCredentials(EnvironmentCredentials(), WindowsCredentialManager())
    email_provider_name = str(settings.get("integrations.email.provider", "none")).casefold()
    email_provider = None
    if email_provider_name == "graph":
        email_provider = CredentialGraphEmailProvider(credentials)
    elif email_provider_name == "gmail":
        email_provider = GmailEmailProvider(credentials)
    email = EmailService(DraftStore(settings.root / "data" / "communications.db"), email_provider)
    registry.register(DraftEmailTool(email))
    registry.register(SendEmailTool(email))
    registry.register(ReadEmailTool(email))
    if settings.get("integrations.graph.enabled", False):
        communications = MicrosoftGraphCommunications(credentials)
        registry.register(ReadMessagesTool(communications))
        registry.register(PreviewMessageTool())
        registry.register(SendMessageTool(communications))
        registry.register(ReadCalendarTool(communications))
        registry.register(PreviewCalendarEventTool())
        registry.register(CreateCalendarEventTool(communications))
    registry.register(ScreenshotTool(settings.root / "data" / "screenshots"))
    registry.register(PowerShellTool(
        list(settings.get("security.allowlisted_commands", [])),
        int(settings.get("security.powershell_timeout_seconds", 15)),
        kill_switch,
        int(settings.get("security.max_command_output_chars", 16_384)),
    ))
    memory = None
    embeddings = None
    if settings.get("memory.embeddings_enabled", False):
        embeddings = LocalHashEmbeddingProvider(
            int(settings.get("memory.embedding_dimensions", 384))
        )
    if settings.get("memory.enabled", True):
        memory = MemoryEngine(
            settings.root / settings.get("memory.database", "data/memory.db"),
            embedding_provider=embeddings,
        )
    knowledge = None
    if settings.get("knowledge.enabled", True):
        knowledge = KnowledgeStore(
            settings.root / settings.get("knowledge.database", "data/knowledge.db"),
            chunk_size=int(settings.get("knowledge.chunk_size", 1_200)),
            chunk_overlap=int(settings.get("knowledge.chunk_overlap", 150)),
            embedding_provider=embeddings,
        )
    context = ContextManager(get_active_window, memory, knowledge)
    provider = build_llm_provider(settings)
    perception = ScreenPerception(EventBus(), PerceptionOptions.from_settings(settings))
    vision_fallback = None
    visual_state_verifier = None
    if settings.get("computer_use.enabled", False) and settings.get(
        "computer_use.visual_validation_enabled", False
    ):
        visual_state_verifier = EphemeralVisualStateVerifier(perception)
    if (
        settings.get("computer_use.enabled", False)
        and settings.get("computer_use.vision_fallback_enabled", False)
        and "vision" in provider.capabilities
    ):
        vision_fallback = ProviderVisionFallback(provider, perception)
    register_computer_use_tools(
        registry,
        settings,
        vision_fallback=vision_fallback,
        visual_state_verifier=visual_state_verifier,
    )
    resources = [hotkey, browser, email.store]
    if memory is not None:
        resources.append(memory)
    if knowledge is not None:
        resources.append(knowledge)
    resources.append(provider)
    local_specialists = load_local_specialists()
    agent_router = AgentRouter(provider, specialists=local_specialists or None)
    planner = None
    if settings.get("planning.enabled", False):
        plan_store = PlanStore(
            settings.root / settings.get("planning.database", "data/planning.db")
        )
        resources.append(plan_store)
        planner = TaskPlanner(
            provider,
            registry,
            agent_router,
            max_steps=int(settings.get("planning.max_steps", 5)),
            max_safe_retries=int(settings.get("planning.max_safe_retries", 1)),
            store=plan_store,
        )
    core = AgentCore(
        registry,
        provider,
        context,
        agent_router=agent_router,
        resources=resources,
        task_planner=planner,
        perception=perception,
    )
    core.background = BackgroundServices(settings, registry)
    return core, kill_switch


def run_desktop_app(settings: Settings, argv: list[str] | None = None) -> int:
    """Carrega PySide6 somente quando a interface desktop for solicitada."""
    from app.ui.desktop import run_desktop

    return run_desktop(
        lambda confirm: build_app(settings, confirm=confirm),
        argv,
        build_voice_service(settings),
        float(settings.get("voice.capture_seconds", 5)),
    )
