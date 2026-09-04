"""End-to-end, approval-gated Instagram pilot orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.automation.instagram_governance import GovernedDM, InstagramDMGovernance
from app.integrations.instagram import (
    InstagramContractError,
    InstagramMessage,
    InstagramMessagingClient,
    parse_message_events,
    verify_webhook_signature,
)

from .instagram_flow import InstagramB2CFlow, InstagramFlowResult


@dataclass(frozen=True, slots=True)
class InstagramPilotItem:
    event_id: str
    action_id: str | None
    result: InstagramFlowResult | None
    outcome: str


class InstagramPilotService:
    """Connect authenticated inbound DMs to governed, human-approved delivery."""

    def __init__(
        self,
        *,
        app_secret: str,
        flow: InstagramB2CFlow,
        governance: InstagramDMGovernance,
        messaging: InstagramMessagingClient,
    ) -> None:
        if not app_secret:
            raise ValueError("App secret do Instagram é obrigatório.")
        self._app_secret = app_secret
        self._flow = flow
        self._governance = governance
        self._messaging = messaging
        # Recipient IDs are kept out of the governance/audit database. A process
        # restart therefore fails closed and requires the inbound event to be reconciled.
        self._recipient_by_action: dict[str, str] = {}

    def receive(self, raw_body: bytes, signature: str | None) -> tuple[InstagramPilotItem, ...]:
        verify_webhook_signature(raw_body, signature, self._app_secret)
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InstagramContractError("Webhook do Instagram contém JSON inválido.") from exc
        if not isinstance(payload, dict):
            raise TypeError("Webhook do Instagram deve ser um objeto JSON.")
        return tuple(self._receive_message(message) for message in parse_message_events(payload))

    def _receive_message(self, message: InstagramMessage) -> InstagramPilotItem:
        if (
            message.instagram_account_id != self._messaging.account_id
            or message.recipient_id != self._messaging.account_id
            or message.sender_id == self._messaging.account_id
        ):
            return InstagramPilotItem(message.message_id, None, None, "wrong_account")
        if message.is_echo or not message.text:
            return InstagramPilotItem(message.message_id, None, None, "ignored")
        # Meta message IDs are scoped to the receiving Instagram account.
        event_id = f"{message.instagram_account_id}:{message.message_id}"
        existing = self._governance.action_for_event(event_id)
        if existing is not None:
            self._recipient_by_action.setdefault(existing.id, message.sender_id)
            return InstagramPilotItem(event_id, existing.id, None, "duplicate")
        outcome = self._governance.ingest(event_id, message.sender_id, message.text)
        if outcome == "opt_out":
            return InstagramPilotItem(event_id, None, None, outcome)

        captured_at = datetime.fromtimestamp(message.timestamp_ms / 1000, UTC)
        result = self._flow.process({
            "external_id": message.sender_id,
            "captured_at": captured_at.isoformat(),
            "full_name": "Contato do Instagram",
            "social_handle": message.sender_id,
            "message": message.text,
            "consent": {
                "granted": True,
                "at": captured_at.isoformat(),
                "source": "instagram_inbound_dm",
                "purpose": "responder_solicitacao_recebida",
                "channels": ["instagram"],
            },
        })
        if result.draft is None:
            return InstagramPilotItem(event_id, None, result, "blocked")
        action_id = self._governance.create_draft(
            event_id, result.draft.content, actor="kiara"
        )
        self._recipient_by_action[action_id] = message.sender_id
        return InstagramPilotItem(event_id, action_id, result, "pending_approval")

    async def approve_and_send(self, action_id: str, *, actor: str) -> str:
        approved_now = self._governance.approve(action_id, actor=actor)
        current = self._governance.get(action_id)
        if not approved_now and (current is None or current.status not in ("approved", "retry_wait")):
            return "not_approved"
        claimed = self._governance.claim_delivery(action_id)
        if claimed is None:
            return "blocked"
        recipient_id = self._recipient_by_action.get(action_id)
        if recipient_id is None:
            self._governance.finish_delivery(action_id, success=False, retryable=False)
            return "recipient_unavailable"
        return await self._deliver(action_id, claimed, recipient_id)

    async def _deliver(self, action_id: str, claimed: GovernedDM, recipient_id: str) -> str:
        try:
            message_id = await self._messaging.send_text(recipient_id, claimed.draft)
        except Exception as exc:
            retryable = bool(getattr(exc, "retryable", False))
            self._governance.finish_delivery(action_id, success=False, retryable=retryable)
            raise
        self._governance.finish_delivery(action_id, success=True)
        self._recipient_by_action.pop(action_id, None)
        return message_id
