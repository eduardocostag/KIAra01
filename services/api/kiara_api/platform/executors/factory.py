from typing import Dict, Type
from .base import BaseExecutor
from .voice_studio import VoiceStudioExecutor
from .wan2_1 import Wan2_1Executor
from .money_printer_turbo import MoneyPrinterTurboExecutor
from .open_jarvis import OpenJarvisExecutor

class ExecutorFactory:
    _executors: Dict[str, Type[BaseExecutor]] = {
        "voice_studio": VoiceStudioExecutor,
        "wan2_1": Wan2_1Executor,
        "money_printer_turbo": MoneyPrinterTurboExecutor,
        "open_jarvis": OpenJarvisExecutor,
    }

    @classmethod
    def get_executor(cls, name: str) -> BaseExecutor:
        executor_class = cls._executors.get(name)
        if not executor_class:
            raise ValueError(f"Executor '{name}' não encontrado.")
        return executor_class()
