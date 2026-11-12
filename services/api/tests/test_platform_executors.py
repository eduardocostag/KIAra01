"""Unavailable integrations must never fabricate successful work or artifacts."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from kiara_api.platform.executors.factory import ExecutorFactory
from kiara_api.platform.registry import module_descriptors


@pytest.mark.parametrize("name", ["voice_studio", "open_jarvis", "wan2_1", "money_printer_turbo"])
@pytest.mark.parametrize("metadata", [None, {"configured": True, "output_path": "/tmp/not-real.mp4"}])
async def test_unconnected_executor_never_returns_success_or_fictional_artifact(name, metadata, capsys):
    result = await ExecutorFactory.get_executor(name).execute("private user prompt", metadata)
    assert result.success is False
    assert result.output_path is None
    assert "Configure" in result.message
    output = capsys.readouterr()
    assert "private user prompt" not in output.out + output.err


def test_chat_descriptor_keeps_existing_module_key_and_route():
    descriptor = next(module for module in module_descriptors() if module.key == "atendimento")
    assert descriptor.name == "Kiara Chat"
    assert descriptor.href == "/app/platform/atendimento"
    assert "Conversa" in descriptor.description


def test_intelligence_descriptor_is_retained():
    assert any(module.key == "intelligence" for module in module_descriptors())
