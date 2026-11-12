from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Execution outcome; success requires a real completed operation or artifact."""

    success: bool
    output_path: str | None = None
    message: str | None = None

class BaseExecutor(ABC):
    @abstractmethod
    async def execute(self, prompt: str, metadata: dict | None = None) -> ExecutionResult:
        pass
