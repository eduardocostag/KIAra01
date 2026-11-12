from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from app.chat.auth import AuthorizationError
from app.chat.service import ChatError

MAX_BODY_BYTES = 8_000_000


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
    def __init__(self, service, verifier, origins: frozenset[str], automation=None):
        self.service = service
        self.verifier = verifier
        self.origins = origins
        self.automation = automation
        self._slots = threading.BoundedSemaphore(2)

    def dispatch(self, path: str, payload: dict, identity):
        if path == "/api/status":
            result = self.service.status()
            if self.automation:
                for item in result["capabilities"]:
                    if item["id"] == "automation":
                        item.update(available=not self.automation.kill_switch.stopped,
                                    detail="Diagnóstico local com aprovação, plano único, auditoria e parada de emergência. Outros comandos só recebem planejamento.")
            return result
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
