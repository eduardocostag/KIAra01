from .base import BaseExecutor, ExecutionResult


class VoiceStudioExecutor(BaseExecutor):
    async def execute(self, prompt: str, metadata: dict | None = None) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            message="VoiceStudio não está conectado. Configure um serviço real de síntese de voz antes de executar.",
        )
