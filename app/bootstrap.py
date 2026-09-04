from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from app.agents.catalog import load_local_specialists
from app.agents.contracts import Specialist
from app.agents.router import AgentRouter
from app.agents.specialists import (
    GeneralistSpecialist,
    ResearchSpecialist,
    SalesDevelopmentSpecialist,
)
from app.browser import BrowserSession
from app.computer_use import (
    EphemeralVisualStateVerifier,
    ProviderVisionFallback,
    register_computer_use_tools,
)
from app.config import Settings
from app.consumers import ConsumerStore
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.core.event_bus import EventBus
from app.feedback import CorrectionInbox
from app.helpdesk import SystemDiagnosticsTool
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
from app.integrations.mcp import McpHub, McpServerConfig
from app.integrations.obsidian import ObsidianLearningStore, ObsidianVaultIndex
from app.knowledge import KnowledgeStore
from app.leads import LeadStore, ProspectingPolicy, ProspectingPolicyEngine
from app.memory import MemoryEngine, MemoryKind
from app.memory.embeddings import LocalHashEmbeddingProvider, OllamaEmbeddingProvider
from app.models import AutonomyMode
from app.perception import PerceptionOptions, ScreenPerception
from app.perception.windows import get_active_window
from app.personal import PersonalOrganizerStore
from app.planning import PlanStore, TaskPlanner
from app.providers.factory import build_llm_provider
from app.runtime import BackgroundServices
from app.security.audit import AuditLog
from app.security.hotkey import EmergencyHotkey
from app.security.kill_switch import KillSwitch
from app.security.permissions import PermissionGate
from app.tools.browser import (
    BrowserClickTool,
    BrowserFillTool,
    BrowserNavigateTool,
    BrowserReadTool,
    GoogleMapsBusinessSearchTool,
    OrganicConsumerSearchTool,
)
from app.tools.communications import (
    CreateCalendarEventTool,
    PreviewCalendarEventTool,
    PreviewMessageTool,
    ReadCalendarTool,
    ReadMessagesTool,
    SendMessageTool,
)
from app.tools.email import DraftEmailTool, ReadEmailTool, SendEmailTool
from app.tools.mcp import CallMcpTool, DiscoverMcpToolsTool, ListMcpServersTool
from app.tools.obsidian import (
    OpenObsidianNoteTool,
    SaveObsidianNoteTool,
    SearchObsidianTool,
    SyncObsidianTool,
)
from app.tools.personal import (
    AddPersonalEventTool,
    AddPersonalTaskTool,
    CompletePersonalTaskTool,
    ListPersonalEventsTool,
    ListPersonalTasksTool,
    SearchPersonalFilesTool,
)
from app.tools.powershell import PowerShellTool
from app.tools.registry import ToolRegistry
from app.tools.social import SendSocialMessageTool
from app.tools.web_studio import (
    GenerateBusinessSiteFromScreenTool,
    GenerateBusinessSiteTool,
    ValidateBusinessSiteTool,
)
from app.tools.windows import NetworkPingTool, OpenApplicationTool, OpenUrlTool, ScreenshotTool
from app.voice.adapters import (
    EdgeNeuralSynthesizer,
    FasterWhisperRecognizer,
    KokoroSynthesizer,
    SapiSynthesizer,
    SoundDeviceMicrophone,
)
from app.voice.service import VoiceService
from app.web_studio import BusinessSiteGenerator, SitePreviewValidator
from app.workflows import ConversationalWorkflowBuilder, WorkflowStore


def _merge_specialists(*groups: Sequence[Specialist]) -> tuple[Specialist, ...]:
    """Preserve built-ins and add catalog roles without duplicate identities."""
    merged: list[Specialist] = []
    seen: set[str] = set()
    for specialist in (item for group in groups for item in group):
        identity = specialist.name.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(specialist)
    return tuple(merged)


def build_voice_service(settings: Settings) -> VoiceService | None:
    """Build voice adapters only when explicitly enabled; imports remain dependency-safe."""
    if not settings.get("voice.enabled", False):
        return None
    sapi = SapiSynthesizer(
        int(settings.get("voice.tts_rate", -1)),
        int(settings.get("voice.tts_volume", 92)),
        settings.get("voice.tts_voice_name"),
        language=str(settings.get("voice.tts_language", "pt-BR")),
        max_chunk_chars=int(settings.get("voice.tts_max_chunk_chars", 280)),
    )
    engine = str(settings.get("voice.tts_engine", "edge")).casefold()
    kokoro = KokoroSynthesizer(
            voice=str(settings.get("voice.tts_kokoro_voice", "pf_dora")),
            speed=float(settings.get("voice.tts_kokoro_speed", 0.94)),
            device=str(settings.get("voice.tts_kokoro_device", "cpu")),
            fallback=sapi,
            max_chunk_chars=int(settings.get("voice.tts_max_chunk_chars", 280)),
    )
    synthesizer = kokoro if engine in {"edge", "kokoro"} else sapi
    if engine == "edge":
        synthesizer = EdgeNeuralSynthesizer(
            voice=str(
                settings.get("voice.tts_edge_voice", "pt-BR-FranciscaNeural")
            ),
            rate=str(settings.get("voice.tts_edge_rate", "+0%")),
            pitch=str(settings.get("voice.tts_edge_pitch", "+0Hz")),
            timeout_seconds=float(settings.get("voice.tts_edge_timeout_seconds", 18)),
            fallback=kokoro,
        )
    return VoiceService(
        SoundDeviceMicrophone(int(settings.get("voice.sample_rate", 16_000))),
        FasterWhisperRecognizer(
            str(settings.get("voice.stt_model", "base")),
            settings.get("voice.stt_language", "pt"),
        ),
        synthesizer,
        wake_word=str(settings.get("voice.wake_word", "Kiara")),
        require_wake_word=bool(settings.get("voice.require_wake_word", True)),
        vad_enabled=bool(settings.get("voice.vad_enabled", True)),
        continuous_conversation=bool(settings.get("voice.continuous_conversation", False)),
        always_listen_for_wake_word=bool(settings.get("voice.always_listen_for_wake_word", True)),
        conversation_requires_wake_word=bool(
            settings.get("voice.conversation_requires_wake_word", True)
        ),
        wake_command_timeout_seconds=float(
            settings.get("voice.wake_command_timeout_seconds", 10.0)
        ),
        wake_min_confidence=float(settings.get("voice.wake_min_confidence", 0.65)),
    )


def build_app(settings: Settings, confirm=None) -> tuple[AgentCore, KillSwitch]:
    kill_switch = KillSwitch()
    hotkey = None
    if settings.get("security.global_hotkey_enabled", False):
        hotkey = EmergencyHotkey(kill_switch.trigger)
        hotkey.start()
        kill_switch.hotkey = hotkey
    mode = AutonomyMode(settings.get("autonomy.mode", "execute_with_confirmation"))
    gate = PermissionGate(mode, confirm=confirm)
    audit = AuditLog(settings.root / settings.get("security.audit_log", "data/audit.jsonl"))
    registry = ToolRegistry(gate, audit, kill_switch)
    personal_store = None
    if settings.get("personal.enabled", True):
        personal_store = PersonalOrganizerStore(
            settings.root / settings.get("personal.database", "data/personal.db")
        )
        registry.register(AddPersonalTaskTool(personal_store))
        registry.register(ListPersonalTasksTool(personal_store))
        registry.register(CompletePersonalTaskTool(personal_store))
        registry.register(AddPersonalEventTool(personal_store))
        registry.register(ListPersonalEventsTool(personal_store))
        raw_roots = settings.get("personal.file_roots", [])
        if not isinstance(raw_roots, list):
            raise ValueError("personal.file_roots deve ser uma lista.")
        roots = [Path(str(item)).expanduser() for item in raw_roots]
        registry.register(SearchPersonalFilesTool(roots))
    if settings.get("mcp.enabled", True):
        raw_mcp_servers = settings.get("mcp.servers", [])
        if not isinstance(raw_mcp_servers, list):
            raise ValueError("mcp.servers deve ser uma lista.")
        mcp_hub = McpHub(
            [McpServerConfig.from_mapping(item) for item in raw_mcp_servers],
            max_output_chars=int(settings.get("mcp.max_output_chars", 20_000)),
        )
        registry.register(ListMcpServersTool(mcp_hub))
        registry.register(DiscoverMcpToolsTool(mcp_hub))
        registry.register(CallMcpTool(mcp_hub))
    desktop_tools_enabled = bool(settings.get("desktop_tools.enabled", False))
    if desktop_tools_enabled:
        registry.register(OpenApplicationTool())
        registry.register(NetworkPingTool())
        registry.register(OpenUrlTool())
    browser = BrowserSession(
        headless=bool(settings.get("browser.headless", True)),
        timeout_ms=int(settings.get("browser.timeout_ms", 15_000)),
        allow_private_hosts=bool(settings.get("browser.allow_private_hosts", False)),
        profile_dir=settings.root
        / str(settings.get("browser.profile_dir", "data/browser-profile")),
    )
    registry.register(BrowserNavigateTool(browser))
    registry.register(BrowserFillTool(browser))
    registry.register(BrowserClickTool(browser))
    registry.register(BrowserReadTool(browser))
    registry.register(GoogleMapsBusinessSearchTool(browser))
    registry.register(OrganicConsumerSearchTool(browser))
    prospecting_policy_engine = ProspectingPolicyEngine(
        settings.root / "data" / "prospecting-policy.db",
        ProspectingPolicy(
            daily_limit=int(settings.get("leads.daily_contact_limit", 20)),
        ),
    )
    registry.register(SendSocialMessageTool(browser, prospecting_policy_engine))
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
    if desktop_tools_enabled:
        registry.register(ScreenshotTool(settings.root / "data" / "screenshots"))
        registry.register(
            SystemDiagnosticsTool(
                timeout_seconds=float(settings.get("security.powershell_timeout_seconds", 15))
            )
        )
        registry.register(
            PowerShellTool(
                list(settings.get("security.allowlisted_commands", [])),
                int(settings.get("security.powershell_timeout_seconds", 15)),
                kill_switch,
                int(settings.get("security.max_command_output_chars", 16_384)),
            )
        )
    memory = None
    embeddings = None
    if settings.get("memory.embeddings_enabled", False):
        embedding_provider = str(settings.get("memory.embedding_provider", "hash")).casefold()
        if embedding_provider == "ollama":
            embeddings = OllamaEmbeddingProvider(
                model=str(settings.get("memory.embedding_model", "embeddinggemma")),
                base_url=str(settings.get("llm.ollama_base_url", "http://127.0.0.1:11434")),
                timeout_seconds=float(settings.get("memory.embedding_timeout_seconds", 30)),
            )
        elif embedding_provider == "hash":
            embeddings = LocalHashEmbeddingProvider(
                int(settings.get("memory.embedding_dimensions", 384))
            )
        else:
            raise ValueError(f"Provider de embeddings desconhecido: {embedding_provider}")
    if settings.get("memory.enabled", True):
        memory = MemoryEngine(
            settings.root / settings.get("memory.database", "data/memory.db"),
            embedding_provider=embeddings,
            default_ttl={
                MemoryKind.WORKING: timedelta(
                    hours=float(settings.get("memory.working_ttl_hours", 24))
                )
            },
            retrieval_limit=int(settings.get("memory.retrieval_limit", 5)),
        )
    knowledge = None
    if settings.get("knowledge.enabled", True):
        knowledge = KnowledgeStore(
            settings.root / settings.get("knowledge.database", "data/knowledge.db"),
            chunk_size=int(settings.get("knowledge.chunk_size", 1_200)),
            chunk_overlap=int(settings.get("knowledge.chunk_overlap", 150)),
            embedding_provider=embeddings,
            relevance_threshold=float(settings.get("knowledge.relevance_threshold", 0.1)),
            max_chunks_per_source=int(settings.get("knowledge.max_chunks_per_source", 2)),
        )
        if embeddings is not None:
            knowledge.backfill_embeddings(
                batch_size=int(settings.get("memory.embedding_batch_size", 16))
            )
    obsidian = None
    if settings.get("integrations.obsidian.enabled", False):
        if knowledge is None:
            raise ValueError("A integração Obsidian requer knowledge.enabled.")
        vault_path = str(settings.get("integrations.obsidian.vault_path", "")).strip()
        if not vault_path:
            raise ValueError("Configure integrations.obsidian.vault_path.")
        obsidian = ObsidianVaultIndex(
            vault_path,
            knowledge,
            settings.root / settings.get("integrations.obsidian.state", "data/obsidian-index.json"),
            max_file_bytes=int(settings.get("integrations.obsidian.max_file_bytes", 2_000_000)),
        )
        obsidian.sync()
        registry.register(SyncObsidianTool(obsidian))
        registry.register(SearchObsidianTool(knowledge))
        registry.register(OpenObsidianNoteTool(obsidian))
        if settings.get("integrations.obsidian.write_enabled", False):
            registry.register(SaveObsidianNoteTool(obsidian))
    active_window_provider = get_active_window if settings.get("screen.enabled", False) else lambda: None
    context = ContextManager(
        active_window_provider,
        memory,
        knowledge,
        knowledge_max_chars=int(settings.get("knowledge.context_max_chars", 6_000)),
    )
    provider = build_llm_provider(settings)
    site_generator = None
    site_validator = None
    if settings.get("web_studio.enabled", True):
        site_output_root = settings.root / settings.get("web_studio.output_root", "generated-sites")
        site_validator = SitePreviewValidator(
            site_output_root,
            timeout_ms=int(settings.get("web_studio.preview_timeout_ms", 10_000)),
        )
        site_generator = BusinessSiteGenerator(
            provider,
            reference_root=settings.root
            / settings.get("web_studio.reference_root", "data/site-references"),
            output_root=site_output_root,
            max_image_bytes=int(settings.get("web_studio.max_image_bytes", 10_000_000)),
        )
        registry.register(GenerateBusinessSiteTool(site_generator, site_validator))
        registry.register(ValidateBusinessSiteTool(site_validator))
    perception = ScreenPerception(EventBus(), PerceptionOptions.from_settings(settings))
    if site_generator is not None and site_validator is not None:
        registry.register(
            GenerateBusinessSiteFromScreenTool(site_generator, site_validator, perception)
        )
    vision_fallback = None
    visual_state_verifier = None
    if settings.get("computer_use.enabled", False) and settings.get(
        "computer_use.visual_validation_enabled", False
    ):
        visual_state_verifier = EphemeralVisualStateVerifier(
            perception,
            change_threshold=float(settings.get("computer_use.visual_change_threshold", 0.02)),
        )
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
    resources = [browser, email.store, prospecting_policy_engine]
    if hotkey is not None:
        resources.append(hotkey)
    if personal_store is not None:
        resources.append(personal_store)
    if memory is not None:
        resources.append(memory)
    if knowledge is not None:
        resources.append(knowledge)
    resources.append(provider)
    lead_store = LeadStore(settings.root / settings.get("leads.database", "data/leads.db"))
    resources.append(lead_store)
    consumer_store = ConsumerStore(
        settings.root / settings.get("consumers.database", "data/consumers.db")
    )
    resources.append(consumer_store)
    local_specialists = (
        load_local_specialists()
        if settings.get("agents.load_local_specialists", False)
        else ()
    )
    built_in_specialists = (
        GeneralistSpecialist(),
        ResearchSpecialist(),
        SalesDevelopmentSpecialist(),
    )
    agent_router = AgentRouter(
        provider,
        specialists=_merge_specialists(built_in_specialists, local_specialists),
        generalist=GeneralistSpecialist(),
    )
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
            require_visual_validation=bool(
                settings.get("planning.require_visual_validation", True)
            ),
            recovery_on_failure=bool(settings.get("planning.recovery_on_failure", True)),
        )
    core = AgentCore(
        registry,
        provider,
        context,
        agent_router=agent_router,
        resources=resources,
        task_planner=planner,
        perception=perception,
        feedback_learning=(
            ObsidianLearningStore(obsidian)
            if obsidian is not None
            and settings.get("integrations.obsidian.feedback_learning_enabled", False)
            else None
        ),
        correction_inbox=CorrectionInbox(
            settings.root
            / settings.get("feedback.correction_inbox", "data/correction-inbox.jsonl")
        ),
        feedback_prompt=str(settings.get("integrations.obsidian.feedback_prompt", "Te auxiliei?")),
        workflow_builder=ConversationalWorkflowBuilder(
            WorkflowStore(settings.root / settings.get("workflows.database", "data/workflows.db"))
        ),
        lead_store=lead_store,
        consumer_store=consumer_store,
    )
    core.obsidian = obsidian
    core.settings = settings
    core.background = BackgroundServices(
        settings,
        registry,
        screen=perception,
        provider=provider,
        context=context,
        obsidian=obsidian,
    )
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
