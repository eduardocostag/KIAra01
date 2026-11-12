from dataclasses import dataclass
from typing import List, Optional
from kiara_api.platform.executors.factory import ExecutorFactory

@dataclass
class TaskIntent:
    action_type: str
    target_executor: str
    prompt: str
    metadata: Optional[dict] = None

class KiaraBrain:
    """
    Orquestrador central do Agente Geral da Kiara.
    Identifica a intenção do usuário e roteia para o executor/ferramenta ideal.
    """
    
    def analyze_intent(self, command: str) -> TaskIntent:
        cmd_lower = command.lower()
        
        # Detecção de intenção para Vídeo
        if any(w in cmd_lower for w in ["vídeo", "video", "filme", "animar"]):
            if "viral" in cmd_lower or "reels" in cmd_lower or "tiktok" in cmd_lower:
                return TaskIntent(
                    action_type="viral_video_generation",
                    target_executor="money_printer_turbo",
                    prompt=command
                )
            return TaskIntent(
                action_type="video_generation",
                target_executor="wan2_1",
                prompt=command
            )
            
        # Detecção de intenção para Voz/Áudio
        if any(w in cmd_lower for w in ["fale", "voz", "áudio", "audio", "narrar", "leia"]):
            return TaskIntent(
                action_type="text_to_speech",
                target_executor="voice_studio",
                prompt=command
            )
            
        # Padrão: Execução via Jarvis Core (Agente Geral de OS / Computador)
        return TaskIntent(
            action_type="general_automation",
            target_executor="open_jarvis",
            prompt=command
        )

    def create_execution_plan(self, command: str) -> List[TaskIntent]:
        cmd_lower = command.lower()
        plan = []
        
        # Tarefas multimodais complexas (vídeo viral + voz)
        if "vídeo viral" in cmd_lower and "voz" in cmd_lower:
            plan.append(TaskIntent(
                action_type="text_to_speech",
                target_executor="voice_studio",
                prompt="Gerar voz narrativa para vídeo viral"
            ))
            plan.append(TaskIntent(
                action_type="viral_video_generation",
                target_executor="money_printer_turbo",
                prompt=command
            ))
            return plan
            
        return [self.analyze_intent(command)]
