from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExecutionResult:
    success: bool
    output_path: Optional[str] = None
    message: Optional[str] = None

class BaseExecutor(ABC):
    @abstractmethod
    async def execute(self, prompt: str, metadata: Optional[dict] = None) -> ExecutionResult:
        pass
