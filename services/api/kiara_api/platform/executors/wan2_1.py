from .base import BaseExecutor, ExecutionResult


class Wan2_1Executor(BaseExecutor):
    async def execute(self, prompt: str, metadata: dict | None = None) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            message="Wan2.1 não está conectado. Configure um serviço real de geração de vídeo antes de executar.",
        )
