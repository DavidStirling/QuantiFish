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
    [],
    exclude_binaries=True,
    name='quantifish',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources/QFIcon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QuantiFish',
)
app = BUNDLE(
    coll,
    name='QuantiFish.app',
    icon='resources/QFIcon.icns',
    bundle_identifier="com.davidstirling.quantifish",
    info_plist={
        'CFBundleShortVersionString': '2.1.2',
        'NSPrincipalClass': 'NSApplication',
    },
)
