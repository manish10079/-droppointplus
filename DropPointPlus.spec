# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for DropPoint+ (onedir, windowed, icons bundled).

Replaces the manual ``pyinstaller ... launcher.py`` CLI invocation so the
build is reproducible on all three OSes in CI:

    pyinstaller --noconfirm DropPointPlus.spec

Produces:
* Windows — ``dist/DropPointPlus/DropPointPlus.exe`` (NSIS wraps this)
* macOS   — ``dist/DropPointPlus/DropPointPlus.app`` (BUNDLE)
* Linux   — ``dist/DropPointPlus/DropPointPlus`` (AppImage wraps this)

Notes:
* ``launcher.py`` is the entry script: it imports the package absolutely, so
  the frozen app never hits ``main.py``'s relative imports (the
  "no known parent package" failure of the first build).
* The resources folder is added as data so ``icons.py`` finds the PNGs/ico
  inside the bundle.
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)  # directory containing this spec file
PKG = ROOT / "droppointplus"
ICON_DIR = PKG / "resources" / "icons"

# Platform icon: .ico on Windows, .icns on macOS (falls back to .png), .png on Linux.
if sys.platform == "win32":
    exe_icon = str(ICON_DIR / "droppoint.ico")
elif sys.platform == "darwin":
    exe_icon = str(ICON_DIR / "pngLogo" / "droppoint.png")
else:
    exe_icon = str(ICON_DIR / "pngLogo" / "droppoint.png")

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(PKG / "resources"), str(Path("droppointplus") / "resources"))],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name="DropPointPlus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # windowed: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DropPointPlus",
)

if sys.platform == "darwin":
    # macOS gets a proper .app bundle (draggable into /Applications).
    app = BUNDLE(
        coll,
        name="DropPointPlus.app",
        icon=str(ICON_DIR / "pngLogo" / "droppoint.png"),
        bundle_identifier="com.droppointplus.app",
        info_plist={
            "CFBundleName": "DropPoint+",
            "CFBundleDisplayName": "DropPoint+",
            "CFBundleShortVersionString": "0.3.0",
            "NSHighResolutionCapable": True,
        },
    )
