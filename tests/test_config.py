from app.config import load_settings


def test_missing_config_uses_safe_defaults(tmp_path):
    settings = load_settings(tmp_path / "missing.yaml")
    assert settings.get("assistant.name") == "Kiara"
    assert settings.get("autonomy.mode") == "execute_with_confirmation"
    assert settings.get("security.allowlisted_commands") == ["hostname"]


def test_frozen_build_separates_bundled_config_and_writable_data(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    (bundle / "config").mkdir(parents=True)
    (bundle / "config" / "kiara.yaml").write_text(
        "assistant:\n  name: Empacotada\n", encoding="utf-8"
    )
    local = tmp_path / "local"
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys._MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("KIARA_CONFIG", raising=False)
    monkeypatch.delenv("KIARA_DATA_ROOT", raising=False)

    settings = load_settings()

    assert settings.get("assistant.name") == "Empacotada"
    assert settings.root == local / "Kiara"
