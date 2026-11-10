from __future__ import annotations

import asyncio
import base64
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID, uuid4

EXTENSION_ID = "ejnelpchnognifbmcecmbcjehkjbnnoe"
EXTENSION_ORIGIN = f"chrome-extension://{EXTENSION_ID}"
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 17843


class ExtensionBridgeError(RuntimeError):
    pass


class ChromeExtensionBridge:
    def __init__(self, *, require_site_session=False):
        self.require_site_session = require_site_session
        self._condition = threading.Condition()
        self._results: dict[str, dict] = {}
        self._last_heartbeat = 0.0
        self._last_ready = True
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._commands: dict[str, dict] = {}
        self._command_results: dict[str, dict] = {}
        self._session_token = ""
        self._session_deadline = 0.0
        self._session_subject = None

    def accept_session(self, payload):
        token = payload.get("access_token")
        with self._condition:
            if token is None:
                self._session_token = ""
                self._session_deadline = 0.0
                return
            expires = payload.get("expires_at")
            if (not isinstance(token, str) or len(token) > 16384
                    or type(expires) not in (int, float)):
                raise ValueError("invalid session")
            try:
                parts = token.split(".")
                if len(parts) != 3:
                    raise ValueError
                claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
                subject = str(UUID(claims["sub"]))
                deadline = min(float(expires), float(claims["exp"]))
                if not time.time() < deadline <= time.time() + 3600:
                    raise ValueError
            except (ValueError, TypeError, KeyError, AttributeError):
                raise ValueError("invalid session") from None
            if self._session_subject and self._session_subject != subject:
                self._session_token = ""
                self._session_deadline = 0.0
                raise ValueError("restart required for account switch")
            # Claims here only limit lifetime/account affinity. The remote API
            # remains responsible for signature validation and authorization.
            self._session_subject = subject
            self._session_token = token
            self._session_deadline = min(deadline, time.time() + 90)

    def session_token(self):
        with self._condition:
            if time.time() >= self._session_deadline:
                self._session_token = ""
            return self._session_token

    def start(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def _origin_allowed(self):
                return (self.headers.get("Origin") == EXTENSION_ORIGIN
                        and self.headers.get("Host") == f"{BRIDGE_HOST}:{BRIDGE_PORT}")

            def _cors_headers(self):
                self.send_header("Access-Control-Allow-Origin", EXTENSION_ORIGIN)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

            def _json(self, status, payload):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                if not self._origin_allowed():
                    self.send_error(403)
                    return
                self.send_response(status)
                self._cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                if not self._origin_allowed():
                    self.send_error(403)
                    return
                self.send_response(204)
                self._cors_headers()
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self):
                if self.path not in {"/v1/session", "/v1/heartbeat", "/v1/scan", "/v1/commands/next", "/v1/commands/result", "/v1/commands/authorize"}:
                    self._json(404, {"error": "not_found"})
                    return
                if self.headers.get("Origin") != EXTENSION_ORIGIN or self.headers.get("Host") != f"{BRIDGE_HOST}:{BRIDGE_PORT}":
                    self.send_error(403)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 <= length <= 2_000_000:
                        raise ValueError
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise TypeError
                    if self.path == "/v1/session":
                        bridge.accept_session(payload)
                        self._json(200, {"ok": True})
                        return
                    if self.path == "/v1/commands/next":
                        active = not bridge.require_site_session or bool(bridge.session_token())
                        self._json(200, {"command": bridge.next_command() if active else None})
                        return
                    if self.path == "/v1/commands/result":
                        bridge.accept_command_result(payload)
                        self._json(200, {"ok": True})
                        return
                    if self.path == "/v1/commands/authorize":
                        with bridge._condition:
                            command = bridge._commands.get(payload.get("id"))
                            allowed = bool(command and command["claimed"]
                                           and (not bridge.require_site_session or bridge.session_token())
                                           and command["expires_at"] > time.time()
                                           and command["phone"] == payload.get("phone")
                                           and command["id"] not in bridge._command_results)
                        self._json(200, {"allowed": allowed})
                        return
                    if self.path == "/v1/heartbeat":
                        with bridge._condition:
                            bridge._last_heartbeat = time.monotonic()
                            bridge._last_ready = payload.get("ready", True) is True
                            bridge._condition.notify_all()
                        self._json(200, {"ok": True})
                        return
                    bridge._accept_scan(payload)
                    self._json(200, {"ok": True})
                except (ValueError, TypeError, KeyError):
                    self._json(400, {"error": "invalid_payload"})

        self._server = ThreadingHTTPServer((BRIDGE_HOST, BRIDGE_PORT), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, name="kiara-chrome-bridge", daemon=True)
        self._thread.start()

    def close(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def online(self):
        with self._condition:
            return time.monotonic() - self._last_heartbeat <= 45 and self._last_ready

    def _accept_scan(self, payload):
        try:
            job_id = str(UUID(payload["job_id"]))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ValueError("invalid job id") from None
        scanned = payload.get("scanned")
        skipped = payload.get("skipped")
        conversations = payload.get("conversations")
        if (type(scanned) is not int or not 0 <= scanned <= 30
                or type(skipped) is not int or not 0 <= skipped <= 30
                or not isinstance(conversations, list) or len(conversations) > 30):
            raise ValueError("invalid scan result")
        checked = []
        seen_phones = set()
        for conversation in conversations:
            if not isinstance(conversation, dict):
                raise TypeError("invalid conversation")
            phone = conversation.get("phone")
            name = conversation.get("name")
            messages = conversation.get("messages")
            if (not isinstance(phone, str) or not re.fullmatch(r"[1-9][0-9]{7,14}", phone)
                    or phone in seen_phones or not isinstance(name, str) or not 1 <= len(name) <= 160
                    or not isinstance(messages, list) or not 1 <= len(messages) <= 20):
                raise ValueError("invalid conversation")
            seen_phones.add(phone)
            checked_messages = []
            for message in messages:
                if (not isinstance(message, dict) or message.get("direction") not in {"in", "out"}
                        or not isinstance(message.get("id"), str) or len(message["id"]) > 250
                        or not isinstance(message.get("text"), str) or len(message["text"]) > 2000):
                    raise ValueError("invalid message")
                checked_messages.append({
                    "id": message["id"],
                    "direction": message["direction"],
                    "text": message["text"],
                })
            checked.append({"phone": phone, "name": name, "messages": checked_messages})
        result = {"scanned": scanned, "skipped": skipped, "conversations": checked}
        with self._condition:
            self._results[job_id] = result
            self._condition.notify_all()

    def _wait_for_scan(self, job_id, limit, timeout):
        deadline = time.monotonic() + timeout
        with self._condition:
            while job_id not in self._results:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ExtensionBridgeError(
                        "Não recebemos a análise do Chrome. Confira se a extensão Kiara está instalada "
                        "e se a guia do WhatsApp Web está aberta e atualizada."
                    )
                self._condition.wait(min(remaining, 2))
            result = self._results.pop(job_id)
        result["conversations"] = result["conversations"][:limit]
        return result

    async def wait_for_scan(self, job_id, limit, timeout=180):
        return await asyncio.to_thread(self._wait_for_scan, job_id, limit, timeout)

    def next_command(self):
        """Claim exactly once; expired or claimed sends are never replayed."""
        with self._condition:
            now = time.time()
            for command in self._commands.values():
                if command["expires_at"] > now and not command["claimed"]:
                    command["claimed"] = True
                    return {key: value for key, value in command.items() if key != "claimed"}
        return None

    def accept_command_result(self, payload):
        identifier = payload.get("id")
        with self._condition:
            command = self._commands.get(identifier) if isinstance(identifier, str) else None
            if not command or not command["claimed"] or command["expires_at"] < time.time():
                raise ValueError("unknown or expired command")
            if identifier in self._command_results:
                raise ValueError("command result already received")
            if payload.get("phone") != command["phone"] or type(payload.get("ok")) is not bool:
                raise ValueError("command identity mismatch")
            if payload["ok"] and command["action"] == "read":
                messages = payload.get("messages")
                if not isinstance(messages, list) or len(messages) > 100:
                    raise ValueError("invalid messages")
                for message in messages:
                    if (not isinstance(message, dict) or message.get("direction") not in {"in", "out"}
                            or not isinstance(message.get("id"), str) or not 1 <= len(message["id"]) <= 250
                            or not isinstance(message.get("text"), str) or len(message["text"]) > 10000):
                        raise ValueError("invalid message")
            if (payload["ok"] and command["action"] == "send"
                    and (not isinstance(payload.get("message_id"), str) or not 1 <= len(payload["message_id"]) <= 250)):
                raise ValueError("unconfirmed send")
            # Do not retain arbitrary error bodies, URLs or unexpected response fields.
            self._command_results[identifier] = {
                "ok": payload["ok"], "messages": payload.get("messages", []),
                "message_id": payload.get("message_id"),
            }
            self._condition.notify_all()

    def _execute(self, action, phone, text, expected_ids, timeout):
        if not self.online():
            raise ExtensionBridgeError("A extensão do WhatsApp não está conectada.")
        if action not in {"read", "send"} or not re.fullmatch(r"[1-9][0-9]{7,14}", phone):
            raise ValueError("invalid command")
        if action == "send" and (not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000):
            raise ValueError("invalid send text")
        if (not isinstance(expected_ids, list) or len(expected_ids) > 100
                or any(not isinstance(value, str) or len(value) > 250 for value in expected_ids)):
            raise ValueError("invalid expected IDs")
        identifier = str(uuid4())
        deadline = time.monotonic() + timeout
        with self._condition:
            self._commands[identifier] = {
                "id": identifier, "action": action, "phone": phone, "text": text,
                "expected_ids": expected_ids, "expires_at": time.time() + timeout, "claimed": False,
            }
            self._condition.notify_all()
            try:
                while identifier not in self._command_results:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ExtensionBridgeError("A ação não foi confirmada pelo Chrome; confira a conversa antes de repetir.")
                    self._condition.wait(min(remaining, 1))
                result = self._command_results.pop(identifier)
                if not result["ok"]:
                    raise ExtensionBridgeError("O Chrome bloqueou a ação ou não confirmou o resultado; confira a conversa.")
                return result
            finally:
                self._commands.pop(identifier, None)

    async def execute(self, action, phone, *, text="", expected_ids=None, timeout=60):
        return await asyncio.to_thread(self._execute, action, phone, text, expected_ids or [], timeout)
