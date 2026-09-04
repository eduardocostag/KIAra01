from __future__ import annotations

import json

from app.feedback import CorrectionInbox


def test_correction_inbox_records_redacted_pending_exchange(tmp_path) -> None:
    inbox = CorrectionInbox(tmp_path / "corrections.jsonl")

    correction_id = inbox.add(
        "Use api_key=segredo-super-secreto",
        "Tente o token: sk-abcdefghijklmnop",
    )

    record = json.loads(inbox.path.read_text(encoding="utf-8"))
    assert record["id"] == correction_id
    assert record["status"] == "pending"
    assert "segredo-super-secreto" not in record["user_message"]
    assert "sk-abcdefghijklmnop" not in record["assistant_response"]
    assert inbox.pending_count() == 1


def test_correction_inbox_ignores_malformed_lines_when_counting(tmp_path) -> None:
    inbox = CorrectionInbox(tmp_path / "corrections.jsonl")
    inbox.path.write_text('{"status":"pending"}\ninválido\n', encoding="utf-8")

    assert inbox.pending_count() == 1
