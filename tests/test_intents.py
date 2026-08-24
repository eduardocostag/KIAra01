from app.core.intents import IntentRouter


def test_routes_application_without_hardcoding_notepad():
    intent = IntentRouter().route("Kiara, abra o bloco de notas.")
    assert intent.name == "open_application"
    assert intent.parameters == {"application": "bloco de notas"}


def test_routes_powershell_acceptance_phrase():
    intent = IntentRouter().route("Kiara, execute no PowerShell o comando hostname.")
    assert intent.name == "powershell"
    assert intent.parameters == {"command": "hostname"}


def test_routes_url():
    assert IntentRouter().route("abra https://example.com").name == "open_url"


def test_routes_screen_capability_without_triggering_capture():
    assert IntentRouter().route("consegue ver minha tela?").name == "screen_capability"


def test_routes_common_screen_description_variants():
    router = IntentRouter()
    assert router.route("oque esta vendo?").name == "screen_context"
    assert router.route("o que você vê na tela?").name == "screen_context"
    assert router.route("descreva minha tela").name == "screen_context"
