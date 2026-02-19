# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Linux — builds ERPlora Bridge as a single binary.

Usage:
    cd native
    pip install pyinstaller
    pyinstaller build/linux/erplora_bridge.spec
"""

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
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
