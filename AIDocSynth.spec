# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

# --- Build Mode & Platform ---
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"
dev = os.getenv("PYI_MODE", "release") == "dev"

a = Analysis(
    ['run.py'],
    pathex=[],
    # --- Qt / PySide6 Plugins ---
    binaries=collect_dynamic_libs("PySide6"),
    # --- Data Files ---
    datas=collect_data_files("PySide6", subdir="plugins") +
          collect_data_files("aidocsynth/ui/resources", destdir="aidocsynth/ui/resources") +
          collect_data_files("aidocsynth/prompts", destdir="aidocsynth/prompts"),
    # --- Hidden Imports ---
    hiddenimports=[
        'PySide6.QtSvg', 'PySide6.QtNetwork',
        *(['openai','httpx','anyio'] if os.getenv("INC_OPENAI", "true").lower() == "true" else []),
        *(['azure'] if os.getenv("INC_AZURE", "true").lower() == "true" else []),
        *(['ollama'] if os.getenv("INC_OLLAMA", "true").lower() == "true" else []),
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
    icon='aidocsynth/ui/resources/app_icon.ico' if IS_WIN else None,
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
