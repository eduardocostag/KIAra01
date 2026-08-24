from app.security.redaction import redact, redact_text


def test_redacts_secret_values():
    output = redact_text("token=abc123 password: secret")
    assert "abc123" not in output
    assert "secret" not in output


def test_redacts_structured_secret_values():
    output = redact({"token": "abc123", "command": "hostname"})
    assert output == {"token": "[REDACTED]", "command": "hostname"}


def test_redacts_tool_text_and_message_bodies():
    output = redact({"text": "typed-password", "body": "private email", "value": "secret"})
    assert output == {
        "text": "[REDACTED]",
        "body": "[REDACTED]",
        "value": "[REDACTED]",
    }
