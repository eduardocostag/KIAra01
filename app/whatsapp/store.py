from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_CONFIG = {
    "pilot_mode": True, "pilot_consent_confirmed": False, "enabled": False,
    "ai_context": "",
    "reply_template": "Olá! Recebi sua mensagem. Vou encaminhar seu atendimento para a equipe.",
    "followup_template": "Olá! Posso ajudar com alguma dúvida sobre nossa conversa?",
    "followup_hours": 24, "contact_start": "09:00", "contact_end": "18:00", "contacts": [],
    "daily_limit": 50, "auto_reply_enabled": True, "followup_enabled": False,
    "initial_outreach_enabled": False,
    "outreach_template": "Olá {name}! Gostaria de conversar sobre como podemos ajudar sua empresa?",
}


def utcnow():
    return datetime.now(UTC)


def normalize_phone(value):
    phone = re.sub(r"[\s()+.-]", "", str(value))
    if not re.fullmatch(r"[1-9][0-9]{7,14}", phone):
        raise ValueError("Telefone deve incluir país e DDD, com 8 a 15 dígitos.")
    return phone


def validate_config(value):
    config = {**DEFAULT_CONFIG, **value}
    if type(config["pilot_mode"]) is not bool:
        raise ValueError("pilot_mode deve ser booleano")
    for key in ("auto_reply_enabled", "followup_enabled", "initial_outreach_enabled"):
        if type(config[key]) is not bool:
            raise ValueError(f"{key} deve ser booleano")
    if type(config["daily_limit"]) is not int or not 1 <= config["daily_limit"] <= 500:
        raise ValueError("daily_limit deve estar entre 1 e 500")
    if type(config["pilot_consent_confirmed"]) is not bool:
        raise ValueError("pilot_consent_confirmed deve ser booleano")
    if type(config["enabled"]) is not bool:
        raise ValueError("enabled deve ser booleano")
    for key in ("reply_template", "followup_template", "outreach_template"):
        if not isinstance(config[key], str) or not 1 <= len(config[key].strip()) <= 4000:
            raise ValueError(f"{key} deve conter entre 1 e 4000 caracteres")
    if not isinstance(config["ai_context"], str) or len(config["ai_context"]) > 6000:
        raise ValueError("ai_context deve conter no máximo 6000 caracteres")
    hours = config["followup_hours"]
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not 1 <= hours <= 720:
        raise ValueError("followup_hours deve estar entre 1 e 720")
    for key in ("contact_start", "contact_end"):
        if not isinstance(config[key], str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", config[key]):
            raise ValueError("Horário inválido")
    if config["contact_start"] >= config["contact_end"]:
        raise ValueError("Início deve ser anterior ao fim")
    if not isinstance(config["contacts"], list) or len(config["contacts"]) > 500:
        raise ValueError("Lista de contatos inválida")
    contacts = []
    seen = set()
    for item in config["contacts"]:
        phone = normalize_phone(item["phone"])
        if phone in seen:
            raise ValueError("Telefone duplicado")
        seen.add(phone)
        if type(item.get("enabled", False)) is not bool or type(item.get("handoff", False)) is not bool:
            raise ValueError("Estado do contato inválido")
        contacts.append({"phone": phone, "name": str(item.get("name", phone))[:160],
                         "enabled": item.get("enabled", False), "handoff": item.get("handoff", False)})
    enabled_contacts = sum(contact["enabled"] for contact in contacts)
    if config["pilot_mode"] and enabled_contacts > 1:
        raise ValueError("O piloto permite habilitar somente um contato por vez.")
    if config["enabled"] and (enabled_contacts == 0 or (config["pilot_mode"] and enabled_contacts != 1)):
        raise ValueError("Habilite contatos autorizados para iniciar a operação (exatamente um no piloto).")
    if config["enabled"] and not config["pilot_consent_confirmed"]:
        raise ValueError("Confirme que o contato autorizou o teste antes de habilitar a automação.")
    if config["enabled"] and not config["ai_context"].strip():
        raise ValueError("Informe as informações autorizadas da empresa antes de habilitar a automação.")
    config["contacts"] = contacts
    return config


def within_window(config, now):
    # Windows installations can use the tzdata package when OS IANA data is absent.
    local = now.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%H:%M")
    start, end = config["contact_start"], config["contact_end"]
    return start <= local < end if start < end else local >= start or local < end


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS contacts (phone TEXT PRIMARY KEY, baseline INTEGER NOT NULL DEFAULT 0,
          handoff INTEGER NOT NULL DEFAULT 0, optout INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS messages (phone TEXT NOT NULL, dom_id TEXT NOT NULL, direction TEXT NOT NULL,
          text TEXT NOT NULL, occurred_at TEXT NOT NULL, PRIMARY KEY(phone,dom_id));
        CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, phone TEXT NOT NULL, kind TEXT NOT NULL,
          text TEXT NOT NULL, due_at TEXT NOT NULL, status TEXT NOT NULL, source_id TEXT NOT NULL,
          UNIQUE(phone,kind,source_id));
        CREATE TABLE IF NOT EXISTS own_messages (phone TEXT NOT NULL, dom_id TEXT NOT NULL, PRIMARY KEY(phone,dom_id));
        CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, body TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0);
        """)
        # A process crash cannot distinguish a sent click from an unsent click: never retry.
        rows = self.db.execute("SELECT * FROM outbox WHERE status='sending'").fetchall()
        for row in rows:
            self._status(row, "unknown")
            self.db.execute("UPDATE contacts SET handoff=1 WHERE phone=?", (row["phone"],))
        self.db.commit()

    def close(self):
        self.db.close()

    def config(self):
        row = self.db.execute("SELECT body FROM settings WHERE id=1").fetchone()
        return json.loads(row[0]) if row else dict(DEFAULT_CONFIG)

    def configure(self, config):
        config = validate_config(config)
        previous = {contact["phone"]: contact for contact in self.config()["contacts"]}
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (1,?)", (json.dumps(config),))
            for contact in config["contacts"]:
                self.db.execute("INSERT OR IGNORE INTO contacts(phone) VALUES (?)", (contact["phone"],))
                if previous.get(contact["phone"], {}).get("handoff") and not contact["handoff"]:
                    self.db.execute("UPDATE contacts SET handoff=0 WHERE phone=? AND optout=0", (contact["phone"],))
            allowed = {c["phone"] for c in config["contacts"] if c["enabled"] and not c["handoff"]}
            for row in self.db.execute("SELECT * FROM outbox WHERE status='pending'").fetchall():
                if row["phone"] not in allowed:
                    self._status(row, "cancelled")
        return config

    def event(self, phone, kind, text="", status="recorded", now=None, *, external_message_id=None, direction=None):
        event = {"id": str(uuid.uuid4()), "phone": phone, "kind": {"reply": "outbound", "reply_handoff": "outbound", "outreach": "outbound", "outbound_observed": "outbound", "optout": "handoff", "resume": "handoff"}.get(kind, kind), "text": text,
                 "occurred_at": (now or utcnow()).isoformat(), "status": status}
        if external_message_id:
            event.update(external_message_id=external_message_id, conversation_id=phone,
                         direction=direction or ("in" if kind == "inbound" else "out"))
        self.db.execute("INSERT INTO events(id,body) VALUES (?,?)", (event["id"], json.dumps(event)))
        return event

    def contact_allowed(self, phone, config=None):
        config = config or self.config()
        selected = next((c for c in config["contacts"] if c["phone"] == phone), None)
        row = self.db.execute("SELECT * FROM contacts WHERE phone=?", (phone,)).fetchone()
        return bool(config["enabled"] and selected and selected["enabled"] and not selected["handoff"]
                    and row and not row["handoff"] and not row["optout"])

    def pause(self, phone, *, optout=False):
        with self.db:
            self.db.execute("UPDATE contacts SET handoff=1,optout=MAX(optout,?) WHERE phone=?", (int(optout), phone))
            for row in self.db.execute("SELECT * FROM outbox WHERE phone=? AND status='pending'", (phone,)).fetchall():
                self._status(row, "cancelled")
            self.event(phone, "optout" if optout else "handoff", status="paused")

    def resume(self, phone):
        with self.db:
            self.db.execute("UPDATE contacts SET handoff=0 WHERE phone=? AND optout=0", (phone,))
            self.event(phone, "resume", status="recorded")

    def ingest(self, phone, messages, now=None):
        now = now or utcnow()
        row = self.db.execute("SELECT baseline FROM contacts WHERE phone=?", (phone,)).fetchone()
        if not row:
            raise ValueError("Contato não cadastrado")
        baseline = not row[0]
        incoming = []
        # When WhatsApp lazily loads older bubbles or a different window, never treat history as new.
        anchors = [index for index, message in enumerate(messages) if self.db.execute(
            "SELECT 1 FROM messages WHERE phone=? AND dom_id=?", (phone, message.get("id", ""))).fetchone()]
        boundary = max(anchors) if anchors else len(messages) - 1
        with self.db:
            for index, message in enumerate(messages):
                if not message.get("id") or message.get("direction") not in {"in", "out"}:
                    continue
                # DOM snapshots do not expose a trustworthy original sent timestamp.
                # Preserve observed order in UTC without pretending this is delivery time.
                observed_at = now + timedelta(microseconds=index)
                cursor = self.db.execute("INSERT OR IGNORE INTO messages VALUES (?,?,?,?,?)",
                    (phone, message["id"], message["direction"], message.get("text", ""), observed_at.isoformat()))
                if not cursor.rowcount:
                    continue
                historical = baseline or index <= boundary
                self.event(phone, "inbound" if message["direction"] == "in" else "outbound_observed",
                           message.get("text", ""), "historical" if historical else "recorded", now=observed_at,
                           external_message_id=message["id"], direction=message["direction"])
                if historical:
                    continue
                if message["direction"] == "in":
                    incoming.append(message)
                    for pending in self.db.execute("SELECT * FROM outbox WHERE phone=? AND status='pending'", (phone,)).fetchall():
                        self._status(pending, "cancelled")
                elif not self.db.execute("SELECT 1 FROM own_messages WHERE phone=? AND dom_id=?", (phone, message["id"])).fetchone():
                    # A human answered through WhatsApp: stop competing with that operator.
                    self.db.execute("UPDATE contacts SET handoff=1 WHERE phone=?", (phone,))
                    for pending in self.db.execute("SELECT * FROM outbox WHERE phone=? AND status='pending'", (phone,)).fetchall():
                        self._status(pending, "cancelled")
                    self.event(phone, "handoff", "Resposta humana detectada", "paused", now)
            self.db.execute("UPDATE contacts SET baseline=1 WHERE phone=?", (phone,))
        return incoming

    def history(self, phone, limit=12):
        rows = self.db.execute("SELECT direction,text FROM messages WHERE phone=? ORDER BY rowid DESC LIMIT ?", (phone, limit)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def queue(self, phone, kind, text, source_id, due_at):
        identifier = str(uuid.uuid4())
        with self.db:
            inserted = self.db.execute("INSERT OR IGNORE INTO outbox VALUES (?,?,?,?,?,?,?)",
                (identifier, phone, kind, text, due_at.isoformat(), "pending", source_id))
            if inserted.rowcount:
                self.event(phone, kind, text, "pending")
        return identifier

    def due(self, now=None):
        now = now or utcnow()
        config = self.config()
        if not config["enabled"] or not within_window(config, now):
            return []
        return [dict(row) for row in self.db.execute("SELECT * FROM outbox WHERE status='pending' AND due_at<=? ORDER BY due_at", (now.isoformat(),))
                if self.contact_allowed(row["phone"], config)]

    def claim(self, identifier, now=None):
        # Commit before touching browser. A crash afterwards becomes unknown on startup.
        now = now or utcnow()
        row = self.db.execute("SELECT * FROM outbox WHERE id=? AND status='pending'", (identifier,)).fetchone()
        if not row or not self.contact_allowed(row["phone"]) or not within_window(self.config(), now):
            return False
        with self.db:
            cursor = self.db.execute("UPDATE outbox SET status='sending' WHERE id=? AND status='pending'", (identifier,))
        return bool(cursor.rowcount)

    def _status(self, row, status, dom_id=None):
        self.db.execute("UPDATE outbox SET status=? WHERE id=?", (status, row["id"]))
        self.event(row["phone"], row["kind"], row["text"], status,
                   external_message_id=dom_id, direction="out")

    def finish(self, identifier, *, confirmed, now=None, dom_id=None):
        now = now or utcnow()
        row = self.db.execute("SELECT * FROM outbox WHERE id=? AND status='sending'", (identifier,)).fetchone()
        if not row:
            return
        with self.db:
            self._status(row, "sent" if confirmed else "unknown", dom_id=dom_id)
            if confirmed and dom_id:
                self.db.execute("INSERT OR IGNORE INTO own_messages VALUES (?,?)", (row["phone"], dom_id))
            if not confirmed:
                self.db.execute("UPDATE contacts SET handoff=1 WHERE phone=?", (row["phone"],))
        if confirmed and row["kind"] in {"reply", "outreach"} and self.config().get("followup_enabled", False):
            config = self.config()
            self.queue(row["phone"], "followup", config["followup_template"], identifier,
                       now + timedelta(hours=config["followup_hours"]))

    def pending_events(self, limit=100):
        return [json.loads(row[0]) for row in self.db.execute("SELECT body FROM events WHERE synced=0 ORDER BY rowid LIMIT ?", (limit,))]

    def acknowledge_events(self, identifiers):
        with self.db:
            self.db.executemany("UPDATE events SET synced=1 WHERE id=?", [(i,) for i in identifiers])
