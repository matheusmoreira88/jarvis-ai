# PyInstaller one-folder bundle for Qt WebEngine, audio and credential providers.
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs

hiddenimports = collect_submodules("keyring.backends") + [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "pyttsx3.drivers.sapi5", "win32com.client",
]

a = Analysis(
    ["run_jarvis.py"], pathex=["src"], binaries=collect_dynamic_libs("vosk"), datas=[],
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=[
        "googleapiclient", "httplib2", "google_auth_httplib2",
        "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtPdf",
        "PySide6.QtPdfWidgets", "PySide6.QtQuick3D", "PySide6.Qt3DCore",
        "PySide6.Qt3DRender", "PySide6.Qt3DExtras", "tkinter",
    ], noarchive=False, optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="JarvisAI",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[],
    name="JarvisAI",
)
