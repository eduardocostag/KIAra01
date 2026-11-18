"""Kiara's spoken text: the words and formats Francisca mispronounces are rewritten; the rest stays untouched."""
from app.voice.kiara_style import spoken


def test_loanwords_that_failed_the_listening_test_are_respelled_in_any_case():
    assert spoken("Faça um Follow-up e poste nos Stories e Reels.") == "Faça um fólou ápi e poste nos stóris e vídeos curtos."
    assert spoken("Tive um insight.") == "Tive um ínsaiti."


def test_loanwords_the_voice_already_says_well_are_kept():
    text = "Mais leads pelo WhatsApp, online, com feedback no app e no site."
    assert spoken(text) == text


def test_acronyms_are_case_sensitive_so_the_verb_ia_is_kept():
    assert spoken("Ela ia sair. A IA ajuda no CRM.") == "Ela ia sair. A I A ajuda no cê érre ême."


def test_times_multipliers_rates_and_symbols_are_written_as_spoken():
    assert spoken("Às 14h30, 9:00 ou 13h05.") == "Às 14 horas e 30, 9 horas ou 13 horas e 5."
    assert spoken("Temos 3x mais clientes 😊.") == "Temos 3 vezes mais clientes."
    assert spoken("Custa R$ 99/mês ou R$ 10/dia.") == "Custa R$ 99 por mês ou R$ 10 por dia."
    assert spoken("Use e-mail/WhatsApp, etc.") == "Use e-mail ou WhatsApp, etcétera."
    assert spoken("De A -> B, ~20 pessoas, 3 x 4 = 12") == "De A, B, cerca de 20 pessoas, 3 vezes 4 é igual a 12"


def test_dates_and_money_are_left_to_the_voice():
    # Francisca already reads these correctly ("18 de novembro de 2026", "mil e quinhentos reais").
    assert spoken("Prazo 18/11/2026, custa R$ 1.500,00.") == "Prazo 18/11/2026, custa R$ 1.500,00."
