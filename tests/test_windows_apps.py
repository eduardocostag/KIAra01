from __future__ import annotations

import pytest

from app.tools.windows import NetworkPingTool, OpenApplicationTool


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application", "expected"),
    (
        ("cmd", ["cmd.exe"]),
        ("powershell", ["powershell.exe"]),
        ("lixeira", ["explorer.exe", "shell:RecycleBinFolder"]),
        ("pasta de downloads", ["explorer.exe", "shell:Downloads"]),
        ("gerenciador de dispositivos", ["mmc.exe", "devmgmt.msc"]),
    ),
)
async def test_known_windows_targets_use_safe_argument_lists(
    monkeypatch, application: str, expected: list[str]
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("app.tools.windows.subprocess.Popen", lambda command: calls.append(command))

    result = await OpenApplicationTool().execute(application=application)

    assert result.success is True
    assert calls == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application", "target"),
    (("teams", "msteams:"), ("obsidian", "obsidian://open")),
)
async def test_protocol_apps_use_windows_shell(monkeypatch, application: str, target: str) -> None:
    activated: list[str] = []
    monkeypatch.setattr("app.tools.windows.os.startfile", activated.append)
    if application == "obsidian":
        monkeypatch.setattr(OpenApplicationTool, "_common_executable", lambda *args, **kwargs: None)

    result = await OpenApplicationTool().execute(application=application)

    assert result.success is True
    assert activated == [target]


@pytest.mark.asyncio
async def test_start_menu_shortcut_uses_shell_instead_of_popen(monkeypatch) -> None:
    activated: list[str] = []
    monkeypatch.setattr("app.tools.windows.os.startfile", activated.append)
    monkeypatch.setattr(OpenApplicationTool, "_common_executable", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        OpenApplicationTool,
        "_start_menu_shortcut",
        lambda *_args: r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\AnyDesk.lnk",
    )

    result = await OpenApplicationTool().execute(application="anydesk")

    assert result.success is True
    assert activated == [r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\AnyDesk.lnk"]


def test_shortcut_canonicalization_accepts_desktop_suffix_without_fuzzy_guessing() -> None:
    assert OpenApplicationTool._canonical_name("Notion Desktop") == "notion"
    assert OpenApplicationTool._canonical_name("Aplicativo diferente") == "aplicativo diferente"


def test_path_resolution_rejects_commands_with_shell_characters(monkeypatch) -> None:
    monkeypatch.setattr("app.tools.windows.shutil.which", lambda _name: "unexpected.exe")

    assert OpenApplicationTool._path_executable("calc & hostname") is None


@pytest.mark.asyncio
async def test_network_ping_uses_argument_list_without_shell(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "app.tools.windows.shutil.which",
        lambda name: r"C:\Windows\System32\cmd.exe"
        if name.startswith("cmd")
        else r"C:\Windows\System32\PING.EXE",
    )
    monkeypatch.setattr("app.tools.windows.subprocess.Popen", lambda args: calls.append(args))

    result = await NetworkPingTool().execute(target="8.8.8.8", resolve_name=True)

    assert result.success is True
    assert calls == [
        [
            r"C:\Windows\System32\cmd.exe",
            "/k",
            r"C:\Windows\System32\PING.EXE",
            "-a",
            "8.8.8.8",
        ]
    ]


@pytest.mark.parametrize("target", ("8.8.8.8 & whoami", "-n 999 localhost", "bad..host"))
def test_network_ping_rejects_shell_or_invalid_targets(target: str) -> None:
    with pytest.raises(ValueError, match="inválido"):
        NetworkPingTool().validate({"target": target})
