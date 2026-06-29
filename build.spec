# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the PHAST Temperature Analyser (directory bundle).

The app imports only:
  - PySide6.QtWidgets / QtCore / QtGui   (GUI)
  - pandas + openpyxl                     (Excel read/write)
  - numpy + scipy.interpolate             (interpolation)

Everything else in the Qt/scientific stack is excluded to keep the
on-disk footprint as small as possible. Built for Windows / Python 3.13.
"""

import os
import shutil

APP_NAME = "PhastTemperatureAnalyser"

# 'strip' is a GNU binutils tool (Linux/macOS). It isn't shipped with Windows
# and, when missing, breaks the EXE stage. Enable it only when it's on PATH so
# the build still optimises on Linux/macOS CI but works out-of-the-box on Windows.
USE_STRIP = shutil.which("strip") is not None

# --- Modules the app never imports -----------------------------------------
# Excluding a PySide6 sub-module stops the PySide6 hook from collecting its
# (often large) Qt6 DLLs and plugins.
excludes = [
    # --- Unused PySide6 / Qt sub-modules ---
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickTest",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtWebView",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSpatialAudio",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs",
    "PySide6.QtGraphsWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSql",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSerialBus",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtUiTools",
    "PySide6.QtHelp",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPrintSupport",
    "PySide6.QtConcurrent",
    "PySide6.QtXml",
    "PySide6.QtStateMachine",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtTextToSpeech",
    "PySide6.QtHttpServer",
    "PySide6.QtDBus",
    # --- Other GUI toolkits we don't use ---
    "PyQt5",
    "PyQt6",
    "PySide2",
    "tkinter",
    "_tkinter",
    "Tkinter",
    # --- Unused matplotlib backends (matplotlib isn't even a dependency,
    #     but exclude defensively in case a transitive dep pulls it) ---
    "matplotlib",
    "matplotlib.backends._backend_tk",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends.backend_tkcairo",
    "matplotlib.backends.backend_wx",
    "matplotlib.backends.backend_wxagg",
    "matplotlib.backends.backend_gtk3agg",
    "matplotlib.backends.backend_gtk4agg",
    "matplotlib.backends.backend_webagg",
    "matplotlib.backends.backend_macosx",
    # --- Dev / test / misc baggage ---
    "numpy.f2py",
    "numpy.distutils",
    "numpy.tests",
    "scipy.tests",
    "pandas.tests",
    "PIL",
    "IPython",
    "pytest",
    "setuptools._distutils",
]

# --- DLLs UPX is known to corrupt (skip compression for these) -------------
upx_exclude = [
    "python313.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
    "Qt6Pdf.dll",
    "qwindows.dll",
    "qwindowsvistastyle.dll",
]


a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)

# Drop any *.tests packages that slipped into the module graph.
a.pure = [m for m in a.pure if "tests" not in m[0].split(".")]

# Qt6 libraries that get pulled in as *transitive binary dependencies* of kept
# Qt libs/plugins, even though the code never imports their Python bindings.
# Module `excludes` can't remove these (they aren't in the import graph), so we
# drop them by binary name. A pure QtWidgets app needs none of them.
_QT_BINARY_DENY = (
    "qt6qml", "qt6quick", "qt6pdf", "qt63d", "qt6multimedia",
    "qt6spatialaudio", "qt6charts", "qt6datavisualization", "qt6graphs",
    "qt6svg", "qt6websockets", "qt6webchannel", "qt6webengine",
    "qt6sensors", "qt6nfc", "qt6bluetooth", "qt6positioning",
    "qt6location", "qt6serialport", "qt6serialbus", "qt6scxml",
    "qt6remoteobjects", "qt6texttospeech", "qt6httpserver",
    "qt6test", "qt6designer", "qt6help", "qt6sql",
)


def _keep_binary(dest):
    return not os.path.basename(dest).lower().startswith(_QT_BINARY_DENY)


def _keep_data(dest):
    parts = dest.replace("\\", "/").lower().split("/")
    # Qt ships ~40 translation catalogues we don't need (English UI only).
    if "translations" in parts and dest.lower().endswith(".qm"):
        return False
    # PySide6/qml/* — QML modules, unused by a QtWidgets app.
    if "qml" in parts:
        return False
    return True


a.binaries = [b for b in a.binaries if _keep_binary(b[0])]
a.datas = [d for d in a.datas if _keep_data(d[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=USE_STRIP,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=USE_STRIP,
    upx=True,
    upx_exclude=upx_exclude,
    name=APP_NAME,
)
