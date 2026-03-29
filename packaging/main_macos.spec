# -*- mode: python ; coding: utf-8 -*-
import os

ROOT = os.path.normpath(os.path.join(SPECPATH, '..'))

# Preferir .icns no macOS (gerado pelo CI), fallback para .ico
_icns = os.path.join(ROOT, 'memorylab.icns')
_ico  = os.path.join(ROOT, 'memorylab.ico')
APP_ICON = _icns if os.path.exists(_icns) else _ico

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (APP_ICON, '.'),
        (os.path.join(ROOT, 'qt_compat.py'), '.'),
        (os.path.join(ROOT, 'procurar_objeto.py'), '.'),
        (os.path.join(ROOT, 'procurar_distvel.py'), '.'),
        (os.path.join(ROOT, 'updater.py'), '.'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'openpyxl.utils.dataframe',
        'openpyxl.worksheet',
        'openpyxl.worksheet.worksheet',
        'PySide6',
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'numpy.distutils',
        'tkinter',
        'test',
        'unittest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NeuroTrace',
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
    icon=APP_ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NeuroTrace',
)

app = BUNDLE(
    coll,
    name='NeuroTrace.app',
    icon=APP_ICON,
    bundle_identifier='com.rodrigoorvate.neurotrace',
    info_plist={
        'CFBundleDisplayName': 'NeuroTrace',
        'CFBundleShortVersionString': '2.0.1',
        'CFBundleVersion': '2.0.1',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15',
        'NSRequiresAquaSystemAppearance': False,
    },
)
