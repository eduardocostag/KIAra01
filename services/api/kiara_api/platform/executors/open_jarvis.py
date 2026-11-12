from .base import BaseExecutor, ExecutionResult


class OpenJarvisExecutor(BaseExecutor):
    async def execute(self, prompt: str, metadata: dict | None = None) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            message="OpenJarvis não está conectado. Configure um executor local autorizado antes de executar ações.",
        )
