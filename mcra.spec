# mcra.spec — receita do PyInstaller para o MCRA PMJP.
#
# Modo onedir, não onefile: abre mais rápido, porque não extrai o bundle a cada
# execução, e levanta menos suspeita de antivírus corporativo.
#
# Build: pyinstaller mcra.spec --noconfirm

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ("web/dist", "web/dist"),
    ("ref", "ref"),
    ("config/settings.desktop.yaml", "config"),
    ("config/settings.yaml.example", "config"),
    ("config/invites.yaml", "config"),
]
datas += collect_data_files("reportlab")

hiddenimports = collect_submodules("ranking_msc.rules")
hiddenimports += ["app.api.main", "uvicorn.logging", "uvicorn.protocols"]

a = Analysis(
    ["desktop/launcher.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MCRA",
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MCRA",
)
