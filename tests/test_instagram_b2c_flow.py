from __future__ import annotations

from app.consumers import ConsumerStatus, ConsumerStore, InstagramB2CFlow


def _payload(message: str = "Oi, qual o preço do plano?") -> dict:
    return {
        "external_id": "ig-user-42",
        "captured_at": "2026-09-04T09:00:00-03:00",
        "full_name": "Ana",
        "social_handle": "@ana",
        "message": message,
        "campaign_id": "story-setembro",
        "consent": {
            "granted": True,
            "at": "2026-09-04T08:59:00-03:00",
            "source": "instagram_user_initiated_dm",
            "purpose": "responder solicitacao comercial",
            "channels": ["instagram"],
        },
    }


def test_authorized_instagram_inbound_persists_qualifies_and_only_drafts(tmp_path) -> None:
    store = ConsumerStore(tmp_path / "consumers.db")
    calls = []

    def draft_builder(room, message):
        calls.append((room, message))
        return "Rascunho seguro para revisão"

    result = InstagramB2CFlow(store, draft_builder=draft_builder).process(_payload())

    assert result.draft is not None
    assert result.draft.content == "Rascunho seguro para revisão"
    assert result.draft.requires_human_approval is True
    assert result.draft.sent is False
    assert result.room.qualification.status is ConsumerStatus.RESEARCH
    assert [claim.field for claim in result.room.facts] == ["inbound_message"]
    assert result.room.inferences[0].field == "intent"
    assert store.has_active_consent(
        result.person_id,
        channel="instagram",
        purpose="responder solicitacao comercial",
    )
    assert store.touchpoints(result.person_id)[0].direction == "inbound"
    assert calls[0][1] == "Oi, qual o preço do plano?"
    store.close()


def test_opt_out_revokes_consent_and_never_calls_draft_builder(tmp_path) -> None:
    store = ConsumerStore(tmp_path / "consumers.db")

    def forbidden_builder(*_args):
        raise AssertionError("gerador de rascunho não deve ser chamado")

    result = InstagramB2CFlow(store, draft_builder=forbidden_builder).process(
        _payload("Não quero mais mensagens")
    )

    assert result.opted_out is True
    assert result.draft is None
    assert result.room.qualification.status is ConsumerStatus.DISQUALIFIED
    assert not store.has_active_consent(
        result.person_id,
        channel="instagram",
        purpose="responder solicitacao comercial",
    )
    assert store.consents(result.person_id)[0].status == "revoked"
    store.close()


def test_wrong_channel_consent_is_rejected_before_persistence(tmp_path) -> None:
    store = ConsumerStore(tmp_path / "consumers.db")
    payload = _payload()
    payload["consent"]["channels"] = ["email"]

    try:
        InstagramB2CFlow(store).process(payload)
    except ValueError as exc:
        assert "canal Instagram" in str(exc)
    else:
        raise AssertionError("consentimento de outro canal não pode autorizar Instagram")
    assert store.list_people() == []
    store.close()


def test_price_signal_accepts_normal_sentence_punctuation(tmp_path) -> None:
    store = ConsumerStore(tmp_path / "consumers.db")
    assert InstagramB2CFlow(store)._mentions_price("Qual o preço?") is True
