from app.voice.adapters import (
    EdgeNeuralSynthesizer,
    KokoroSynthesizer,
    SapiSynthesizer,
    chunk_text_for_speech,
    normalize_text_for_speech,
)


class FakeToken:
    def __init__(self, description: str, language: str = "") -> None:
        self.description = description
        self.language = language

    def GetDescription(self):
        return self.description

    def GetAttribute(self, name):
        assert name == "Language"
        return self.language


class FakeTokens:
    def __init__(self, *items) -> None:
        self.items = items
        self.Count = len(items)

    def Item(self, index):
        return self.items[index]


def test_normalization_removes_visual_markup_and_preserves_content():
    text = "## Resposta\n- Abra o [site](https://example.com).\n- Use `modo seguro`."
    assert normalize_text_for_speech(text) == "Resposta. Abra o site. Use modo seguro."


def test_chunking_uses_boundaries_and_preserves_every_word():
    text = "Primeira frase curta. Segunda frase um pouco maior, com uma pausa natural. Fim."
    chunks = chunk_text_for_speech(text, max_chars=32)
    assert all(len(chunk) <= 32 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()
    assert all(not chunk.startswith(" ") and not chunk.endswith(" ") for chunk in chunks)


def test_chunking_keeps_unusually_long_token_intact():
    token = "x" * 100
    assert chunk_text_for_speech(token, max_chars=80) == (token,)


def test_sapi_auto_selects_installed_brazilian_portuguese_voice():
    synth = SapiSynthesizer()
    voices = FakeTokens(
        FakeToken("Microsoft David", "409"),
        FakeToken("Microsoft Francisca Natural - Portuguese (Brazil)", "416"),
    )
    assert "Francisca" in synth._select_voice(voices).GetDescription()


def test_explicit_voice_name_overrides_locale_selection():
    synth = SapiSynthesizer(voice_name="David")
    voices = FakeTokens(FakeToken("Microsoft David", "409"), FakeToken("Maria", "416"))
    assert synth._select_voice(voices).GetDescription() == "Microsoft David"


def test_voice_factory_uses_gentle_default_profile(tmp_path):
    from app.bootstrap import build_voice_service
    from app.config import Settings

    service = build_voice_service(Settings({"voice": {"enabled": True}}, tmp_path))
    assert service is not None
    assert isinstance(service.synthesizer, EdgeNeuralSynthesizer)
    assert service.synthesizer.voice == "pt-BR-FranciscaNeural"
    assert service.synthesizer.rate == "+0%"
    assert service.synthesizer.pitch == "+0Hz"
    assert service.synthesizer.language == "pt-BR"
    assert isinstance(service.synthesizer.fallback, KokoroSynthesizer)
    assert service.synthesizer.fallback.voice == "pf_dora"


def test_kokoro_profile_clamps_unsafe_speed_values():
    assert KokoroSynthesizer(speed=0.1).speed == 0.7
    assert KokoroSynthesizer(speed=4).speed == 1.3
