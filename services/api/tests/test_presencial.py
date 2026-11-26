import asyncio
import base64
import json
from datetime import UTC, datetime

import pytest
from kiara_api.http.context import RequestContext
from kiara_api.http.errors import ApiError
from kiara_api.outreach_ai import draft_prompt, lead_facts
from kiara_api.presencial import (
    ContactIn,
    Photo,
    PresencialService,
    ReadRequest,
    company_site,
    contact_key,
    enrich,
    parse_card,
    presencial_attributes,
)
from kiara_api.sdr import HUNTED, contact_origin, contact_profile

JPEG = base64.b64encode(b"\xff\xd8\xff" + b"0" * 200).decode()
CONTEXT = RequestContext(user_id="u1", organization_id="org-1", membership_id="m1", role="operator", correlation_id="c1")


def card_json(**extra):
    data = {"name": "Ana Souza", "role": "Diretora Comercial", "company": "Pulso Marketing", "phones": ["(51) 3333-4444", "+55 51 99876-5432"],
            "emails": ["ana@pulso.com.br"], "website": "", "instagram": "@agenciapulso", "city": "Porto Alegre", "cnpj": "", "kind": "cartao",
            "readable": True}
    data.update(extra)
    return "Aqui está: " + json.dumps(data)


def test_card_is_cleaned_with_mobile_first_and_site_from_corporate_email():
    card = parse_card(card_json())
    assert card["phones"] == ["51998765432", "5133334444"]  # WhatsApp-capable number first, without +55
    assert card["instagram"] == "agenciapulso"
    assert company_site(card) == "https://pulso.com.br"
    assert company_site(parse_card(card_json(emails=["ana.souza@gmail.com"]))) is None  # never a free-mail domain


def test_unreadable_or_invented_output_is_rejected():
    assert parse_card("não consegui ler")["readable"] is False
    assert parse_card(card_json(readable=False))["readable"] is False
    assert parse_card(card_json(emails=["não tem"], phones=["123"]))["emails"] == []


def test_enrich_uses_the_site_cnpj_and_registry_partners():
    site = "Pulso Marketing LTDA - CNPJ 11.222.333/0001-81 - Proprietária: Ana Souza"
    company = {"cnpj": "11222333000181", "trade_name": "Pulso", "partners": [{"name": "ANA SOUZA", "role": "Sócio-Administrador"}]}
    result = asyncio.run(enrich(parse_card(card_json()), site_fetcher=lambda url: site, lookup=lambda cnpj: company))
    assert result["site_read"] and result["cnpj"] == "11222333000181"
    assert result["decision_maker"]["source"] == "receita"


def test_read_returns_a_preview_and_saves_nothing():
    async def vision(image, prompt=""):
        assert image.startswith("data:image/jpeg;base64,")
        return card_json()

    async def no_enrich(card):
        return {"website": "https://pulso.com.br", "site_read": False, "cnpj": "", "company": None, "decision_maker": None}

    service = PresencialService(None, vision=vision, enricher=no_enrich)
    preview = asyncio.run(service.read(CONTEXT, ReadRequest(photo=Photo(mime="image/jpeg", data_base64=JPEG))))
    assert preview["contact"]["phone"] == "51998765432" and preview["contact"]["phone_kind"] == "celular"
    assert preview["contact"]["other_phones"] == ["5133334444"]


def test_read_refuses_fake_images_and_unreadable_cards():
    async def vision(image, prompt=""):
        return "{}"

    service = PresencialService(None, vision=vision, enricher=enrich)
    png_bytes_as_jpeg = Photo(mime="image/jpeg", data_base64=base64.b64encode(b"\x89PNG" + b"0" * 200).decode())
    with pytest.raises(ApiError):
        asyncio.run(service.read(CONTEXT, ReadRequest(photo=png_bytes_as_jpeg)))
    with pytest.raises(ApiError) as error:
        asyncio.run(service.read(CONTEXT, ReadRequest(photo=Photo(mime="image/jpeg", data_base64=JPEG))))
    assert error.value.code == "card_unreadable"


def test_save_needs_a_name_and_a_channel_and_a_writer_role():
    service = PresencialService(None)
    with pytest.raises(ApiError):
        asyncio.run(service.save(CONTEXT, ContactIn(phone="51998765432")))
    with pytest.raises(ApiError):
        asyncio.run(service.save(CONTEXT, ContactIn(name="Ana")))
    viewer = RequestContext(user_id="u2", organization_id="org-1", membership_id="m2", role="viewer", correlation_id="c2")
    with pytest.raises(ApiError):
        asyncio.run(service.save(viewer, ContactIn(name="Ana", phone="51998765432")))


def test_same_person_gets_the_same_key_and_the_meeting_is_recorded():
    body = ContactIn(name="Ana Souza", company="Pulso", phone="(51) 99876-5432", event="Expo Sul", note="Quer 3 unidades até março")
    assert contact_key(body) == contact_key(ContactIn(name="Ana", phone="+55 51 99876-5432")) == "phone:51998765432"
    met = presencial_attributes(body, user_id="u1", company=None, now=datetime(2026, 11, 26, tzinfo=UTC))
    assert met["phone"] == "+5551998765432" and met["phone_kind"] == "celular" and met["event"] == "Expo Sul"


def test_first_message_and_sdr_know_where_they_met():
    attributes = {"presencial": {"contact_name": "Ana Souza", "role": "Diretora", "company": "Pulso", "event": "Expo Sul",
                                 "met_at": "2026-11-26T10:00:00+00:00", "note": "Quer 3 unidades até março"}}
    facts = lead_facts("Ana Souza · Pulso", attributes)
    assert any("Expo Sul (26/11)" in fact for fact in facts) and any("3 unidades" in fact for fact in facts)
    prompt = draft_prompt("first_contact", {}, "", facts, [], "", met=True)
    assert "conhecer essa pessoa pessoalmente" in prompt[1]["content"]
    assert contact_origin(attributes) == HUNTED
    assert any("Conhecido pessoalmente em Expo Sul" in line for line in contact_profile(attributes))


# ---------------------------------------------------------------- storefront mode

def place_json(**extra):
    data = {"business": "Pizzaria Bella Napoli", "segment": "pizzaria", "phones": ["(51) 3222-1100"], "instagram": "@bellanapolipoa",
            "website": "", "address_text": "", "details": "fachada simples, delivery", "readable": True}
    data.update(extra)
    return json.dumps(data)


MAPS_ROWS = [
    {"title": "Bella Napoli Pizzaria", "url": "https://www.google.com/maps/place/?q=place_id:abc",
     "public_data": {"phone": "(51) 99123-4567", "address": "Rua Padre Chagas, 300 - Moinhos de Vento, Porto Alegre",
                     "rating": 4.7, "user_rating_count": 312, "website_status": "not_listed"}},
    {"title": "Pizza Hut", "url": "https://www.google.com/maps/place/?q=place_id:xyz",
     "public_data": {"phone": "(51) 3000-0000", "address": "Av. Ipiranga, 1000, Porto Alegre"}},
]


def test_storefront_photo_finds_the_business_on_maps_and_scores_it():
    from kiara_api.presencial import Location

    queries = []

    async def vision(image, prompt=""):
        assert "fachadas" in prompt
        return place_json()

    async def geocode(lat, lng):
        return {"road": "Rua Padre Chagas", "number": "300", "suburb": "Moinhos de Vento", "city": "Porto Alegre", "state": "RS"}

    async def maps(query, limit):
        queries.append(query)
        return MAPS_ROWS

    async def no_enrich(card):
        return {"website": "", "site_read": False, "cnpj": "", "company": None, "decision_maker": None}

    service = PresencialService(None, vision=vision, enricher=no_enrich, geocode=geocode, maps=maps)
    body = ReadRequest(photo=Photo(mime="image/jpeg", data_base64=JPEG), mode="place", location=Location(lat=-30.02, lng=-51.2))
    preview = asyncio.run(service.read(CONTEXT, body))
    assert queries == ["Pizzaria Bella Napoli, Rua Padre Chagas, Porto Alegre, RS"]
    assert preview["kind"] == "fachada" and preview["place"]["found_on_maps"] and preview["place"]["rating"] == 4.7
    assert preview["contact"]["company"] == "Bella Napoli Pizzaria"
    assert preview["contact"]["phone"] == "51991234567"  # the mobile from Maps comes before the landline on the sign
    assert preview["fit"]["grade"] in {"A", "B"} and any("Sem site" in reason["text"] for reason in preview["fit"]["reasons"])


def test_storefront_never_takes_a_different_business():
    from kiara_api.presencial_place import best_match

    assert best_match(MAPS_ROWS, "Sorveteria Gelato", [], "Rua Padre Chagas") is None
    assert best_match(MAPS_ROWS, "Qualquer", ["5130000000"], "")["title"] == "Pizza Hut"  # same phone = same business


def test_storefront_draft_says_they_passed_by():
    attributes = {"presencial": {"kind": "fachada", "company": "Bella Napoli", "segment": "pizzaria", "address": "Rua Padre Chagas, 300",
                                 "rating": 4.7, "user_rating_count": 312, "website_status": "not_listed"}}
    facts = lead_facts("Bella Napoli", attributes)
    assert any("passou pessoalmente em frente" in fact for fact in facts) and any("Não tem site" in fact for fact in facts)
    prompt = draft_prompt("first_contact", {}, "", facts, [], "", met="fachada")
    assert "viu pessoalmente" in prompt[1]["content"]
    assert any("passou em frente" in line for line in contact_profile(attributes))
