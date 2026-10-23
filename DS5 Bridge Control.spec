# -*- mode: python ; coding: utf-8 -*-

datas = [
    ('assets', 'assets'),
    ('ds5_bridge/qml', 'ds5_bridge/qml'),
]
binaries = []
hiddenimports = [
    'hid',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickControls2',
    'PySide6.QtQuickLayouts',
    'PySide6.QtWidgets',
]


a = Analysis(
    ['ds5_qml_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchaudio",
        "torchvision",
        "tensorflow",
        "keras",
        "onnxruntime",
        "transformers",
        "sklearn",
        "scipy",
        "pandas",
        "matplotlib",
        "numba",
        "llvmlite",
        "cv2",
        "sympy",
        "pytest",
        "_pytest",
        "IPython",
        "jupyter",
        "notebook",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebChannel",
        "PySide6.QtWebSockets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtQuick3D",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtLocation",
        "PySide6.QtSensors",
        "PySide6.QtTest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# PySide6's QtQml hook pulls the whole Qt6 binary set (including a 194 MB
# WebEngine DLL). The QML UI only uses QtQuick/Controls/Layouts, so drop the
# binaries that cannot be reached from those imports.
_DROP_BINARIES = (
    "Qt6WebEngine",
    "QtWebEngine",
    "Qt6Pdf",
    "Qt6Quick3D",
    "Qt6ShaderTools",
)
a.binaries = [
    entry
    for entry in a.binaries
    if not any(token in str(part) for part in entry[:2] for token in _DROP_BINARIES)
]

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DS5 Bridge Control',
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
    icon=['assets/ds5_bridge.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DS5 Bridge Control',
)
