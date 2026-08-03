# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    # Khi phát hành kèm FFmpeg, bỏ comment hai dòng dưới và bảo đảm file tồn tại:
    # binaries=[('bin/ffmpeg.exe', 'bin'), ('bin/ffprobe.exe', 'bin')],
    binaries=[],
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
    name='MultiPlay',
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
