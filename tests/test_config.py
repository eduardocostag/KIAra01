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


def test_local_secret_file_loads_only_allowlisted_keys_without_overrides(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "existing")
    (tmp_path / ".env.local").write_text(
        "OPENAI_API_KEY=local-openai\n"
        "GEMINI_API_KEY='local-gemini'\n"
        "OPENROUTER_API_KEY=local-openrouter\n"
        "GROQ_API_KEY=must-not-replace\n"
        "NVIDIA_API_KEY=local-nvidia\n"
        "UNSAFE_VARIABLE=blocked\n",
        encoding="utf-8",
    )

    load_settings(tmp_path / "missing.yaml")

    assert __import__("os").environ["OPENAI_API_KEY"] == "local-openai"
    assert __import__("os").environ["GEMINI_API_KEY"] == "local-gemini"
    assert __import__("os").environ["OPENROUTER_API_KEY"] == "local-openrouter"
    assert __import__("os").environ["GROQ_API_KEY"] == "existing"
    assert __import__("os").environ["NVIDIA_API_KEY"] == "local-nvidia"
    assert "UNSAFE_VARIABLE" not in __import__("os").environ
