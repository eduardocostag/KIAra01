from .base import BaseExecutor, ExecutionResult

class Wan2_1Executor(BaseExecutor):
    async def execute(self, prompt: str, metadata: dict = None) -> ExecutionResult:
        print(f"[Wan2_1Executor] Simulando geração de vídeo para: {prompt}")
        # Lógica para chamar o Wan2.1
        output_path = f"/tmp/video_output_{hash(prompt)}.mp4"
        return ExecutionResult(success=True, output_path=output_path, message="Geração de vídeo simulada com sucesso.")
