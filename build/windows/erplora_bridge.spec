# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Windows — builds ERPlora Bridge as a single .exe.

Usage:
    cd native
    pip install pyinstaller
    pyinstaller build/windows/erplora_bridge.spec
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
    console=False,  # No console window
    disable_windowed_traceback=False,
    icon=None,  # TODO: Add .ico file
    version_info={
        'CompanyName': 'ERPlora',
        'FileDescription': 'ERPlora Hardware Bridge',
        'FileVersion': '0.1.0',
        'ProductName': 'ERPlora Bridge',
        'ProductVersion': '0.1.0',
    } if False else None,  # version_info needs a .txt file, skip for now
)
