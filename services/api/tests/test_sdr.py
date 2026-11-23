import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from kiara_api import sdr

ORG = "6f1c2c1e-1111-4222-8333-944444444444"
NOW = datetime.now(UTC)


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def fetchone(self):
        return self.rows[0] if self.rows else None

    async def fetchall(self):
        return self.rows


class FakeDB:
    def __init__(self, config, threads, messages, followups_done=0, outbox=(0, 0), paused=False):
        self.config, self.threads, self.messages, self.followups_done = config, threads, messages, followups_done
        self.outbox, self.paused = outbox, paused  # (failed, total) recent sends; a pause notice in the last hours
        self.requests, self.updates = [], []

    @asynccontextmanager
    async def _transaction(self, organization_id):
        yield self

    async def execute(self, sql, params=()):
        if sql.startswith("SELECT config FROM whatsapp_web_config"):
            return Cursor([{"config": self.config}])
        if "AS last_direction" in sql:
            return Cursor(self.threads)
        if sql.startswith("SELECT direction,body,sent_at FROM messages"):
            return Cursor(self.messages[str(params[1])])
        if sql.startswith("SELECT body FROM messages"):
            inbound = [row for row in self.messages.get(str(params[1]), []) if row["direction"] == "inbound"]
            return Cursor([{"body": inbound[-1]["body"]}] if inbound else [])
        if "kind='notice' AND node_id=%s" in sql:
            return Cursor([{"?": 1}] if self.paused else [])
        if "AS bad" in sql:
            return Cursor([{"bad": self.outbox[0], "total": self.outbox[1]}])
        if sql.startswith("UPDATE action_requests SET status='rejected'"):
            for r in self.requests:
                if r["status"] in {"pending", "approved"} and r["kind"] == "whatsapp.reply":
                    r["status"] = "rejected"
            return Cursor([])
        if "node_id LIKE" in sql:
            return Cursor([{"?": 1}] if any(r["status"] in {"pending", "approved"} and r["node"].endswith(str(params[1]).rsplit(":", 1)[-1]) and r["kind"] == "whatsapp.reply" for r in self.requests) else [])
        if "count(*) AS total" in sql and "node_id=%s" in sql:
            return Cursor([{"total": self.followups_done}])
        if "count(*) AS total" in sql:
            return Cursor([{"total": 0}])
        if sql.lstrip().startswith("INSERT INTO action_requests"):
            _org, node, kind, title, payload, status, _decided = params
            self.requests.append({"id": uuid4(), "node": node, "kind": kind, "title": title, "payload": payload.obj, "status": status})
            return Cursor([])
        if "status='approved' AND (%s OR" in sql:
            inside, limit = params[1], params[2]
            return Cursor([{"id": r["id"], "node_id": r["node"], "payload": r["payload"]} for r in self.requests
                           if r["status"] == "approved" and (inside or r["node"].startswith("sdr:reply:"))][:limit])
        if sql.startswith("UPDATE action_requests SET status"):
            for r in self.requests:
                if r["id"] == params[3]:
                    r["status"] = params[0]
            return Cursor([])
        self.updates.append(sql.split()[0] + " " + sql.split()[1] + " " + sql.split()[2])
        return Cursor([])


class Inbox:
    def __init__(self):
        self.sent = []

    async def reply(self, organization_id, thread_id, payload, *, by_kiara=False):
        self.sent.append((thread_id, payload.text, by_kiara))
        return {"status": "sent"}


class WhatsApp:
    async def sync(self, organization_id):
        return {"messages": 2}

    async def status(self):
        return {"connected": True}


def thread(**changes):
    base = {"id": uuid4(), "consumer_id": uuid4(), "provider_thread_id": "5551988887777", "metadata": {}, "automation_enabled": True,
            "display_name": "Maria Souza", "attributes": {}, "last_direction": "inbound",
            "last_inbound": NOW - timedelta(minutes=5), "last_at": NOW - timedelta(minutes=5)}
    return {**base, **changes}


def config(mode, **changes):
    return {"sdr_mode": mode, "sdr_since": (NOW - timedelta(days=1)).isoformat(), "ai_context": "Clínica de estética em Campinas.",
            "followup_enabled": True, "followup_hours": 24, "contact_start": "00:00", "contact_end": "23:59", "daily_limit": 50,
            "reply_template": "Oi {name}, um atendente já vai continuar com você!", **changes}


def model(reply=None, handoff=False, analysis=None):
    async def ask(conversation):
        if "analista comercial" in conversation[0]["content"]:
            return json.dumps(analysis or {"summary": "Quer preço de limpeza de pele.", "stage": "qualified", "temperature": "hot",
                                           "score": 80, "intent": "Preço", "facts": ["Pediu preço"], "gaps": ["Prazo"],
                                           "next_action": "Enviar valores", "handoff": False, "optout": False, "confidence": 0.8})
        return "Claro! " + json.dumps({"reply": reply or "Oi Maria! A limpeza de pele sai a partir de R$ 150. Para quando você gostaria?", "handoff": handoff})
    return ask


def run(db, ask, whatsapp=WhatsApp(), inbox=None):
    inbox = inbox or Inbox()
    service = sdr.SdrService(db, inbox, whatsapp, ask=ask)
    return asyncio.run(service.tick(ORG)), inbox


def messages_for(t, *rows):
    return {str(t["id"]): [{"direction": d, "body": b, "sent_at": at} for d, b, at in rows]}


def test_pilot_drafts_for_approval_and_sends_nothing():
    t = thread(automation_enabled=False)  # pilot mode works on every conversation, a human approves each message
    db = FakeDB(config("approval"), [t], messages_for(t, ("inbound", "Quanto custa a limpeza de pele?", NOW - timedelta(minutes=5))))
    summary, inbox = run(db, model())
    assert summary["analyzed"] == 1 and summary["drafted"] == 1 and summary["sent"] == 0 and inbox.sent == []
    request = db.requests[0]
    assert request["status"] == "pending" and request["kind"] == "whatsapp.reply" and request["node"] == f"sdr:reply:{t['id']}"
    assert request["payload"]["text"].startswith("Oi Maria!") and request["payload"]["motivo"] == "Resposta ao cliente"
    assert any(item.startswith("INSERT INTO qualifications") for item in db.updates) and "UPDATE pipeline_entries SET" in db.updates


def test_auto_mode_sends_through_the_safe_sender_as_kiara():
    t = thread()
    db = FakeDB(config("auto"), [t], messages_for(t, ("inbound", "Oi, quanto custa?", NOW - timedelta(minutes=5))))
    summary, inbox = run(db, model())
    assert summary["sent"] == 1 and db.requests[0]["status"] == "done"
    assert inbox.sent == [(str(t["id"]), db.requests[0]["payload"]["text"], True)]


def test_auto_mode_skips_conversations_with_the_ai_off():
    t = thread(automation_enabled=False)
    db = FakeDB(config("auto"), [t], messages_for(t, ("inbound", "Oi", NOW - timedelta(minutes=5))))
    summary, inbox = run(db, model())
    assert summary["drafted"] == 0 and inbox.sent == []


def test_handoff_stops_the_ai_and_warns_the_attendant():
    t = thread()
    db = FakeDB(config("approval"), [t], messages_for(t, ("inbound", "Quero fechar, me liga?", NOW - timedelta(minutes=5))))
    summary, _ = run(db, model(analysis={"summary": "Quer fechar.", "stage": "opportunity", "temperature": "hot", "score": 95,
                                         "handoff": True, "handoff_reason": "Quer fechar", "optout": False}))
    assert summary["handoffs"] == 1
    kinds = [(r["kind"], r["status"]) for r in db.requests]
    assert ("notice", "pending") in kinds and ("whatsapp.reply", "pending") in kinds
    assert any(r["payload"].get("text", "").startswith("Oi Maria, um atendente") for r in db.requests)
    assert "UPDATE conversation_threads SET" in db.updates


def test_follow_up_after_silence_then_gives_up_after_two():
    t = thread(last_direction="outbound", last_inbound=NOW - timedelta(hours=40), last_at=NOW - timedelta(hours=30))
    rows = messages_for(t, ("inbound", "Vou pensar", NOW - timedelta(hours=40)), ("outbound", "Combinado!", NOW - timedelta(hours=30)))
    since = (NOW - timedelta(days=3)).isoformat()  # the quiet conversation happened while the SDR was on
    db = FakeDB(config("approval", sdr_since=since), [t], rows)
    summary, _ = run(db, model(reply="Oi Maria, conseguiu pensar sobre a limpeza de pele?"))
    assert summary["followups"] == 1 and db.requests[-1]["payload"]["motivo"] == "Follow-up 1 de 2"
    db = FakeDB(config("approval", sdr_since=since), [t], rows, followups_done=2)
    assert run(db, model())[0]["followups"] == 0


def test_an_explicit_stop_is_obeyed_before_any_ai():
    t = thread()
    db = FakeDB(config("auto"), [t], messages_for(t, ("inbound", "Por favor, não quero mais receber mensagens!", NOW - timedelta(minutes=5))))

    async def never(_conversation):
        raise AssertionError("the model must not run for an opt-out")
    summary, inbox = run(db, never)
    assert summary["optouts"] == 1 and summary["drafted"] == 0 and inbox.sent == []
    assert [(r["kind"], r["node"]) for r in db.requests] == [("notice", f"sdr:optout:{t['id']}")]
    assert "UPDATE consumers SET" in db.updates and "UPDATE conversation_threads SET" in db.updates


def test_first_replies_carry_no_links():
    t = thread()
    db = FakeDB(config("approval"), [t], messages_for(t, ("inbound", "Oi, vi o anúncio", NOW - timedelta(minutes=5))))
    run(db, model(reply="Oi Maria! Veja os valores em https://clinica.com.br/precos e me diga."))
    assert db.requests[0]["payload"]["text"] == "Oi Maria! Veja os valores em e me diga."


def test_failed_sends_pause_the_automation_and_tell_the_owner():
    t = thread()
    rows = messages_for(t, ("inbound", "Quanto custa?", NOW - timedelta(minutes=5)))
    db = FakeDB(config("auto"), [t], rows, outbox=(4, 6))
    summary, inbox = run(db, model())
    assert summary["paused"] is True and inbox.sent == []
    assert any(r["kind"] == "notice" and r["node"] == sdr.PAUSE_NODE for r in db.requests)
    db = FakeDB(config("auto"), [t], rows, paused=True)  # while the pause lasts, nothing leaves
    summary, inbox = run(db, model())
    assert summary["paused"] is True and inbox.sent == [] and not any(r["node"] == sdr.PAUSE_NODE for r in db.requests)
    db = FakeDB(config("auto"), [t], rows, outbox=(2, 40))  # a couple of failures in many sends is normal
    assert run(db, model())[0]["sent"] == 1


def test_number_protection_helpers():
    for text in ("Pare", "PARE!!", "pode parar por favor", "não quero mais receber", "Não me mandem mais nada",
                 "me tira da lista", "Descadastrar", "para de me mandar mensagem", "isso é spam", "vou te denunciar", "STOP"):
        assert sdr.wants_out(text), text
    for text in ("Quanto sai?", "Para quando tem horário?", "Quero cancelar a consulta de amanhã", "não quero agora, obrigado",
                 "Chega amanhã?", "Pode parar o carro na frente?", "Quero remover a tatuagem", "não"):
        assert not sdr.wants_out(text), text
    assert sdr.without_links("Veja www.loja.com e https://x.io/a?b=1 ou loja.com.br/p hoje") == "Veja e ou hoje"
    start = NOW - timedelta(days=1)
    assert sdr.warmup_limit(start, 50, NOW) == 20 and sdr.warmup_limit(NOW - timedelta(days=10), 50, NOW) == 50
    assert sdr.warmup_limit(NOW - timedelta(days=10), 300, NOW) == 80 and sdr.warmup_limit(NOW - timedelta(days=30), 300, NOW) == 300
    assert sdr.warmup_limit(None, 300) == 20


def test_old_history_and_off_mode_are_never_answered():
    t = thread(last_inbound=NOW - timedelta(days=3), last_at=NOW - timedelta(days=3))
    db = FakeDB(config("approval", sdr_since=(NOW - timedelta(hours=1)).isoformat()), [t],
                messages_for(t, ("inbound", "Oi", NOW - timedelta(days=3))))
    assert run(db, model())[0]["drafted"] == 0
    db = FakeDB(config("off"), [thread()], {})
    summary, _ = run(db, model())
    assert summary == {"synced": 2, "analyzed": 0, "drafted": 0, "followups": 0, "handoffs": 0, "sent": 0, "failed": 0, "mode": "off"}


def test_helpers():
    assert sdr.parse_json('Aqui está: ```json\n{"a": 1}\n```') == {"a": 1}
    assert sdr.followup_due({"followup_hours": 24}, 0, NOW - timedelta(hours=25), NOW)
    assert not sdr.followup_due({"followup_hours": 24}, 1, NOW - timedelta(hours=25), NOW)  # 2nd waits 3 days
    assert sdr.in_contact_hours({"contact_start": "09:00", "contact_end": "18:00"}, datetime(2026, 11, 16, 15, 0, tzinfo=UTC))  # 12:00 BRT
    assert not sdr.in_contact_hours({"contact_start": "09:00", "contact_end": "18:00"}, datetime(2026, 11, 16, 23, 0, tzinfo=UTC))


def simulate(ask, *rows, followup=0, **cfg):
    body = sdr.SimulationRequest(name="Maria Souza", followup=followup,
                                 messages=[sdr.SimulatedMessage(direction=d, body=b) for d, b in rows])
    return asyncio.run(sdr.simulate_turn(ask, config("approval", **cfg), body))


def test_simulator_answers_like_the_real_sdr_without_storing_or_sending():
    result = simulate(model(), ("inbound", "Quanto custa a limpeza de pele?"))
    assert result["action"] == "reply" and "R$ 150" in result["reply"]
    assert result["analysis"]["temperature"] == "hot" and result["analysis"]["score"] == 80
    assert result["configured"] is True


def test_simulator_applies_the_number_protections():
    asked = []

    async def never(conversation):
        asked.append(conversation)
        return "{}"
    stop = simulate(never, ("inbound", "Oi"), ("outbound", "Olá!"), ("inbound", "pare de me mandar mensagem"))
    assert stop["action"] == "optout" and not asked  # obeyed before any AI
    link = simulate(model(reply="Veja em www.clinica.com.br e me diga"), ("inbound", "Oi, vi o anúncio"))
    assert "www." not in link["reply"] and any("Link removido" in note for note in link["notes"])
    handoff = simulate(model(handoff=True), ("inbound", "Quero fechar, me liga?"))
    assert handoff["action"] == "handoff" and handoff["reply"] == "Oi Maria, um atendente já vai continuar com você!"


def test_simulator_follow_up_only_after_a_kiara_message():
    result = simulate(model(reply="Oi Maria, conseguiu ver os horários?"), ("inbound", "Oi"), ("outbound", "Olá! Para quando?"), followup=1)
    assert result["action"] == "followup" and "1 de 2" in result["notes"][-1]
    try:
        simulate(model(), ("inbound", "Oi"), followup=1)
        raise AssertionError("follow-up without a Kiara message")
    except sdr.ApiError as error:
        assert error.code == "followup_not_due"
