from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from app.chat.auth import AuthorizationError
from app.chat.service import ChatError

MAX_BODY_BYTES = 8_000_000


class BinaryResult:
    """A file streamed back to the browser (e.g. a rendered video)."""

    def __init__(self, path, mime: str):
        self.path = path
        self.mime = mime


def validate_origins(raw: str) -> frozenset[str]:
    origins = set()
    for candidate in raw.split(","):
        value = candidate.strip().rstrip("/")
        try:
            parts = urlsplit(value)
            if (parts.hostname and parts.scheme in {"http", "https"} and not parts.username
                    and not parts.password and not parts.path and not parts.query and not parts.fragment
                    and (parts.scheme == "https" or parts.hostname in {"127.0.0.1", "localhost", "::1"})):
                _ = parts.port
                origins.add(value)
        except ValueError:
            continue
    if not origins:
        raise ValueError("Configure KIARA_CHAT_ALLOWED_ORIGINS com origens exatas HTTPS.")
    return frozenset(origins)


class ChatBridge:
    def __init__(self, service, verifier, origins: frozenset[str], automation=None, videos=None):
        self.service = service
        self.videos = videos
        self.verifier = verifier
        self.origins = origins
        self.automation = automation
        self._slots = threading.BoundedSemaphore(2)

    def _video(self, payload: dict, identity):
        from app.video_studio.engine import VideoError
        owner = f"{identity.organization_id}:{identity.user_id}"
        action = payload.get("action")
        try:
            if action == "start":
                prompt = payload.get("prompt")
                if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4_000:
                    raise ChatError(422, "Descreva o vídeo em até 4.000 caracteres.")
                audience = payload.get("audience") or []
                if not isinstance(audience, list) or len(audience) > 3 or not all(isinstance(n, str) and 0 < len(n.strip()) <= 30 for n in audience):
                    raise ChatError(422, "Informe até 3 nomes de até 30 caracteres.")
                problem = video_requirements()
                if problem:
                    raise ChatError(503, problem)
                job = self.videos.start(owner, prompt.strip(), [n.strip() for n in audience], payload.get("quality") or "1080p")
                return {"text": "Comecei a produzir o vídeo: vou escrever o roteiro, gravar a minha fala e renderizar as cenas. Acompanhe o progresso aqui.", "video": job}
            if action == "status":
                return {"video": self.videos.status(owner, payload.get("job_id"))}
            if action == "download":
                return BinaryResult(self.videos.video(owner, payload.get("job_id")), "video/mp4")
        except VideoError as error:
            raise ChatError(409, str(error)) from None
        raise ChatError(422, "Ação de vídeo desconhecida.")

    def dispatch(self, path: str, payload: dict, identity):
        if path == "/api/status":
            result = self.service.status()
            if self.automation:
                for item in result["capabilities"]:
                    if item["id"] == "automation":
                        item.update(available=not self.automation.kill_switch.stopped,
                                    detail="Diagnóstico local com aprovação, plano único, auditoria e parada de emergência. Outros comandos só recebem planejamento.")
            if self.videos:
                chat_ready = any(item["id"] == "chat" and item["available"] for item in result["capabilities"])
                problem = video_requirements()
                for item in result["capabilities"]:
                    if item["id"] == "video":
                        item.update(available=chat_ready and not problem,
                                    detail=problem or ("Vídeos de apresentação narrados pela Kiara, com telas reais do sistema. A produção leva alguns minutos."
                                                       if chat_ready else "Conecte a IA do Chat para a Kiara escrever o roteiro."))
            return result
        if path == "/api/video" and self.videos:
            return self._video(payload, identity)
        if path == "/api/plan" and self.automation:
            prompt = payload.get("prompt")
            if isinstance(prompt, str) and 0 < len(prompt) <= 8_000:
                result = self.automation.prepare(prompt, identity)
                if result:
                    return result
        if path == "/api/execute" and self.automation:
            return asyncio.run(self.automation.execute(payload, identity))
        if path == "/api/stop" and self.automation:
            return self.automation.stop()
        handlers = {"/api/chat": self.service.chat, "/api/build": self.service.build,
                    "/api/speech": self.service.speech, "/api/transcribe": self.service.transcribe,
                    "/api/plan": self.service.plan}
        if path in {"/api/image", "/api/video"}:
            raise ChatError(503, "Nenhum gerador real foi configurado para este recurso. Nenhum arquivo foi criado.")
        method = handlers.get(path)
        if method is None:
            raise ChatError(404, "Operação local desconhecida.")
        return asyncio.run(method(payload))


def video_requirements() -> str:
    """Empty when this computer can produce videos; otherwise what is missing."""
    import importlib.util

    from app.video_studio.engine import VideoError, find_ffmpeg
    missing = [name for name, module in (("edge-tts", "edge_tts"), ("Playwright", "playwright")) if importlib.util.find_spec(module) is None]
    try:
        find_ffmpeg()
    except VideoError:
        missing.append("ffmpeg")
    return f"Para gerar vídeos, instale neste computador: {', '.join(missing)}." if missing else ""


def handler_for(bridge: ChatBridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "KiaraChatBridge/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def _json(self, status, payload, origin=None):
            raw = b"" if status == 204 else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if origin in bridge.origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                if self.headers.get("Access-Control-Request-Private-Network") == "true":
                    self.send_header("Access-Control-Allow-Private-Network", "true")
            self.end_headers()
            self.wfile.write(raw)

        def _file(self, result: BinaryResult, origin):
            size = result.path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", result.mime)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if origin in bridge.origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.connection.settimeout(300)
            with result.path.open("rb") as handle:
                while chunk := handle.read(1 << 20):
                    self.wfile.write(chunk)

        def do_OPTIONS(self):
            origin = self.headers.get("Origin")
            self._json(204 if origin in bridge.origins else 403, {}, origin)

        def do_POST(self):
            origin = self.headers.get("Origin")
            if origin not in bridge.origins:
                self._json(403, {"error": "Origem não autorizada."})
                return
            acquired = False
            try:
                authorization = self.headers.get("Authorization", "")
                if not authorization.startswith("Bearer "):
                    raise AuthorizationError("Entre na Kiara para continuar.")
                # Authenticate before parsing or processing user-controlled media.
                identity = bridge.verifier.verify(authorization[7:])
                if self.headers.get_content_type() != "application/json":
                    raise ChatError(415, "Envie JSON.")
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise ChatError(400, "Tamanho inválido.") from None
                if not 0 < size <= MAX_BODY_BYTES:
                    raise ChatError(413, "Solicitação acima de 8 MB ou vazia.")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ChatError(422, "Envie um objeto JSON.")
                if self.path == "/api/stop" and bridge.automation:
                    self._json(200, bridge.automation.stop(), origin)
                    return
                acquired = bridge._slots.acquire(blocking=False)
                if not acquired:
                    raise ChatError(429, "A ponte está ocupada. Aguarde a tarefa atual.")
                result = bridge.dispatch(self.path, payload, identity)
                if isinstance(result, BinaryResult):
                    self._file(result, origin)
                else:
                    self._json(200, result, origin)
            except AuthorizationError as error:
                self._json(403, {"error": str(error)}, origin)
            except ChatError as error:
                self._json(error.status, {"error": str(error)}, origin)
            except (ValueError, UnicodeError):
                self._json(400, {"error": "Solicitação JSON inválida."}, origin)
            except Exception:  # noqa: BLE001 - sanitized HTTP boundary
                self._json(503, {"error": "O serviço local não concluiu a operação. Verifique as dependências."}, origin)
            finally:
                if acquired:
                    bridge._slots.release()

        def log_message(self, _format, *_args):
            # Never log headers, tokens, prompts, transcripts or generated output.
            return

    return Handler


def serve(bridge: ChatBridge, host: str = "127.0.0.1", port: int = 3008):
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("A ponte deve escutar somente em loopback IPv4.")
    return ThreadingHTTPServer((host, port), handler_for(bridge))
