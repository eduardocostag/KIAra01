from __future__ import annotations

import re
import tomllib
import unicodedata
from pathlib import Path

from app.agents.contracts import Specialist

_ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "accessibility-auditor": ("acessibilidade", "wcag", "leitor de tela", "contraste"),
    "agentic-identity-trust": ("identidade de agente", "confianca", "autorizacao"),
    "agents-orchestrator": ("orquestrar agentes", "equipe de agentes", "delegacao"),
    "ai-data-remediation-engineer": ("corrigir dados", "anomalia de dados", "remediacao"),
    "ai-engineer": ("inteligencia artificial", "ia", "modelo", "machine learning"),
    "ai-generated-code-auditor": ("codigo gerado por ia", "auditar codigo", "cwe"),
    "api-platform-engineer": ("api", "openapi", "endpoint", "sdk"),
    "api-tester": ("testar api", "teste de endpoint", "contrato api"),
    "appsec-engineer": ("seguranca", "vulnerabilidade", "appsec", "cwe"),
    "automation-governance-architect": ("governanca de automacao", "aprovacao", "rollback"),
    "autonomous-optimization-architect": ("otimizacao autonoma", "guardrail", "custo de api"),
    "backend-architect": ("backend", "servidor", "api", "microsservico"),
    "cloud-security-architect": ("seguranca em nuvem", "cloud", "zero trust"),
    "code-reviewer": ("revisar codigo", "code review", "qualidade do codigo"),
    "codebase-onboarding-engineer": ("entender codigo", "onboarding", "codebase"),
    "compliance-auditor": ("conformidade", "compliance", "soc 2", "iso 27001"),
    "data-consolidation-agent": ("consolidar dados", "relatorio comercial", "pipeline de vendas"),
    "data-engineer": ("dados", "etl", "pipeline", "lakehouse"),
    "data-privacy-officer": ("privacidade", "lgpd", "gdpr", "dados pessoais"),
    "data-visualization-engineer": ("grafico", "dashboard", "visualizacao de dados"),
    "database-optimizer": ("banco de dados", "sql", "consulta", "indice"),
    "database-reliability-engineer": ("confiabilidade do banco", "backup", "failover"),
    "desktop-app-engineer": ("windows", "desktop", "electron", "tauri"),
    "developer-tooling-engineer": ("ferramenta de desenvolvimento", "cli", "dx"),
    "devops-automator": ("devops", "ci/cd", "deploy", "docker"),
    "email-intelligence-engineer": ("email", "extrair email", "thread de email"),
    "evidence-collector": ("coletar evidencia", "captura de tela", "prova visual"),
    "executive-summary-generator": ("resumo executivo", "c-level", "diretoria"),
    "finops-engineer": ("custo cloud", "finops", "nuvem", "gasto"),
    "frontend-developer": ("frontend", "react", "css", "interface"),
    "git-workflow-master": ("git", "branch", "commit", "pull request"),
    "identity-access-engineer": ("login", "oauth", "identidade", "acesso"),
    "incident-response-commander": ("incidente", "indisponibilidade", "on-call"),
    "it-service-manager": ("itil", "servico de ti", "sla", "cmdb"),
    "jira-workflow-steward": ("jira", "ticket", "issue", "workflow git"),
    "mcp-builder": ("mcp", "model context protocol", "ferramenta de agente"),
    "minimal-change-engineer": ("mudanca minima", "diff pequeno", "sem refatorar"),
    "mobile-app-builder": ("aplicativo mobile", "android", "ios"),
    "mobile-release-engineer": ("publicar aplicativo", "app store", "play store"),
    "model-qa-specialist": ("avaliar modelo", "eval", "calibracao", "modelo"),
    "multi-agent-systems-architect": ("multiagente", "agentes", "orquestrador"),
    "network-engineer": ("rede", "firewall", "roteamento", "cisco"),
    "payments-billing-engineer": ("pagamento", "cobranca", "assinatura", "stripe"),
    "penetration-tester": ("teste de penetracao", "pentest", "exploracao autorizada"),
    "performance-benchmarker": ("desempenho", "benchmark", "latencia", "carga"),
    "privacy-engineer": ("privacidade", "pii", "retencao", "consentimento"),
    "product-manager": ("produto", "mvp", "roadmap", "metrica"),
    "product-sprint-prioritizer": ("priorizar sprint", "backlog", "prioridade"),
    "project-manager-senior": ("gerenciar projeto", "cronograma", "dependencia"),
    "project-shepherd": ("acompanhar projeto", "coordenar equipe", "risco de projeto"),
    "prompt-engineer": ("prompt", "instrucao", "llm"),
    "rag-pipeline-engineer": ("rag", "embedding", "recuperacao", "conhecimento"),
    "rapid-prototyper": ("prototipo", "mvp rapido", "prova de conceito"),
    "reality-checker": ("pronto para producao", "validar evidencia", "gate final"),
    "realtime-collaboration-engineer": ("tempo real", "websocket", "sse", "crdt"),
    "search-relevance-engineer": ("busca", "relevancia", "elasticsearch", "bm25"),
    "security-architect": ("arquitetura de seguranca", "ameaca", "zero trust"),
    "secrets-credential-hygiene-engineer": ("segredo", "credencial", "chave de api", "senha"),
    "senior-developer": ("desenvolvimento avancado", "laravel", "livewire"),
    "software-architect": ("arquitetura", "software", "design de sistema"),
    "sre": ("sre", "confiabilidade", "slo", "observabilidade"),
    "support-analytics-reporter": ("analise de suporte", "kpi", "relatorio", "dashboard"),
    "technical-writer": ("documentacao", "readme", "manual", "tutorial"),
    "test-automation-engineer": ("teste automatizado", "playwright", "cypress", "qa"),
    "test-results-analyzer": ("resultado de teste", "falha de teste", "qualidade"),
    "threat-detection-engineer": ("detectar ameaca", "siem", "mitre", "alerta"),
    "tool-evaluator": ("avaliar ferramenta", "comparar tecnologia", "ferramenta"),
    "ui-designer": ("design visual", "ui", "cores", "layout"),
    "ui-finish-gate-reviewer": ("acabamento da interface", "qualidade visual", "ui final"),
    "ux-architect": ("ux", "experiencia", "usabilidade", "jornada"),
    "ux-researcher": ("pesquisa de usuario", "entrevista", "usabilidade"),
    "video-streaming-engineer": ("streaming de video", "hls", "dash", "transmissao"),
    "voice-ai-integration-engineer": ("voz", "audio", "microfone", "transcricao"),
    "visual-operations-copilot": ("tela", "visao", "assistente", "operacional"),
    "workflow-architect": ("workflow", "fluxo", "processo", "automacao"),
    "workflow-optimizer": ("otimizar processo", "melhorar fluxo", "produtividade"),
}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _words(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9][a-z0-9+.-]{2,}", _normalize(value))}


class CatalogSpecialist(Specialist):
    """Especialista descoberto por metadados, nunca por prompts locais executáveis."""

    def __init__(self, slug: str, display_name: str, description: str) -> None:
        self.slug = slug
        self.name = f"especialista:{slug}"
        self.description = description[:300]
        aliases = _ROLE_ALIASES.get(slug, ())
        self.keywords = frozenset(
            _words(slug.replace("-", " ")) | _words(display_name) | {_normalize(item) for item in aliases}
        )
        self.system_prompt = (
            "Você é um especialista consultivo da Kiara. Trabalhe somente no domínio "
            "identificado pelo nome da função e respeite os limites de segurança."
        )

    def score(self, message: str) -> int:
        normalized = _normalize(message)
        return sum(3 if " " in keyword else 1 for keyword in self.keywords if keyword in normalized)

    def instructions(self) -> str:
        return (
            f"Atue no escopo consultivo de {self.name}. Dê uma análise verificável, "
            "declare incertezas e encaminhe assuntos fora do seu escopo ao coordenador."
        )


def default_catalog_path() -> Path:
    return Path.home() / ".codex" / "agents"


def load_local_specialists(directory: Path | None = None) -> tuple[CatalogSpecialist, ...]:
    """Carrega apenas nome/descrição; `developer_instructions` nunca entra no modelo."""

    root = directory or default_catalog_path()
    specialists: list[CatalogSpecialist] = []
    for path in sorted(root.glob("*.toml")):
        try:
            with path.open("rb") as stream:
                metadata = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError):
            # Um arquivo legado malformado ainda pode contribuir com uma identidade
            # consultiva segura. O nome do arquivo é dado, nunca instrução executável.
            if path.is_file() and re.fullmatch(r"[a-z0-9-]+", path.stem.casefold()):
                slug = path.stem.casefold()
                display_name = slug.replace("-", " ").title()
                specialists.append(CatalogSpecialist(slug, display_name, "Especialidade local"))
            continue
        slug = path.stem.casefold()
        name = metadata.get("name")
        description = metadata.get("description")
        if not isinstance(name, str) or not isinstance(description, str):
            continue
        specialists.append(CatalogSpecialist(slug, name[:100], description))
    return tuple(specialists)
