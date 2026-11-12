from __future__ import annotations

import asyncio

import pytest

from app.integrations.maps_scraper import MapsScraperClient
from services.api.kiara_api.maps_scraper import native_maps_search


@pytest.mark.asyncio
async def test_native_hunter_is_opt_in(monkeypatch):
    monkeypatch.delenv("KIARA_MAPS_SCRAPER_EXECUTABLE", raising=False)
    assert await native_maps_search("dentistas Canoas", 10) is None


@pytest.mark.asyncio
async def test_native_hunter_caps_rows_and_preserves_verification_shape(tmp_path, monkeypatch):
    binary = tmp_path / "scraper.exe"
    binary.write_bytes(b"fixture")
    monkeypatch.setenv("KIARA_MAPS_SCRAPER_EXECUTABLE", str(binary))
    calls = []

    async def search(self, **kwargs):
        calls.append(kwargs)
        return [{"name": "Clínica", "maps_url": "https://www.google.com/maps/place/example",
                 "phone": "+55 51 99999-1111", "website": "", "address": "Canoas RS",
                 "category": "Dentista", "rating": 4.9, "review_count": 42}]

    monkeypatch.setattr(MapsScraperClient, "search", search)
    rows = await native_maps_search("dentistas Canoas", 100)
    assert calls == [{"query": "dentistas Canoas", "limit": 50}]
    data = rows[0]["public_data"]
    assert data["detail_inspected"] is True
    assert data["website_status"] == "not_listed"
    assert data["provider"] == "gosom/google-maps-scraper"
    assert not data["whatsapp_url"]
    assert data["user_rating_count"] == 42


@pytest.mark.asyncio
async def test_hunter_cancellation_stops_native_processes(tmp_path, monkeypatch):
    binary = tmp_path / "scraper.exe"
    binary.write_bytes(b"fixture")
    monkeypatch.setenv("KIARA_MAPS_SCRAPER_EXECUTABLE", str(binary))
    switches = []

    async def cancelled(self, **kwargs):
        switches.append(self.kill_switch)
        raise asyncio.CancelledError

    monkeypatch.setattr(MapsScraperClient, "search", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await native_maps_search("dentistas Canoas", 10)
    assert switches[0].stopped


@pytest.mark.asyncio
async def test_hunter_prefers_explicitly_configured_native_provider(monkeypatch):
    from services.api.kiara_api import hunter, maps_scraper

    monkeypatch.setenv("KIARA_MAPS_SCRAPER_EXECUTABLE", "configured.exe")
    expected = [{"source": "google_maps", "title": "fixture",
                 "public_data": {"detail_inspected": True}}]

    async def native(query, limit):
        assert (query, limit) == ("dentistas Canoas", 10)
        return expected

    async def unexpected(*args, **kwargs):
        raise AssertionError("A native result must not create a paid browser session")

    monkeypatch.setattr(maps_scraper, "native_maps_search", native)
    monkeypatch.setattr(hunter, "google_places_search", unexpected)
    monkeypatch.setattr(hunter, "_read_maps_local", unexpected)
    monkeypatch.setattr(hunter, "maps_index_search", unexpected)
    monkeypatch.setattr(hunter, "_read_maps_cdp", unexpected)
    assert await hunter.maps_search("dentistas Canoas", 10) == expected


@pytest.mark.asyncio
async def test_hunter_native_failure_keeps_existing_provider_fallback(monkeypatch):
    from services.api.kiara_api import hunter, maps_scraper

    monkeypatch.setenv("KIARA_MAPS_SCRAPER_EXECUTABLE", "configured.exe")
    expected = [{"source": "google_maps", "title": "fixture"}]

    async def failed(query, limit):
        raise RuntimeError("native unavailable")

    async def places(query, limit):
        return expected

    monkeypatch.setattr(maps_scraper, "native_maps_search", failed)
    monkeypatch.setattr(hunter, "google_places_search", places)
    assert await hunter.maps_search("dentistas Canoas", 1) == expected
