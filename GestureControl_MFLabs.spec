# -*- mode: python ; coding: utf-8 -*-

MP = 'C:\\Users\\jimmy\\AppData\\Local\\Python\\pythoncore-3.11-64\\Lib\\site-packages\\mediapipe'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        (MP + '\\tasks\\c\\libmediapipe.dll', 'mediapipe/tasks/c'),
    ],
    datas=[
        ('config.json', '.'),
        ('hand_landmarker.task', '.'),
        ('logo_sidebar.png', '.'),
        ('logo.ico', '.'),
        ('banner.png', '.'),
        (MP, 'mediapipe'),
    ],
    hiddenimports=[
        'mediapipe.tasks',
        'mediapipe.tasks.python',
        'mediapipe.tasks.python.vision',
        'mediapipe.tasks.python.core',
    ],
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
    name='GestureControl_MFLabs',
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
    icon=['logo.ico'],
)
