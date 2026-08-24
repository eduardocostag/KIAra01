"""Especialistas de raciocínio da Kiara; execução permanece no ToolRegistry."""

from app.agents.catalog import CatalogSpecialist, load_local_specialists
from app.agents.router import AgentRouter

__all__ = ["AgentRouter", "CatalogSpecialist", "load_local_specialists"]
