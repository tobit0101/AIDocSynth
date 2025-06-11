#!/bin/bash
#
# Release Build Script for AIDocSynth
#
# This script creates a final, optimized build for distribution.
# - Smaller file size (UPX compression, stripped symbols)
# - Faster startup
# - No console window
#
set -e

# --- Environment for macOS ARM64 Build ---
export ARCHFLAGS="-arch arm64"
export QT_MAC_WANTS_LAYER=1 # Recommended for PySide6 on Apple Silicon

echo "🚀 Compiling Qt resources..."
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py

echo "🚀 Building for macOS ARM64 (Release)..."
# The spec file uses PYI_MODE to set dev=False
PYI_MODE=release pyinstaller --noconfirm --distpath dist --workpath build AIDocSynth.spec

echo "✅ Release build complete in dist/"

#

echo "📦 Starting release build..."

pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py

# Run PyInstaller for a release build (PYI_MODE is not set)
# --jobs=auto uses all available CPU cores to speed up the build.
pyinstaller --noconfirm --distpath dist --workpath .build AIDocSynth.spec

echo "🎉 Release build complete. You can find the app in the 'dist' folder."
