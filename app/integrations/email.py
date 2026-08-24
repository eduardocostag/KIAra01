from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.integrations.credentials import CredentialProvider
from app.integrations.http import JsonHttpClient


@dataclass(frozen=True, slots=True)
class DraftEmail:
    to: str
    subject: str
    body: str
    id: str = ""

    def with_id(self) -> DraftEmail:
        return self if self.id else DraftEmail(self.to, self.subject, self.body, str(uuid.uuid4()))


class EmailProvider(Protocol):
    async def send(self, draft: DraftEmail) -> str: ...


class MailboxProvider(EmailProvider, Protocol):
    async def read(self, limit: int = 20) -> list[dict[str, object]]: ...


class DraftStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS email_drafts(id TEXT PRIMARY KEY, recipient TEXT, subject TEXT, body TEXT, sent_id TEXT)")
        self._db.commit()

    def save(self, draft: DraftEmail) -> DraftEmail:
        draft = draft.with_id()
        self._db.execute("INSERT OR REPLACE INTO email_drafts(id,recipient,subject,body,sent_id) VALUES (?,?,?,?,NULL)", (draft.id, draft.to, draft.subject, draft.body))
        self._db.commit()
        return draft

    def get(self, identifier: str) -> DraftEmail | None:
        row = self._db.execute("SELECT id,recipient,subject,body FROM email_drafts WHERE id=? AND sent_id IS NULL", (identifier,)).fetchone()
        return DraftEmail(row[1], row[2], row[3], row[0]) if row else None

    def mark_sent(self, identifier: str, provider_id: str) -> None:
        self._db.execute("UPDATE email_drafts SET sent_id=? WHERE id=?", (provider_id, identifier))
        self._db.commit()

    def close(self) -> None:
        self._db.close()


class EmailService:
    def __init__(self, store: DraftStore, provider: EmailProvider | None = None) -> None:
        self.store, self.provider = store, provider

    def draft(self, to: str, subject: str, body: str) -> DraftEmail:
        if "@" not in to or len(to) > 320 or not subject.strip() or not body.strip():
            raise ValueError("Destinatário, assunto ou corpo inválido.")
        return self.store.save(DraftEmail(to.strip(), subject.strip()[:300], body.strip()))

    async def send(self, identifier: str) -> str:
        draft = self.store.get(identifier)
        if draft is None:
            raise ValueError("Rascunho inexistente ou já enviado.")
        if self.provider is None:
            raise RuntimeError("Provider de e-mail não configurado.")
        provider_id = await self.provider.send(draft)
        self.store.mark_sent(identifier, provider_id)
        return provider_id


class MicrosoftGraphEmailProvider:
    def __init__(self, access_token: str, *, timeout_seconds: float = 20) -> None:
        if not access_token:
            raise ValueError("Token do Microsoft Graph ausente.")
        self._token, self._timeout = access_token, timeout_seconds

    async def send(self, draft: DraftEmail) -> str:
        return await asyncio.to_thread(self._send_sync, draft)

    def _send_sync(self, draft: DraftEmail) -> str:
        payload = {"message": {"subject": draft.subject, "body": {"contentType": "Text", "content": draft.body}, "toRecipients": [{"emailAddress": {"address": draft.to}}]}, "saveToSentItems": True}
        request = urllib.request.Request(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            data=json.dumps(payload).encode(), method="POST",
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                if response.status != 202:
                    raise RuntimeError(f"Microsoft Graph retornou HTTP {response.status}.")
        except urllib.error.URLError as exc:
            raise RuntimeError("Falha ao enviar pelo Microsoft Graph.") from exc
        return f"graph:{draft.id}"


class CredentialGraphEmailProvider:
    def __init__(self, credentials: CredentialProvider, client: JsonHttpClient | None = None) -> None:
        self.credentials, self.client = credentials, client or JsonHttpClient()

    def _token(self) -> str:
        token = self.credentials.get("KIARA_GRAPH_TOKEN")
        if not token:
            raise RuntimeError("Credencial Microsoft Graph não configurada.")
        return token

    async def send(self, draft: DraftEmail) -> str:
        payload = {"message": {"subject": draft.subject, "body": {"contentType": "Text", "content": draft.body}, "toRecipients": [{"emailAddress": {"address": draft.to}}]}, "saveToSentItems": True}
        await self.client.request("POST", "https://graph.microsoft.com/v1.0/me/sendMail", token=self._token(), payload=payload, idempotency_key=draft.id)
        return f"graph:{draft.id}"

    async def read(self, limit: int = 20) -> list[dict[str, object]]:
        response = await self.client.request("GET", f"https://graph.microsoft.com/v1.0/me/messages?$top={min(max(limit, 1), 50)}&$select=id,subject,from,receivedDateTime", token=self._token())
        return list(response.body.get("value", []))


class GmailEmailProvider:
    def __init__(self, credentials: CredentialProvider, client: JsonHttpClient | None = None) -> None:
        self.credentials, self.client = credentials, client or JsonHttpClient()

    def _token(self) -> str:
        token = self.credentials.get("KIARA_GMAIL_TOKEN")
        if not token:
            raise RuntimeError("Credencial Gmail não configurada.")
        return token

    async def send(self, draft: DraftEmail) -> str:
        mime = f"To: {draft.to}\r\nSubject: {draft.subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{draft.body}"
        raw = base64.urlsafe_b64encode(mime.encode()).decode().rstrip("=")
        response = await self.client.request("POST", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send", token=self._token(), payload={"raw": raw}, idempotency_key=draft.id)
        return str(response.body.get("id", f"gmail:{draft.id}"))

    async def read(self, limit: int = 20) -> list[dict[str, object]]:
        response = await self.client.request("GET", f"https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={min(max(limit, 1), 50)}", token=self._token())
        return list(response.body.get("messages", []))
