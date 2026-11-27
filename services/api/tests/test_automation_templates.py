"""The ready-made flows the site offers (exported from apps/web/src/lib/automation/catalog.ts into
fixtures/automation_templates.json) run end to end on the server engine: right blocks, right order, the lead
reaching the WhatsApp step with its phone, and the CRM drafts going to the approval center."""
import asyncio
import json
import time
from pathlib import Path

import pytest
from kiara_api.automation import (
    FlowDefinition,
    RunEnv,
    RunState,
    definition_dict,
    describe_lead,
    initial_queue,
    run_flow,
)

TEMPLATES = {item["id"]: item for item in json.loads((Path(__file__).parent / "fixtures" / "automation_templates.json").read_text(encoding="utf-8"))}
LEAD = describe_lead({"display_name": "Pizzaria Bella Napoli", "stage": "new", "next_action": "Enviar a primeira mensagem",
                      "attributes": {"presencial": {"kind": "fachada", "phone": "+5551991234567", "address": "Rua Padre Chagas, 300", "segment": "pizzaria"}}})


class Env:
    def __init__(self, classify="SIM"):
        self.approvals, self.notices, self.drafts_asked, self.prompts = [], [], [], []
        self.classify = classify

    def build(self) -> RunEnv:
        async def ask(prompt):
            self.prompts.append(prompt)
            if "SIM ou NÃO" in prompt:
                return self.classify
            return "Oi! Passei aí em frente e adorei a fachada. Posso te mostrar uma ideia rápida?"

        async def leads(stage, limit):
            return [LEAD, "Clínica Aurora · WhatsApp +5551988887777 · etapa: Em contato"]

        async def latest():
            return LEAD

        async def http_get(url):
            return ""

        async def approval(node, kind, title, payload):
            self.approvals.append((kind, payload))
            return "req-1"

        async def notify(title, text):
            self.notices.append((title, text))

        async def drafts(node, kind, limit):
            self.drafts_asked.append((kind, limit))
            return f"2 mensagem(ns) de {kind} pronta(s) na Central de aprovações: Pizzaria Bella Napoli, Clínica Aurora."

        return RunEnv(ask=ask, leads=leads, latest_lead=latest, http_get=http_get, request_approval=approval, notify=notify, drafts=drafts)


def run(template_id, trigger="manual", value="", classify="SIM"):
    template = TEMPLATES[template_id]
    definition = definition_dict(FlowDefinition.model_validate({"nodes": template["nodes"], "edges": template["edges"]}))
    env = Env(classify)
    state = asyncio.run(run_flow(definition, RunState(pending=initial_queue(definition, trigger, value)), env.build(), deadline=time.monotonic() + 30))
    assert not state.pending
    assert all(step["status"] in {"done", "approval"} for step in state.steps), state.steps
    return env, state


def test_the_site_offers_only_leads_crm_and_message_templates():
    assert set(TEMPLATES) == {"crm-digest", "first-messages", "follow-ups", "reactivation", "lead-welcome", "hot-lead"}
    for template in TEMPLATES.values():
        assert not any(node["type"].startswith(("social.", "ads.", "machine.", "code.", "web.")) for node in template["nodes"])


def test_daily_crm_digest_reads_leads_and_notifies_priorities():
    env, _ = run("crm-digest")
    assert "Pizzaria Bella Napoli" in env.prompts[0] and env.notices[0][0] == "Prioridades de hoje"


@pytest.mark.parametrize(("template", "kind"), [("first-messages", "first_contact"), ("follow-ups", "follow_up"), ("reactivation", "reactivation")])
def test_crm_message_templates_prepare_one_draft_per_lead(template, kind):
    env, _ = run(template, trigger="schedule")
    assert env.drafts_asked and env.drafts_asked[0][0] == kind
    assert "Central de aprovações" in env.notices[0][1]


def test_welcome_flow_writes_for_the_lead_and_sends_to_its_phone():
    env, _ = run("lead-welcome", trigger="lead", value=LEAD)
    assert "Pizzaria Bella Napoli" in env.prompts[-1]  # the message is written about the lead, not about "SIM"
    kind, payload = env.approvals[0]
    assert kind == "whatsapp" and payload["to"] == "51991234567" and payload["text"].startswith("Oi!")
    assert "Bella Napoli" in payload["lead"]


def test_welcome_flow_skips_leads_without_profile():
    env, _ = run("lead-welcome", trigger="lead", value=LEAD, classify="NÃO")
    assert not env.approvals and env.notices[0][0] == "Lead sem perfil para abordagem agora"


def test_hot_lead_alert_and_manual_test_use_the_latest_lead():
    env, _ = run("hot-lead")  # "Executar agora" without a new lead: the most recent lead is used
    assert env.notices[0][0] == "Lead prioritário" and "Pizzaria Bella Napoli" in env.prompts[0]


def test_ai_text_reaches_the_client_without_markdown():
    from kiara_api.automation import plain

    assert plain("## Hoje\nO CRM retornou **\"Nenhum lead\"**. Use `follow-up` e *priorize* a Clínica.\n- item * 2") == \
        "Hoje\nO CRM retornou \"Nenhum lead\". Use follow-up e priorize a Clínica.\n- item * 2"


def test_whatsapp_step_without_any_phone_fails_clearly():
    template = TEMPLATES["lead-welcome"]
    definition = definition_dict(FlowDefinition.model_validate({"nodes": template["nodes"], "edges": template["edges"]}))
    env = Env()
    no_phone = "Contato sem nome · etapa: Novos"
    state = asyncio.run(run_flow(definition, RunState(pending=initial_queue(definition, "lead", no_phone)), env.build(), deadline=time.monotonic() + 30))
    assert any(step["status"] == "error" and "Sem telefone" in step["message"] for step in state.steps) and not env.approvals
