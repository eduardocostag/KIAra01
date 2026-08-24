from app.security.audit import AuditLog


def test_audit_timeline_is_bounded_redacted_and_exportable(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    audit.record(tool="one", token="super-secret")
    audit.record(tool="two")
    assert [item["tool"] for item in audit.read(limit=1)] == ["two"]
    assert audit.read(limit=2)[1]["token"] == "[REDACTED]"
    destination = tmp_path / "export" / "audit.jsonl"
    assert audit.export(destination) == 2
    assert "super-secret" not in destination.read_text(encoding="utf-8")
