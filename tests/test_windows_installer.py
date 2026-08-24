from pathlib import Path

ROOT = Path(__file__).parents[1]
ISS = (ROOT / "installer" / "kiara.iss").read_text(encoding="utf-8")
BUILD = (ROOT / "scripts" / "build-installer.ps1").read_text(encoding="utf-8")


def test_installer_has_stable_per_user_upgrade_identity() -> None:
    assert "AppId={{6B872A8F-15B5-4C73-BBB8-ECF4D4DA6D55}" in ISS
    assert "DefaultDirName={localappdata}\\Programs\\Kiara" in ISS
    assert "PrivilegesRequired=lowest" in ISS
    assert "ignoreversion" in ISS


def test_shortcuts_and_autostart_are_opt_in_and_uninstalled() -> None:
    assert 'Name: "desktopicon"' in ISS and "Flags: unchecked" in ISS
    assert 'Name: "autostart"' in ISS
    assert 'Name: "{userstartup}\\Kiara"' in ISS
    assert 'Type: files; Name: "{userstartup}\\Kiara.lnk"' in ISS
    assert "Software\\Microsoft\\Windows\\CurrentVersion\\Run" not in ISS


def test_release_pipeline_gates_unsigned_artifacts() -> None:
    assert "Get-AuthenticodeSignature" in BUILD
    assert "-AllowUnsignedDev" in BUILD
    assert "signtool.exe" in BUILD
    assert "/fd SHA256" in BUILD
    assert "/tr $TimestampUrl" in BUILD

