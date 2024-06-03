# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['QuantiFish.py'],
    pathex=[],
    binaries=[],
    datas=[('resources', 'resources')],
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
    name='quantifish',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file='./entitlements.plist',
    icon=['resources/QFIcon.icns'],
)

app = BUNDLE(
    exe,
    name='QuantiFish.app',
    icon='resources/QFIcon.icns',
    info_plist={
        'CFBundleVersion': '2.1.2',
        'CFBundleShortVersionString': '2.1.2',
        'NSPrincipalClass': 'NSApplication',
    },
)
