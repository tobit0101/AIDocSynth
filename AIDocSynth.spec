# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

# --- Build Mode ---
# Set PYI_MODE=dev for development builds (faster, not optimized)
# e.g., PYI_MODE=dev pyinstaller AIDocSynth.spec
# For release builds, run without setting PYI_MODE.
dev = os.getenv("PYI_MODE", "release") == "dev"

a = Analysis(
    ['run.py'],
    pathex=[],
    # --- Qt / PySide6 Plugins ---
    # Collects necessary .dll/.dylib files (e.g., for image formats, platforms)
    binaries=collect_dynamic_libs("PySide6"),
    # --- Data Files ---
    # Bundles all resources and prompts, plus Qt plugins
    datas=collect_data_files("PySide6", subdir="plugins") +
          collect_data_files("aidocsynth/ui/resources", destdir="aidocsynth/ui/resources") +
          collect_data_files("aidocsynth/prompts", destdir="aidocsynth/prompts"),
    # --- Hidden Imports ---
    # Core imports + conditional provider imports based on environment variables.
    # To exclude a provider, set its variable to "false", e.g., INC_OPENAI=false
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
    # Reduces final binary size by excluding testing frameworks and unused backends.
    excludes=['pytest', 'tensorboard', 'numpy.tests', 'torch.testing', 'torch.backends.mkldnn'],
    # --- Dev vs. Release ---
    # noarchive=True: Faster dev builds, modules are not packed into the PYZ archive.
    noarchive=dev,
)

# --- Python Archive (PYZ) ---
# lazy=not dev: Enables lazy imports for faster startup in release builds.
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
    # --- Build Configuration ---
    # strip: Removes debug symbols and docstrings in release builds.
    # upx: Compresses binaries in release builds (if UPX is installed).
    strip=not dev,
    upx=not dev,
    # --- OneDir Cache ---
    # For one-file builds, this speeds up subsequent starts. Harmless for one-dir.
    runtime_tmpdir=os.path.expanduser("~/.aidocsynth_cache"),
    # console=True shows the terminal window, useful for dev builds.
    console=dev,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='aidocsynth/ui/resources/app_icon.ico',  # For Windows
)

app = BUNDLE(
    exe,
    name='AIDocSynth.app',
    icon='aidocsynth/ui/resources/app_icon.icns',  # For macOS
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
