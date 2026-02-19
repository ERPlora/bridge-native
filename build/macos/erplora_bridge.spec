# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for macOS — builds ERPlora Bridge as a .app bundle.

Usage:
    cd native
    pip install pyinstaller
    pyinstaller build/macos/erplora_bridge.spec
"""

import sys
import os

block_cipher = None

a = Analysis(
    ['../../erplora_bridge/__main__.py'],
    pathex=['../../'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'websockets',
        'escpos',
        'escpos.printer',
        'usb',
        'usb.core',
        'serial',
        'zeroconf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='erplora-bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window on macOS
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='ERPlora Bridge.app',
    icon=None,  # TODO: Add app icon
    bundle_identifier='com.erplora.bridge',
    info_plist={
        'CFBundleName': 'ERPlora Bridge',
        'CFBundleDisplayName': 'ERPlora Bridge',
        'CFBundleShortVersionString': '0.1.0',
        'LSBackgroundOnly': True,  # Run as background service
        'LSUIElement': True,       # Don't show in Dock
    },
)
