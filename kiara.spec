from pathlib import Path

root = Path(SPECPATH)

analysis = Analysis(
    [str(root / "app" / "__main__.py")],
    pathex=[str(root)],
    datas=[
        (str(root / "config"), "config"),
        (str(root / "app" / "ui" / "assets"), "app/ui/assets"),
    ],
    hiddenimports=["app.ui.desktop"],
    excludes=["pytest"],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="Kiara",
    icon=str(root / "app" / "ui" / "assets" / "kiara-app-icon-v3.ico"),
    console=False,
    disable_windowed_traceback=False,
    uac_admin=False,
)
