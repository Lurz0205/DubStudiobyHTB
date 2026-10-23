# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/sieut/Documents/ToolDichThuat/start_app.py'],
    pathex=[],
    binaries=[],
    datas=[('ui', 'ui'), ('dubstudio', 'dubstudio'), ('config', 'config')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'triton', 'onnxruntime', 'ctranslate2', 'nvidia', 'scipy', 'numba', 'llvmlite', 'matplotlib', 'sympy', 'mpmath', 'sklearn', 'pandas', 'dask', 'cupy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DubStudio',
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
    icon=['C:/Users/sieut/Documents/ToolDichThuat/dubstudio.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DubStudio',
)
