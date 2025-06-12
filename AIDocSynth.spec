# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

# --- Build Mode & Platform ---
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"
dev = os.getenv("PYI_MODE", "release") == "dev"

# --- Data Collection Helpers ---
pyside_plugins = collect_data_files("PySide6", subdir="plugins", include_py_files=False)
a = Analysis(
    ['run.py'],
    pathex=[],
    # --- Qt / PySide6 Plugins & Shiboken --- 
    binaries=collect_dynamic_libs("PySide6") + collect_dynamic_libs("shiboken6"),
    # --- Data Files ---
    datas=pyside_plugins + [
        ('aidocsynth/ui/resources', 'aidocsynth/ui/resources'),
        ('aidocsynth/prompts', 'aidocsynth/prompts')
    ],
    # --- Hidden Imports ---
    hiddenimports=[
        'PySide6.QtSvg',
        'PySide6.QtNetwork',
        'openai',
        'httpx',
        'anyio',
        'ollama',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # --- Excludes ---
    excludes=['pytest', 'tensorboard', 'numpy.tests', 'torch.testing', 'torch.backends.mkldnn'],
    noarchive=dev,
)

pyz = PYZ(a.pure, lazy=not dev)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AIDocSynth',
    debug=dev,
    bootloader_ignore_signals=False,
    strip=not dev,
    upx=not dev,
    # --- Platform-specific settings ---
    runtime_tmpdir=None if IS_MAC else os.path.expanduser("~/.aidocsynth_cache"),
    icon='aidocsynth/ui/resources/app_icon.icns' if IS_MAC else 'aidocsynth/ui/resources/app_icon.ico',
    console=dev,
)

# --- macOS App Bundle ---
# This section is only executed when building on macOS.
if IS_MAC:
    app = BUNDLE(
        exe,
        name='AIDocSynth.app',
        icon='aidocsynth/ui/resources/app_icon.icns',
        bundle_identifier='com.tobit0101.AIDocSynth',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSMinimumSystemVersion': '10.13.0',
            'CFBundleDisplayName': 'AI Doc Synth',
            'CFBundleVersion': '0.1.0',
            'CFBundleShortVersionString': '0.1.0',
            'NSHumanReadableCopyright': 'Copyright 2025 Tobias Müller. All rights reserved.'
        }
    )

# --- Windows One-Dir-Build Output ---
if IS_WIN:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=not dev,
        upx=not dev,
        name='AIDocSynth'
    )
