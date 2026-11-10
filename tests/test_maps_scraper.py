from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.browser.session import BrowserSession
from app.integrations.maps_scraper import MapsScraperClient, MapsScraperError, validate_search
from app.security.kill_switch import KillSwitch
from app.tools.maps_scraper import GoogleMapsScraperTool


def write_csv(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "title", "link", "phone", "website", "review_rating", "review_count",
        ])
        writer.writeheader()
        for index in (1, 1, 2):
            writer.writerow({
                "title": f"Clínica {index}", "link": f"https://google.com/maps/place/{index}",
                "phone": "51999991111", "website": "",
                "review_rating": "4.8", "review_count": "12",
            })


@pytest.mark.parametrize("query,limit", [("x\ny", 2), ("x\x00y", 2), ("", 2),
                                           ("a" * 301, 1), ("x", True), ("x", 51)])
def test_rejects_multiline_and_invalid_limits(query, limit):
    with pytest.raises(ValueError):
        validate_search(query, limit)


def test_csv_deduplicates_and_does_not_invent_whatsapp(tmp_path):
    output = tmp_path / "results.csv"
    write_csv(output)
    rows = MapsScraperClient.read_results(output, limit=2)
    assert len(rows) == 2
    assert rows[0]["whatsapp"] == ""
    assert rows[0]["website"] == ""
    assert rows[0]["rating"] == 4.8
    assert rows[0]["review_count"] == 12
    assert len(MapsScraperClient.read_results(output, limit=1)) == 1


def test_invalid_website_is_not_reported_as_site_absence(tmp_path):
    output = tmp_path / "results.csv"
    output.write_text(
        'title,link,website,phone\nClínica,https://google.com/maps/place/x,example.test,123\n',
        encoding="utf-8",
    )
    assert MapsScraperClient.read_results(output, limit=1)[0]["website"] == "example.test"


def test_missing_site_column_is_an_incompatible_result(tmp_path):
    output = tmp_path / "results.csv"
    output.write_text('title,link\nClínica,https://google.com/maps/place/x\n', encoding="utf-8")
    with pytest.raises(MapsScraperError, match="incompatível"):
        MapsScraperClient.read_results(output, limit=1)


def client_fixture(tmp_path):
    binary = tmp_path / "scraper.exe"
    binary.write_bytes(b"test fixture; never executed")
    return MapsScraperClient(binary, tmp_path / "output", KillSwitch(), timeout=30)


@pytest.mark.asyncio
async def test_process_uses_fixed_flags_and_registers_kill_switch(tmp_path, monkeypatch):
    monkeypatch.delenv("PLAYWRIGHT_DRIVER_PATH", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    client = client_fixture(tmp_path)
    process = Mock(returncode=0)
    commands = []

    def popen(command, **kwargs):
        commands.append((command, kwargs))
        write_csv(Path(command[command.index("-results") + 1]))
        return process

    monkeypatch.setattr(subprocess, "Popen", popen)
    rows = await client.search(query="dentistas em Canoas; echo bad", limit=1)
    command, kwargs = commands[0]
    assert "-email" not in command
    assert command[command.index("-depth") + 1] == "1"
    assert kwargs["env"]["DISABLE_TELEMETRY"] == "1"
    assert kwargs["env"]["PLAYWRIGHT_DRIVER_PATH"] == str(client.executable.parent / "driver")
    assert kwargs["env"]["PLAYWRIGHT_BROWSERS_PATH"] == str(client.executable.parent / "browsers")
    assert "shell" not in kwargs
    assert "echo bad" not in " ".join(command)
    assert rows[0]["phone"] == "51999991111"
    assert not client.kill_switch._processes


@pytest.mark.asyncio
async def test_timeout_kills_tree_and_preserves_files(tmp_path, monkeypatch):
    client = client_fixture(tmp_path)
    process = Mock(pid=123, returncode=-1)
    process.wait.side_effect = [subprocess.TimeoutExpired("scraper", 30), -1]
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: process)
    kill = Mock()
    monkeypatch.setattr(client.kill_switch, "_kill_tree", kill)
    with pytest.raises(MapsScraperError, match="tempo limite"):
        await client.search(query="dentistas", limit=1)
    kill.assert_called_once_with(123)
    assert len(list(client.output_root.glob("*/queries.txt"))) == 1
    assert not client.kill_switch._processes


@pytest.mark.asyncio
async def test_stopped_switch_does_not_launch_process(tmp_path, monkeypatch):
    client = client_fixture(tmp_path)
    client.kill_switch.trigger()
    popen = Mock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    with pytest.raises(MapsScraperError, match="Kill switch"):
        await client.search(query="dentistas", limit=1)
    popen.assert_not_called()


@pytest.mark.asyncio
async def test_whatsapp_requires_positive_verification(tmp_path, monkeypatch):
    client = client_fixture(tmp_path)
    output = tmp_path / "fixture.csv"
    write_csv(output)

    async def search(**kwargs):
        return client.read_results(output, limit=1)

    monkeypatch.setattr(client, "search", search)
    result = await GoogleMapsScraperTool(client).execute(query="dentistas", limit=1)
    assert result.metadata["businesses"][0]["whatsapp"] == ""

    async def verified(phone):
        return phone == "51999991111"

    result = await GoogleMapsScraperTool(client, verified).execute(query="dentistas", limit=1)
    assert result.metadata["businesses"][0]["whatsapp"] == "51999991111"


@pytest.mark.asyncio
async def test_public_whatsapp_verifier_starts_browser_under_lock(monkeypatch):
    browser = BrowserSession()
    calls = []

    async def start():
        assert browser._lock.locked()
        calls.append("start")

    async def verify(phone):
        assert browser._lock.locked()
        calls.append(phone)
        return True

    monkeypatch.setattr(browser, "start", start)
    monkeypatch.setattr(browser, "_whatsapp_number_is_valid", verify)
    assert await browser.verify_whatsapp_number("51999991111")
    assert calls == ["start", "51999991111"]
