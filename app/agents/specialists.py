from __future__ import annotations

from app.agents.contracts import Specialist


class GeneralistSpecialist(Specialist):
    name = "generalista"
    description = "Conversas e solicitações sem domínio predominante"
    keywords = frozenset()
    system_prompt = "Você é a assistente pessoal Kiara, clara, útil e honesta."

    def instructions(self) -> str:
        return "Responda diretamente, usando o contexto apenas quando relevante."


class SoftwareSpecialist(Specialist):
    name = "engenharia_de_software"
    description = "Código, arquitetura, debugging e testes"
    keywords = frozenset(
        {"código", "codigo", "program", "bug", "api", "teste", "arquitetura", "python"}
    )
    system_prompt = "Você é especialista em engenharia de software pragmática e verificável."
    context_keys = frozenset(
        {"user_message", "recent_actions", "relevant_memories", "relevant_knowledge"}
    )

    def instructions(self) -> str:
        return "Diagnostique tecnicamente, explicite hipóteses e proponha passos testáveis."


class SecuritySpecialist(Specialist):
    name = "seguranca"
    description = "Privacidade, riscos, permissões e segurança defensiva"
    keywords = frozenset(
        {"segurança", "seguranca", "privacidade", "vulner", "permiss", "senha", "risco"}
    )
    system_prompt = "Você é especialista defensivo em segurança e privacidade por padrão."

    def instructions(self) -> str:
        return "Avalie ameaça, impacto, mitigação e necessidade de aprovação humana."


class ProductivitySpecialist(Specialist):
    name = "produtividade"
    description = "Planejamento, prioridades, rotinas e organização"
    keywords = frozenset(
        {"planej", "agenda", "prioridade", "tarefa", "rotina", "produtiv", "organiza"}
    )
    system_prompt = "Você é especialista em planejamento executável e sustentável."
    context_keys = frozenset(
        {"user_message", "recent_actions", "relevant_memories", "relevant_knowledge"}
    )

    def instructions(self) -> str:
        return "Converta o objetivo em prioridades, próximos passos e critérios de conclusão."


class ResearchSpecialist(Specialist):
    name = "pesquisa"
    description = "Síntese, comparação e análise de evidências"
    keywords = frozenset(
        {"pesquis", "compare", "evidência", "evidencia", "fonte", "estudo", "investigue"}
    )
    system_prompt = "Você é especialista em pesquisa rigorosa e síntese de evidências."

    def instructions(self) -> str:
        return "Separe fatos, inferências e lacunas; não invente fontes nem dados."
