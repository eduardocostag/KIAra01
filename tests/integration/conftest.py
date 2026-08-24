from __future__ import annotations

import platform

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    skip = pytest.mark.skip(reason="requires Windows")
    for item in items:
        if "windows_integration" in item.keywords and platform.system() != "Windows":
            item.add_marker(skip)
