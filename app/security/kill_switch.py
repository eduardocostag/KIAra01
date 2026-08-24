from __future__ import annotations

import subprocess
import threading

import psutil


class KillSwitch:
    def __init__(self) -> None:
        self._stopped = threading.Event()
        self._processes: set[subprocess.Popen[str]] = set()
        self._lock = threading.Lock()

    @property
    def stopped(self) -> bool:
        return self._stopped.is_set()

    def register(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            if self._stopped.is_set():
                process.kill()
                return
            self._processes.add(process)

    def unregister(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes.discard(process)

    def trigger(self) -> None:
        self._stopped.set()
        with self._lock:
            processes = tuple(self._processes)
        for process in processes:
            if process.poll() is None:
                self._kill_tree(process.pid)

    def reset(self) -> None:
        self._stopped.clear()

    @staticmethod
    def _kill_tree(pid: int) -> None:
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except psutil.Error:
            return
