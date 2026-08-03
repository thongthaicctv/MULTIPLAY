# -*- mode: python ; coding: utf-8 -*-

import os


project_dir = os.path.abspath(SPECPATH)
binaries = []

for executable in ("ffmpeg.exe", "ffprobe.exe"):
    executable_path = os.path.join(project_dir, "bin", executable)
    if os.path.isfile(executable_path):
        binaries.append((executable_path, "bin"))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[('icon.ico', '.'), ('antn.png', '.')],
    hiddenimports=['pymysql'],
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
    name='ATG-MultiPlay',
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
    icon=['icon.ico'],
)
