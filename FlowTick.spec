# -*- mode: python ; coding: utf-8 -*-

import os

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
FIG_DIR = os.path.join(SPEC_DIR, 'fig')
ICON_PATH = os.path.join(FIG_DIR, 'LOGO.ico')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(FIG_DIR, 'fig')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FlowTick',
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
    icon=ICON_PATH,
    entitlements_file=None,
)
