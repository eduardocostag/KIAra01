import pytest

from scripts import run_whatsapp_local_bridge as bridge


def test_bridge_masks_contact_phone():
    assert bridge.mask_phone("5511999999999@c.us") == "+55*******9999"


def test_bridge_allows_only_explicit_secure_origins(monkeypatch):
    monkeypatch.setenv(
        "KIARA_WHATSAPP_ALLOWED_ORIGINS",
        "https://kiaralead.vercel.app,http://localhost:3000,http://example.com",
    )
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "public-key")

    assert bridge.configured_origins() == frozenset({
        "https://kiaralead.vercel.app",
        "http://localhost:3000",
    })


def test_bridge_requires_a_valid_site_origin(monkeypatch):
    monkeypatch.setenv("KIARA_WHATSAPP_ALLOWED_ORIGINS", "http://example.com")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "public-key")

    with pytest.raises(RuntimeError, match="KIARA_WHATSAPP_ALLOWED_ORIGINS"):
        bridge.configured_origins()


def test_bridge_requires_one_valid_configured_phone(monkeypatch):
    monkeypatch.setenv("KIARA_WHATSAPP_ANALYSIS_PHONE", "+55 (11) 99999-9999")
    assert bridge._configured_phone() == "5511999999999@c.us"

    monkeypatch.setenv("KIARA_WHATSAPP_ANALYSIS_PHONE", "5511999999999@lid")
    with pytest.raises(ValueError):
        bridge._configured_phone()


def test_bridge_exposes_only_read_operations():
    handler = bridge.handler_for(object())
    assert hasattr(handler, "do_POST")
    assert hasattr(handler, "do_OPTIONS")
    assert not hasattr(handler, "do_GET")
    assert not hasattr(handler, "do_PUT")
    assert not hasattr(handler, "do_DELETE")
