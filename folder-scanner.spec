# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for the portable Folder Scanner exe.

Build with the project virtual environment active, from the project root:

    pyinstaller --noconfirm folder-scanner.spec
"""

import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(SPECPATH)

# Bundle the application icon and the loading animation next to the executable.
datas = [
    (os.path.join(ROOT, "assets", "app.ico"), "assets"),
    (os.path.join(ROOT, "assets", "loading-animation.webm"), "assets"),
]

# Collect data / binary modules for the document libraries.
hiddenimports = []
binaries = []
for package in ("docx", "openpyxl", "fitz", "olefile", "xlrd", "rapidfuzz"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        # Some packages may be absent; PyInstaller hooks cover the rest.
        pass

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="folder-scanner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "assets", "app.ico"),
)