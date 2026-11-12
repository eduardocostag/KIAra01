from .base import BaseExecutor, ExecutionResult


class MoneyPrinterTurboExecutor(BaseExecutor):
    async def execute(self, prompt: str, metadata: dict | None = None) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            message="MoneyPrinterTurbo não está conectado. Configure um serviço real de produção de vídeo antes de executar.",
        )
